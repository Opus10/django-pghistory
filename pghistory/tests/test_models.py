import datetime as dt

import ddf
import django
from django.core.management import call_command
import pytest

import pghistory.models
import pghistory.tests.models as test_models


@pytest.mark.django_db
def test_revert():
    """Tests the .revert() method on event models"""
    user = ddf.G("auth.User")
    m = ddf.G(test_models.DenormContext, int_field=1, fk_field=user)

    m.int_field = 2
    m.fk_field = None
    m.save()

    m.int_field = 3
    m.save()

    assert test_models.DenormContextEvent.objects.count() == 3
    assert m.event.count() == 3

    r = m.event.filter(pgh_label="snapshot").order_by("pgh_id")[0].revert()
    assert r.int_field == 1
    assert r.fk_field_id == user.id

    r = m.event.filter(pgh_label="snapshot").order_by("pgh_id")[1].revert()
    assert r.int_field == 2
    assert not r.fk_field_id

    r = m.event.filter(pgh_label="snapshot").order_by("pgh_id")[2].revert()
    assert r.int_field == 3
    assert not r.fk_field_id

    m = ddf.G(test_models.SnapshotModel)
    with pytest.raises(RuntimeError):
        m.dt_field_snapshot.last().revert()


@pytest.mark.django_db
def test_custom_event_proxy():
    """Verifies that proxy fields work on custom event models"""
    user = ddf.G("auth.User", username="hello")

    with pghistory.context(url="https://www.google.com", user=user.pk):
        ddf.G(test_models.EventModel)

    if django.VERSION < (3, 2):
        with pytest.raises(RuntimeError):
            assert test_models.CustomEventProxy.objects.values("url", "auth_user__username")
    else:
        assert list(test_models.CustomEventProxy.objects.values("url", "auth_user__username")) == [
            {"url": "https://www.google.com", "auth_user__username": "hello"}
        ]


@pytest.mark.django_db
def test_aggregate_event_default_manager():
    """Verifies the default manager for aggregate events returns no results"""
    assert list(pghistory.models.Events.no_objects.all()) == []


@pytest.mark.django_db
def test_events_no_history():
    """
    Tests the Events proxy on a model that has no history tracking
    """
    untracked = ddf.G(test_models.UntrackedModel)
    assert list(pghistory.models.Events.objects.references(untracked).all()) == []


@pytest.mark.django_db
def test_events_tracks(django_assert_num_queries):
    """
    Tests using tracks() with events
    """
    ss1 = ddf.G(test_models.SnapshotModel)
    ss2 = ddf.G(test_models.SnapshotModel)
    ss2.int_field += 1
    ss2.save()

    dc1 = ddf.G(test_models.DenormContext)

    assert pghistory.models.Events.objects.tracks(ss1, ss2).count() == 11
    assert (
        pghistory.models.Events.objects.tracks(test_models.SnapshotModel.objects.all()).count()
        == 11
    )
    assert pghistory.models.Events.objects.tracks(ss1).count() == 4
    assert pghistory.models.Events.objects.tracks(ss2).count() == 7
    # This tracking model does not have the pgh_obj field
    assert (
        not pghistory.models.Events.objects.tracks(ss2).across("tests.NoPghObjSnapshot").exists()
    )

    assert pghistory.models.Events.objects.tracks([dc1]).count() == 2


@pytest.mark.django_db(transaction=True)
def test_events_no_references(django_assert_num_queries):
    """
    Test filtering events when using no referenced objects.
    """
    actor = ddf.G("auth.User")
    # Create an event trail under various contexts
    with pghistory.context(key="value1", user=actor.id):
        user1 = ddf.G("auth.User")
        user2 = ddf.G("auth.User")
        sm1 = ddf.G(
            test_models.SnapshotModel,
            dt_field=dt.datetime(2020, 6, 17, tzinfo=dt.timezone.utc),
            int_field=1,
            fk_field=user1,
        )
        sm2 = ddf.G(
            test_models.SnapshotModel,
            dt_field=dt.datetime(2020, 6, 22, tzinfo=dt.timezone.utc),
            int_field=10,
            fk_field=user2,
        )

    with pghistory.context(key="value2", url="https://url.com", user=0):
        sm1.int_field = 2
        sm1.save()
        sm2.int_field = 22
        sm2.save()

    ddf.G(test_models.DenormContext)
    with pghistory.context(key="value2", url="https://url.com", user=0):
        ddf.G(test_models.DenormContext)

    # Make sure we can query without performance issues
    with django_assert_num_queries(1):
        assert {
            e.pgh_context["key"]
            for e in pghistory.models.Events.objects.filter(pgh_context__isnull=False)
        } == {"value1", "value2"}

    assert pghistory.models.Events.objects.values().count() == 22

    # Use the CustomEvents proxy to join on metadata fields.
    # In this case, we join the email of the user in the metadata.
    # Since we provided an invalid user for an event, "None" is returned
    assert set(
        test_models.CustomEvents.objects.values_list("user__email", flat=True).distinct()
    ) == {actor.email, None}

    assert set(test_models.CustomEvents.objects.values_list("url", flat=True).distinct()) == {
        "https://url.com",
        None,
    }


@pytest.mark.django_db(transaction=True)
def test_events_references_joining_filtering(django_assert_num_queries, mocker):
    """
    Test joining and other filtering for the Events proxy.
    Use the CustomEvents subclass to verify we can filter/join on
    context metadata
    """
    actor = ddf.G("auth.User")
    # Create an event trail under various contexts
    with pghistory.context(key="value1", user=actor.id):
        user1 = ddf.G("auth.User")
        user2 = ddf.G("auth.User")
        sm1 = ddf.G(
            test_models.SnapshotModel,
            dt_field=dt.datetime(2020, 6, 17, tzinfo=dt.timezone.utc),
            int_field=1,
            fk_field=user1,
        )
        sm2 = ddf.G(
            test_models.SnapshotModel,
            dt_field=dt.datetime(2020, 6, 22, tzinfo=dt.timezone.utc),
            int_field=10,
            fk_field=user2,
        )

    with pghistory.context(key="value2", url="https://url.com", user=0):
        sm1.int_field = 2
        sm1.save()
        sm2.int_field = 22
        sm2.save()

    with pghistory.context(key="value3", user=actor.id):
        sm1.dt_field = dt.datetime(2020, 6, 19, tzinfo=dt.timezone.utc)
        sm1.int_field = 3
        sm1.save()
        sm2.int_field = 33
        sm2.save()
        sm2.fk_field = user1
        sm2.save()

    # Make sure we can join against our proxy model without performance issues
    with django_assert_num_queries(1):
        assert {
            e.pgh_context["key"]
            for e in pghistory.models.Events.objects.references(sm1).filter(
                pgh_context__isnull=False
            )
        } == {"value1", "value2", "value3"}

    assert list(
        pghistory.models.Events.objects.references(user1)
        .filter(pgh_label="snapshot", pgh_data__int_field=3)
        .values()
    ) == [
        {
            "pgh_slug": mocker.ANY,
            "pgh_context_id": mocker.ANY,
            "pgh_context": {"key": "value3", "user": actor.id},
            "pgh_created_at": mocker.ANY,
            "pgh_data": {
                "dt_field": "2020-06-19T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": {
                "dt_field": [
                    "2020-06-17T00:00:00+00:00",
                    "2020-06-19T00:00:00+00:00",
                ],
                "int_field": [2, 3],
            },
            "pgh_id": mocker.ANY,
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
            "pgh_obj_model": "tests.SnapshotModel",
            "pgh_obj_id": str(sm1.pk),
        }
    ]

    # Use the CustomEvents proxy to join on metadata fields.
    # In this case, we join the email of the user in the metadata.
    # Since we provided an invalid user for an event, "None" is returned
    assert set(
        test_models.CustomEvents.objects.references(user1)
        .values_list("user__email", flat=True)
        .distinct()
    ) == {actor.email, None}

    assert set(
        test_models.CustomEvents.objects.references(user1).values_list("url", flat=True).distinct()
    ) == {"https://url.com", None}


@pytest.mark.django_db(transaction=True)
def test_events_multiple_references(django_assert_num_queries, mocker):
    """
    Test Events proxy with multiple referenced objects.
    """
    user1 = ddf.G("auth.User")
    user2 = ddf.G("auth.User")
    sm1 = ddf.G(
        test_models.SnapshotModel,
        dt_field=dt.datetime(2020, 6, 17, tzinfo=dt.timezone.utc),
        int_field=1,
        fk_field=user1,
    )
    sm2 = ddf.G(
        test_models.SnapshotModel,
        dt_field=dt.datetime(2020, 6, 22, tzinfo=dt.timezone.utc),
        int_field=10,
        fk_field=user2,
    )

    sm1.int_field = 3
    sm1.save()
    sm2.int_field = 33
    sm2.fk_field = user1
    sm2.save()

    default = {
        "pgh_slug": mocker.ANY,
        "pgh_context_id": None,
        "pgh_context": None,
        "pgh_created_at": mocker.ANY,
        "pgh_id": mocker.ANY,
        "pgh_label": "snapshot",
        "pgh_model": "tests.SnapshotModelSnapshot",
        "pgh_obj_model": "tests.SnapshotModel",
        "pgh_obj_id": str(sm1.pk),
    }
    wanted_result = [
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 1,
            },
            "pgh_diff": None,
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-22T00:00:00+00:00",
                "fk_field_id": user2.id,
                "id": sm2.id,
                "int_field": 10,
            },
            "pgh_diff": None,
            "pgh_obj_id": str(sm2.pk),
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": {
                "int_field": [1, 3],
            },
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-22T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm2.id,
                "int_field": 33,
            },
            "pgh_diff": {
                "int_field": [10, 33],
                "fk_field_id": [user2.id, user1.id],
            },
            "pgh_obj_id": str(sm2.pk),
        },
    ]

    assert (
        list(
            pghistory.models.Events.objects.references(sm1, sm2)
            .filter(pgh_label="snapshot")
            .order_by("pgh_created_at")
            .values()
        )
        == wanted_result
    )

    assert (
        list(
            pghistory.models.Events.objects.references(test_models.SnapshotModel.objects.all())
            .filter(pgh_label="snapshot")
            .order_by("pgh_created_at")
            .values()
        )
        == wanted_result
    )


@pytest.mark.django_db(transaction=True)
def test_events_references_denorm_context(django_assert_num_queries, mocker):
    """
    Test Events proxy with event models that have denormalized context
    """
    actor = ddf.G("auth.User")
    # Create an event trail under various contexts
    with pghistory.context(key="value1", user=actor.id):
        user1 = ddf.G("auth.User")
        user2 = ddf.G("auth.User")
        dc1 = ddf.G(
            test_models.DenormContext,
            int_field=1,
            fk_field=user1,
        )
        dc2 = ddf.G(
            test_models.DenormContext,
            int_field=10,
            fk_field=user2,
        )

    with pghistory.context(key="value2", url="https://url.com", user=0):
        dc1.int_field = 2
        dc1.save()
        dc2.int_field = 22
        dc2.save()

    with pghistory.context(key="value3", user=actor.id):
        dc1.int_field = 3
        dc1.save()
        dc2.int_field = 33
        dc2.save()
        dc2.fk_field = user1
        dc2.save()

    # Make sure we can join against our proxy model without performance issues
    with django_assert_num_queries(1):
        assert {
            e.pgh_context["key"]
            for e in pghistory.models.Events.objects.references(dc1).filter(
                pgh_context__isnull=False
            )
        } == {"value1", "value2", "value3"}

    assert list(
        pghistory.models.Events.objects.references(user1)
        .filter(pgh_label="snapshot", pgh_data__int_field=3)
        .values()
    ) == [
        {
            "pgh_slug": mocker.ANY,
            "pgh_context_id": mocker.ANY,
            "pgh_context": {"key": "value3", "user": actor.id},
            "pgh_created_at": mocker.ANY,
            "pgh_data": {
                "fk_field_id": user1.id,
                "id": dc1.id,
                "int_field": 3,
            },
            "pgh_diff": {
                "int_field": [2, 3],
            },
            "pgh_id": mocker.ANY,
            "pgh_label": "snapshot",
            "pgh_model": "tests.DenormContextEvent",
            "pgh_obj_model": "tests.DenormContext",
            "pgh_obj_id": str(dc1.id),
        }
    ]

    # Use the CustomEvents proxy to join on metadata fields.
    # In this case, we join the email of the user in the metadata.
    # Since we provided an invalid user for an event, "None" is returned
    assert set(
        test_models.CustomEvents.objects.references(user1)
        .values_list("user__email", flat=True)
        .distinct()
    ) == {actor.email, None}

    assert set(
        test_models.CustomEvents.objects.references(user1).values_list("url", flat=True).distinct()
    ) == {"https://url.com", None}


@pytest.mark.django_db
def test_events_references_custom_pk(mocker):
    """
    Verify that the Events proxy model properly aggregates
    events across models with custom PKs
    """
    cm = ddf.G(test_models.CustomModel, int_field=1)
    cm.int_field = 2
    cm.save()
    cm.save()

    default = {
        "pgh_slug": mocker.ANY,
        "pgh_context_id": None,
        "pgh_context": None,
        "pgh_created_at": mocker.ANY,
        "pgh_id": mocker.ANY,
        "pgh_obj_model": "tests.CustomModel",
        "pgh_obj_id": str(cm.pk),
    }

    assert list(
        pghistory.models.Events.objects.references(cm).order_by("pgh_model", "pgh_id").values()
    ) == [
        {
            **default,
            "pgh_data": {"integer_field": 2, "my_pk": str(cm.pk)},
            "pgh_diff": None,
            "pgh_label": "int_field_updated",
            "pgh_model": "tests.CustomModelEvent",
        },
        {
            **default,
            "pgh_data": {"integer_field": 1, "my_pk": str(cm.pk)},
            "pgh_diff": None,
            "pgh_label": "snapshot",
            "pgh_model": "tests.CustomModelSnapshot",
        },
        {
            **default,
            "pgh_data": {"integer_field": 2, "my_pk": str(cm.pk)},
            "pgh_diff": {"integer_field": [1, 2]},
            "pgh_label": "snapshot",
            "pgh_model": "tests.CustomModelSnapshot",
        },
    ]


@pytest.mark.django_db
def test_events_usage():
    """Verifies the Events queryset is used properly"""
    with pytest.raises(ValueError, match="are not of the same type"):
        list(
            pghistory.models.Events.objects.references(
                test_models.CustomModel(), test_models.CustomSnapshotModel()
            )
        )

    with pytest.raises(ValueError, match="both tracks"):
        list(
            pghistory.models.Events.objects.references(test_models.CustomModel()).tracks(
                test_models.CustomModel()
            )
        )


@pytest.mark.django_db
def test_events_references_no_obj_tracking_filters(mocker):
    """
    Verify that the Events proxy model properly aggregates
    events even when the event models have no pgh_obj reference
    """
    user1 = ddf.G("auth.User")
    user2 = ddf.G("auth.User")
    sm1 = ddf.G(
        test_models.SnapshotModel,
        dt_field=dt.datetime(2020, 6, 17, tzinfo=dt.timezone.utc),
        int_field=1,
        fk_field=user1,
    )
    sm1.int_field = 2
    sm1.save()
    sm1.dt_field = dt.datetime(2020, 6, 19, tzinfo=dt.timezone.utc)
    sm1.int_field = 3
    sm1.save()

    sm2 = ddf.G(
        test_models.SnapshotModel,
        dt_field=dt.datetime(2020, 6, 22, tzinfo=dt.timezone.utc),
        int_field=10,
        fk_field=user2,
    )
    sm2.int_field = 22
    sm2.save()
    sm2.int_field = 33
    sm2.save()
    sm2.fk_field = user1
    sm2.save()

    default = {
        "pgh_slug": mocker.ANY,
        "pgh_context_id": None,
        "pgh_context": None,
        "pgh_created_at": mocker.ANY,
        "pgh_id": mocker.ANY,
        "pgh_obj_model": "tests.SnapshotModel",
        "pgh_obj_id": str(sm1.pk),
    }

    assert list(
        pghistory.models.Events.objects.references(sm1).order_by("pgh_model", "pgh_id").values()
    ) == [
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 1,
            },
            "pgh_diff": None,
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 2,
            },
            "pgh_diff": {"int_field": [1, 2]},
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": {"int_field": [2, 3]},
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {"dt_field": "2020-06-17T00:00:00+00:00"},
            "pgh_diff": None,
            "pgh_label": "dt_field_snapshot",
            "pgh_model": "tests.SnapshotModelDtFieldEvent",
        },
        {
            **default,
            "pgh_data": {"dt_field": "2020-06-19T00:00:00+00:00"},
            "pgh_diff": {
                "dt_field": [
                    "2020-06-17T00:00:00+00:00",
                    "2020-06-19T00:00:00+00:00",
                ]
            },
            "pgh_label": "dt_field_snapshot",
            "pgh_model": "tests.SnapshotModelDtFieldEvent",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "int_field": 1,
            },
            "pgh_diff": None,
            "pgh_label": "dt_field_int_field_snapshot",
            "pgh_model": "tests.SnapshotModelDtFieldIntFieldEvent",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "int_field": 2,
            },
            "pgh_diff": {"int_field": [1, 2]},
            "pgh_label": "dt_field_int_field_snapshot",
            "pgh_model": "tests.SnapshotModelDtFieldIntFieldEvent",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-19T00:00:00+00:00",
                "int_field": 3,
            },
            "pgh_diff": {
                "dt_field": [
                    "2020-06-17T00:00:00+00:00",
                    "2020-06-19T00:00:00+00:00",
                ],
                "int_field": [2, 3],
            },
            "pgh_label": "dt_field_int_field_snapshot",
            "pgh_model": "tests.SnapshotModelDtFieldIntFieldEvent",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 1,
            },
            "pgh_diff": None,
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 2,
            },
            "pgh_diff": {"int_field": [1, 2]},
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-19T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": {
                "dt_field": [
                    "2020-06-17T00:00:00+00:00",
                    "2020-06-19T00:00:00+00:00",
                ],
                "int_field": [2, 3],
            },
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
        },
    ]

    # Check events on the user model, which will aggregate event tables
    # that have no pgh_obj. All events here will have a reference to user1
    assert list(
        pghistory.models.Events.objects.references(user1).order_by("pgh_model", "pgh_id").values()
    ) == [
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 1,
            },
            "pgh_diff": None,
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 2,
            },
            "pgh_diff": {"int_field": [1, 2]},
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": {"int_field": [2, 3]},
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm2.id,
                "int_field": 33,
            },
            "pgh_diff": None,
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
            "pgh_obj_id": str(sm2.pk),
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 1,
            },
            "pgh_diff": None,
            "pgh_label": "no_pgh_obj_snapshot",
            "pgh_model": "tests.NoPghObjSnapshot",
            "pgh_obj_id": None,
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 2,
            },
            "pgh_diff": None,
            "pgh_label": "no_pgh_obj_snapshot",
            "pgh_model": "tests.NoPghObjSnapshot",
            "pgh_obj_id": None,
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-19T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": None,
            "pgh_label": "no_pgh_obj_snapshot",
            "pgh_model": "tests.NoPghObjSnapshot",
            "pgh_obj_id": None,
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-22T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm2.id,
                "int_field": 33,
            },
            "pgh_diff": None,
            "pgh_label": "no_pgh_obj_snapshot",
            "pgh_model": "tests.NoPghObjSnapshot",
            "pgh_obj_id": None,
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 1,
            },
            "pgh_diff": None,
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-17T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 2,
            },
            "pgh_diff": {"int_field": [1, 2]},
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-19T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": {
                "dt_field": [
                    "2020-06-17T00:00:00+00:00",
                    "2020-06-19T00:00:00+00:00",
                ],
                "int_field": [2, 3],
            },
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
        },
        {
            **default,
            "pgh_data": {
                "dt_field": "2020-06-22T00:00:00+00:00",
                "fk_field_id": user1.id,
                "id": sm2.id,
                "int_field": 33,
            },
            "pgh_diff": None,
            "pgh_label": "snapshot",
            "pgh_model": "tests.SnapshotModelSnapshot",
            "pgh_obj_id": str(sm2.pk),
        },
    ]

    # Only aggregate across some event models
    assert list(
        pghistory.models.Events.objects.references(sm1)
        .across(test_models.CustomSnapshotModel)
        .order_by("pgh_model", "pgh_id")
        .values()
    ) == [
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 1,
            },
            "pgh_diff": None,
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 2,
            },
            "pgh_diff": {"int_field": [1, 2]},
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
        {
            **default,
            "pgh_data": {
                "fk_field2_id": None,
                "fk_field_id": user1.id,
                "id": sm1.id,
                "int_field": 3,
            },
            "pgh_diff": {"int_field": [2, 3]},
            "pgh_label": "custom_snapshot",
            "pgh_model": "tests.CustomSnapshotModel",
        },
    ]


@pytest.mark.django_db(transaction=True)
def test_aggregate_events_inheritance_models(django_assert_num_queries, mocker):
    """
    Check than aggregate event instances can be retrieved,
    for the whole tree of our inheritance test models

    ParentModel ⟵ ParentModelRelatedModel
        ↑
    ChildModel ⟵ ChildModelRelatedModel
        ↑
    SmallChildModel ⟵ SmallChildRelatedModel

    """
    user = ddf.G('auth.User')

    small_child_model_1 = ddf.G(
        test_models.SmallChildModel,
        parent_field="parent_field_1_initial",
        child_field="child_field_1_initial",
        small_child_field="small_child_field_1_initial",
    )

    small_child_model_2 = ddf.G(
        test_models.SmallChildModel,
        parent_field="parent_field_2_initial",
        child_field="child_field_2_initial",
        small_child_field="small_child_field_2_initial",
    )

    parent_model_related_1 = ddf.G(
        test_models.ParentModelRelatedModel,
        parent_model=small_child_model_1,
        parent_related_field="parent_model_related_1_initial",
    )

    parent_model_related_2 = ddf.G(
        test_models.ParentModelRelatedModel,
        parent_model=small_child_model_2,
        parent_related_field="parent_model_related_2_initial",
    )

    child_model_related_1 = ddf.G(
        test_models.ChildModelRelatedModel,
        child_model=small_child_model_1,
        child_related_field="child_model_related_1_initial",
    )

    child_model_related_2 = ddf.G(
        test_models.ChildModelRelatedModel,
        child_model=small_child_model_2,
        child_related_field="child_model_related_2_initial",
    )

    small_child_model_related_1 = ddf.G(
        test_models.SmallChildRelatedModel,
        small_child_model=small_child_model_1,
        small_child_related_field="small_child_model_related_1_initial",
    )

    small_child_model_related_2 = ddf.G(
        test_models.SmallChildRelatedModel,
        small_child_model=small_child_model_2,
        small_child_related_field="small_child_model_related_2_initial",
    )

    with pghistory.context(key='value1', user=user.id):
        small_child_model_1.parent_field = "parent_field_1_updated"
        small_child_model_1.child_field = "child_field_1_updated"
        small_child_model_1.small_child_field = "small_child_field_1_updated"
        small_child_model_1.save()

        small_child_model_2.parent_field = "parent_field_2_updated"
        small_child_model_2.child_field = "child_field_2_updated"
        small_child_model_2.small_child_field = "small_child_field_2_updated"
        small_child_model_2.save()

        parent_model_related_1.parent_related_field = "parent_model_related_1_updated"
        parent_model_related_1.save()

        parent_model_related_2.parent_related_field = "parent_model_related_2_updated"
        parent_model_related_2.save()

        child_model_related_1.child_related_field = "child_model_related_1_updated"
        child_model_related_1.save()

        child_model_related_2.child_related_field = "child_model_related_2_updated"
        child_model_related_2.save()

        small_child_model_related_1.small_child_related_field = (
            "small_child_model_related_1_updated"
        )
        small_child_model_related_1.save()

        small_child_model_related_2.small_child_related_field = (
            "small_child_model_related_2_updated"
        )
        small_child_model_related_2.save()

    # Retrieve the aggregated events
    aggregate_events = (
        pghistory.models.AggregateEvent.objects.target(small_child_model_1)
        .filter(pgh_context__isnull=False)
        .select_related('pgh_context')
    )

    # Make sure we can join against our proxy model without performance issues
    with django_assert_num_queries(1):
        # We do have 6 events because we made changes
        # to all of our models and their parents
        # (the updates done on small_child_model_1 count for 3 changes)
        assert len(aggregate_events) == 6

    # Check the retrieved event values
    with django_assert_num_queries(1):
        assert list(aggregate_events.order_by('pgh_diff').values('pgh_diff')) == [
            {'pgh_diff': {'child_field': ['child_field_1_initial', 'child_field_1_updated']}},
            {
                'pgh_diff': {
                    'child_related_field': [
                        'child_model_related_1_initial',
                        'child_model_related_1_updated',
                    ]
                }
            },
            {'pgh_diff': {'parent_field': ['parent_field_1_initial', 'parent_field_1_updated']}},
            {
                'pgh_diff': {
                    'parent_related_field': [
                        'parent_model_related_1_initial',
                        'parent_model_related_1_updated',
                    ]
                }
            },
            {
                'pgh_diff': {
                    'small_child_field': [
                        'small_child_field_1_initial',
                        'small_child_field_1_updated',
                    ]
                }
            },
            {
                'pgh_diff': {
                    'small_child_related_field': [
                        'small_child_model_related_1_initial',
                        'small_child_model_related_1_updated',
                    ]
                }
            },
        ]


@pytest.mark.django_db
def test_custom_foreign_key_to_m2m_through():
    """
    Verify that we can set up history tracking models that
    foreign key to a M2M through (such as Django's User.groups.through).
    We exercise this test by running a mangement command that
    will perform model checks using Django's check framework
    """
    call_command("check")
