from django.db import models

from pghistory import config, constants


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

    settings.PGHISTORY_FIELD = config.Field(db_index=constants.inherit, unique=True)
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
        related_query_name=constants.inherit, db_index=True
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

    assert config.RelatedField(unique_for_year=True, db_index=constants.inherit).kwargs == {
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": True,
        "related_name": "+",
    }

    # db_index wont take effect because it is overridden by PGHISTORY_RELATED_FIELD
    settings.PGHISTORY_FIELD = config.Field(
        db_index=False, primary_key=True, unique_for_year=constants.inherit
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
    settings.PGHISTORY_RELATED_FIELD = config.RelatedField(related_query_name=constants.inherit)

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

    assert config.ForeignKey(on_delete=constants.inherit, db_constraint=True).kwargs == {
        "db_index": True,
        "primary_key": False,
        "unique": False,
        "unique_for_date": None,
        "unique_for_month": None,
        "unique_for_year": None,
        "related_name": "+",
        "db_constraint": True,
    }
