from django.db import models

from pghistory import config, constants, core


def test_admin_ordering(settings):
    assert config.admin_ordering() == ["-pgh_created_at"]

    settings.PGHISTORY_ADMIN_ORDERING = ["hello", "world"]

    assert config.admin_ordering() == ["hello", "world"]


def test_admin_queryset(settings):
    settings.PGHISTORY_ADMIN_MODEL = "auth.User"
    settings.PGHISTORY_ADMIN_ORDERING = None

    assert config.admin_queryset().model._meta.label == "auth.User"


def test_admin_list_display(settings):
    settings.PGHISTORY_ADMIN_MODEL = "pghistory.MiddlewareEvents"

    assert config.admin_list_display() == [
        "pgh_created_at",
        "pgh_obj_model",
        "pgh_obj_id",
        "pgh_diff",
        "user",
        "url",
    ]


def test_field(settings):
    assert config.field().kwargs == {
        "db_index": False,
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
    }

    settings.PGHISTORY_FIELD = config.Field(db_index=constants.DEFAULT, unique=True)
    assert config.field().kwargs == {
        "primary_key": False,
        "unique": True,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
    }

    assert config.Field(unique_for_year=True, db_index=True).kwargs == {
        "db_index": True,
        "primary_key": False,
        "unique": True,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": True,
    }


def test_related_field(settings):
    assert config.related_field().kwargs == {
        "db_index": False,
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
        "related_name": "+",
        "related_query_name": "+",
    }

    settings.PGHISTORY_RELATED_FIELD = config.RelatedField(
        related_query_name=constants.DEFAULT, db_index=True
    )

    assert config.related_field().kwargs == {
        "db_index": True,
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
        "related_name": "+",
    }

    assert config.RelatedField(unique_for_year=True, db_index=constants.DEFAULT).kwargs == {
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": True,
        "related_name": "+",
    }

    # db_index wont take effect because it is overridden by PGHISTORY_RELATED_FIELD
    settings.PGHISTORY_FIELD = config.Field(
        db_index=False, primary_key=True, unique_for_year=constants.DEFAULT
    )

    assert config.RelatedField().kwargs == {
        "db_index": True,
        "primary_key": True,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "related_name": "+",
    }


def test_foreign_key_field(settings):
    assert config.foreign_key_field().kwargs == {
        "db_index": True,
        "db_constraint": False,
        "on_delete": models.DO_NOTHING,
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
        "related_name": "+",
        "related_query_name": "+",
    }

    settings.PGHISTORY_FIELD = config.Field(db_index=True)
    settings.PGHISTORY_RELATED_FIELD = config.RelatedField(related_query_name=constants.DEFAULT)

    assert config.foreign_key_field().kwargs == {
        "db_index": True,
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
        "related_name": "+",
        "db_constraint": False,
        "on_delete": models.DO_NOTHING,
    }

    assert config.ForeignKey(on_delete=constants.DEFAULT, db_constraint=True).kwargs == {
        "db_index": True,
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
        "related_name": "+",
        "db_constraint": True,
    }


def test_default_trackers(settings):
    assert config.default_trackers() is None

    settings.PGHISTORY_DEFAULT_TRACKERS = [
        core.InsertEvent(),
        core.UpdateEvent(),
        core.DeleteEvent(),
    ]

    for expected_tracker, tracker in zip(
        settings.PGHISTORY_DEFAULT_TRACKERS, config.default_trackers()
    ):
        # Trackers should be the same type, but different instances due to copying
        assert type(expected_tracker) is type(tracker)
        assert expected_tracker is not tracker
