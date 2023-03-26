import collections
import contextlib
import json
import threading
import uuid

from django.db import connection

from pghistory import config


_tracker = threading.local()


Context = collections.namedtuple("Context", ["id", "metadata"])


def _is_concurrent_statement(sql):
    """
    True if the sql statement is concurrent and cannot be ran in a transaction
    """
    sql = sql.strip().lower() if sql else ""
    return sql.startswith("create") and "concurrently" in sql


def _inject_history_context(execute, sql, params, many, context):
    cursor = context["cursor"]

    # A named cursor automatically prepends
    # "NO SCROLL CURSOR WITHOUT HOLD FOR" to the query, which
    # causes invalid SQL to be generated. There is no way
    # to override this behavior in psycopg2, so context tracking
    # cannot happen for named cursors. Django only names cursors
    # for iterators and other statements that read the database,
    # so it seems to be safe to ignore named cursors.
    #
    # Concurrent index creation is also incompatible with local variable
    # setting. Ignore these cases for now.
    if not cursor.name and not _is_concurrent_statement(sql):
        # Metadata is stored as a serialized JSON string with escaped
        # single quotes
        metadata_str = json.dumps(_tracker.value.metadata, cls=config.json_encoder())

        sql = f"SET LOCAL pghistory.context_id=%s; SET LOCAL pghistory.context_metadata=%s;{sql}"
        params = [str(_tracker.value.id), metadata_str, *(params or ())]

    return execute(sql, params, many, context)


class context(contextlib.ContextDecorator):
    """
    A context manager that groups changes under the same context and
    adds additional metadata about the event.

    Context is added as variables at the beginning of every SQL statement.
    By default, all variables are localized to the transaction (i.e
    SET LOCAL), meaning they will only persist for the statement/transaction
    and not across the session.

    Once any code has entered ``pghistory.context``, all subsequent
    entrances of ``pghistory.context`` will be grouped under the same
    context until the top-most parent exits.

    To add context only if a parent has already entered ``pghistory.context``,
    one can call ``pghistory.context`` as a function without entering it.
    The metadata set in the function call will be part of the context if
    ``pghistory.context`` has previously been entered. Otherwise it will
    be ignored.

    Args:
        metadata (dict): Metadata that should be attached to the tracking
            context

    Example:
        Here we track a "key" with a value of "value"::

            with pghistory.context(key='value'):
                # Do things..
                # All tracked events will have the same ``pgh_context``
                # foreign key, and the context object will include
                # {'key': 'value'} in its metadata.
                # Nesting the tracker adds additional metadata to the current
                # context

            # Add metadata if a parent piece of code has already entered
            # pghistory.context
            pghistory.context(key='value')

    Notes:
        Context tracking is compatible for most scenarios, but it currently
        does not work for named cursors. Django uses named cursors for
        the .iterator() operator, which has no effect on history tracking.
        However, there may be other usages of named cursors in Django where
        history context is ignored.
    """

    def __init__(self, **metadata):
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
