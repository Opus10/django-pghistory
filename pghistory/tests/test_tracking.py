import ddf
from django.db import connection
import pytest

import pghistory.models
import pghistory.tests.models as test_models


@pytest.mark.django_db(transaction=True)
def test_concurrent_index_creation():
    """
    Verify that context tracking works even when creating
    concurrent indices. This operation is not compatible with
    context tracking and should be ignored
    """
    with pghistory.context(key1='val1'):
        with connection.cursor() as cursor:
            cursor.execute(
                f'''
                CREATE INDEX   CONCURRENTLY IF NOT EXISTS idx_name ON
                {test_models.SnapshotModel._meta.db_table}
                (dt_field)
            '''
            )


@pytest.mark.django_db
def test_named_cursor():
    """
    Verify that context tracking still works when a named
    cursor is used. Named cursors are used in Django when using
    .iterator()
    """
    with pghistory.context(key1='val1') as ctx:
        # Creating the EventModel will trigger an event, which will
        # attach the current context
        ddf.G('tests.EventModel')

        ctx1 = pghistory.models.Context.objects.get()
        assert ctx1.id == ctx.id
        assert ctx1.metadata == {'key1': 'val1'}

        for val in test_models.EventModel.objects.iterator():
            assert val


@pytest.mark.django_db()
def test_scope_inside_transaction():
    """
    Tests some characteristics of context scope when in a transaction
    """
    # No context should be attached at first
    no_ctx = ddf.G('tests.EventModel')
    assert no_ctx.event.get().pgh_context_id is None

    # Attach context
    with pghistory.context() as ctx:
        with_ctx = ddf.G('tests.EventModel')
        assert with_ctx.event.get().pgh_context_id == ctx.id

    # Although we are out of the context manager, we are still in
    # a transaction, so local context variables will still persist
    with_local_ctx = ddf.G('tests.EventModel')
    assert with_local_ctx.event.get().pgh_context_id == ctx.id


@pytest.mark.django_db
def test_track_context_id(mocker):
    """
    Verifies the tracker attaches a context uuid
    """
    with pghistory.context() as ctx:
        m = ddf.G('tests.EventModel')
        orig_dt = m.dt_field
        orig_int = m.int_field

        assert list(m.event.values()) == [
            {
                'pgh_created_at': mocker.ANY,
                'pgh_context_id': ctx.id,
                'dt_field': orig_dt,
                'pgh_id': mocker.ANY,
                'pgh_label': 'model.create',
                'int_field': orig_int,
                'pgh_obj_id': m.id,
                'id': m.id,
            }
        ]


@pytest.mark.django_db
def test_track_context_metadata(mocker):
    """
    Verifies that the proper metadata is attached to a tracked event
    """
    with pghistory.context(key1='val1') as ctx:
        # Creating the EventModel will trigger an event, which will
        # attach the current context
        m1 = ddf.G('tests.EventModel')

        ctx1 = pghistory.models.Context.objects.get()
        assert ctx1.id == ctx.id
        assert ctx1.metadata == {'key1': 'val1'}

        # Attach additional metadata
        with pghistory.context(key2='val2'):
            # Perform another event so that context will be flushed
            m1.save()

            ctx1.refresh_from_db()
            assert ctx1.id == ctx.id
            assert ctx1.metadata == {'key1': 'val1', 'key2': 'val2'}

        # Even after exiting inner context, the metadata persists until
        # the end of the outer context
        m1.save()
        ctx1.refresh_from_db()
        assert ctx1.id == ctx.id
        assert ctx1.metadata == {'key1': 'val1', 'key2': 'val2'}

    # Starting a new tracking session will result in a new context object
    with pghistory.context() as ctx:
        ddf.G('tests.EventModel')
        assert pghistory.models.Context.objects.count() == 2
        ctx2 = pghistory.models.Context.objects.exclude(id=ctx1.id).get()
        assert ctx2.id == ctx.id
        assert ctx2.metadata == {}


@pytest.mark.django_db
def test_nested_tracking(mocker):
    """
    Verifies the tracker can be nested many times without issue
    """
    with pghistory.context() as ctx:
        with pghistory.context() as nested_ctx:
            assert ctx.id == nested_ctx.id
            m = ddf.G('tests.EventModel', int_field=2)

            assert list(m.event.values()) == [
                {
                    'pgh_created_at': mocker.ANY,
                    'pgh_context_id': ctx.id,
                    'dt_field': m.dt_field,
                    'pgh_id': mocker.ANY,
                    'pgh_label': 'model.create',
                    'int_field': m.int_field,
                    'pgh_obj_id': m.id,
                    'id': m.id,
                }
            ]

        m.save()

        assert list(m.event.values().order_by('pgh_id')) == [
            {
                'pgh_created_at': mocker.ANY,
                'pgh_context_id': ctx.id,
                'dt_field': m.dt_field,
                'pgh_id': mocker.ANY,
                'pgh_label': 'model.create',
                'int_field': m.int_field,
                'pgh_obj_id': m.id,
                'id': m.id,
            },
            {
                'pgh_created_at': mocker.ANY,
                'pgh_context_id': ctx.id,
                'dt_field': m.dt_field,
                'pgh_id': mocker.ANY,
                'pgh_label': 'before_update',
                'int_field': m.int_field,
                'pgh_obj_id': m.id,
                'id': m.id,
            },
        ]
