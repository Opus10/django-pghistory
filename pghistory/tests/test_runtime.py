import pytest
from django.db import connection

import pghistory.runtime
import pghistory.utils


@pytest.mark.parametrize(
    "statement, expected",
    [
        ("create index concurrently", True),
        ("create index", False),
        (b"create index concurrently", True),
        (b"create index", False),
    ],
)
def test_is_concurrent_statement(statement, expected):
    assert pghistory.runtime._is_concurrent_statement(statement) == expected


@pytest.mark.skipif(
    pghistory.utils.psycopg_maj_version == 3, reason="Psycopg2 preserves entire query"
)
@pytest.mark.django_db
@pytest.mark.parametrize(
    "sql, params",
    [
        ("select count(*) from auth_user where id = %s", (1,)),
        ("select count(*) from auth_user where id = %(id)s", {"id": 5}),
        ("select count(*) from auth_user", ()),
        (b"select count(*) from auth_user where id = %s", (1,)),
        (b"select count(*) from auth_user where id = %(id)s", {"id": 5}),
        (b"select count(*) from auth_user", ()),
    ],
)
def test_inject_history_context(settings, mocker, sql, params):
    mocker.patch("uuid.uuid4", return_value="uuid", autospec=True)
    settings.DEBUG = True
    expected_sql = "SELECT set_config('pghistory.context_id', 'uuid', true), set_config('pghistory.context_metadata', '{\"hello\": \"world\"}', true);"  # noqa
    with pghistory.context(hello="world"):
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            query = connection.queries[-1]
            assert query["sql"].startswith(expected_sql)
