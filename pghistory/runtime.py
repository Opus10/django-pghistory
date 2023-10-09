import collections
import contextlib
import json
import threading
import uuid
from typing import Any

from django.db import connection

from pghistory import config, utils

if utils.psycopg_maj_version == 2:
    import psycopg2.extensions
elif utils.psycopg_maj_version == 3:
    import psycopg.pq
else:
    raise AssertionError


_tracker = threading.local()


Context = collections.namedtuple("Context", ["id", "metadata"])


def _is_concurrent_statement(sql):
    """
    True if the sql statement is concurrent and cannot be ran in a transaction
    """
    sql = sql.strip().lower() if sql else ""
    return sql.startswith("create") and "concurrently" in sql


def _is_transaction_errored(cursor):
    """
    True if the current transaction is in an errored state
    """
    if utils.psycopg_maj_version == 2:
        return (
            cursor.connection.get_transaction_status()
            == psycopg2.extensions.TRANSACTION_STATUS_INERROR
        )
    elif utils.psycopg_maj_version == 3:
        return cursor.connection.info.transaction_status == psycopg.pq.TransactionStatus.INERROR
    else:
        raise AssertionError


def _can_inject_variable(cursor, sql):
    """True if we can inject a SQL variable into a statement.

    A named cursor automatically prepends
    "NO SCROLL CURSOR WITHOUT HOLD FOR" to the query, which
    causes invalid SQL to be generated. There is no way
    to override this behavior in psycopg, so ignoring triggers
    cannot happen for named cursors. Django only names cursors
    for iterators and other statements that read the database,
    so it seems to be safe to ignore named cursors.

    Concurrent index creation is also incompatible with local variable
    setting. Ignore these cases for now.
    """
    return (
        not getattr(cursor, "name", None)
        and not _is_concurrent_statement(sql)
        and not _is_transaction_errored(cursor)
    )


def _execute_wrapper(execute_result):
    if utils.psycopg_maj_version == 3:
        while execute_result.nextset():
            pass
    return execute_result


def _inject_history_context(execute, sql, params, many, context):
    if _can_inject_variable(context["cursor"], sql):
        # Metadata is stored as a serialized JSON string with escaped
        # single quotes
        serialized_metadata = json.dumps(_tracker.value.metadata, cls=config.json_encoder())

        sql = (
            "SELECT set_config('pghistory.context_id', %s, true), "
            "set_config('pghistory.context_metadata', %s, true); "
        ) + sql
        params = [str(_tracker.value.id), serialized_metadata, *(params or ())]

    return _execute_wrapper(execute(sql, params, many, context))


class context(contextlib.ContextDecorator):
    """
    A context manager that groups changes under the same context and
    adds additional metadata about the event.

    Context is added as variables at the beginning of every SQL statement.
    By default, all variables are localized to the transaction (i.e
    SET LOCAL), meaning they will only persist for the statement/transaction
    and not across the session.

    Once any code has entered [pghistory.context][], all subsequent
    entrances of [pghistory.context][] will be grouped under the same
    context until the top-most parent exits.

    To add context only if a parent has already entered [pghistory.context][],
    one can call [pghistory.context][] as a function without entering it.
    The metadata set in the function call will be part of the context if
    [pghistory.context][] has previously been entered. Otherwise it will
    be ignored.

    Attributes:
        **metadata: Metadata that should be attached to the tracking
            context

    Example:
        Here we track a "key" with a value of "value":

            with pghistory.context(key='value'):
                # Do things..
                # All tracked events will have the same `pgh_context`
                # foreign key, and the context object will include
                # {'key': 'value'} in its metadata.
                # Nesting the tracker adds additional metadata to the current
                # context

            # Add metadata if a parent piece of code has already entered
            # pghistory.context
            pghistory.context(key='value')

    Note:
        Context tracking is compatible for most scenarios, but it currently
        does not work for named cursors. Django uses named cursors for
        the .iterator() operator, which has no effect on history tracking.
        However, there may be other usages of named cursors in Django where
        history context is ignored.
    """

    def __init__(self, **metadata: Any):
        self.metadata = metadata
        self._pre_execute_hook = None

        if hasattr(_tracker, "value"):
            _tracker.value.metadata.update(**self.metadata)

    def __enter__(self):
        if not hasattr(_tracker, "value"):
            self._pre_execute_hook = connection.execute_wrapper(_inject_history_context)
            self._pre_execute_hook.__enter__()
            _tracker.value = Context(id=uuid.uuid4(), metadata=self.metadata)

        return _tracker.value

    def __exit__(self, *exc):
        if self._pre_execute_hook:
            delattr(_tracker, "value")
            self._pre_execute_hook.__exit__(*exc)
