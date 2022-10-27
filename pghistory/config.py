"""Core way to access configuration"""
from django.apps import apps
from django.conf import settings
from django.db import models
from django.utils.module_loading import import_string

from pghistory import constants


def middleware_methods():
    """
    Methods tracked by the pghistory middleware
    """
    return getattr(
        settings, "PGHISTORY_MIDDLEWARE_METHODS", ("GET", "POST", "PUT", "PATCH", "DELETE")
    )


def json_encoder():
    """The JSON encoder when tracking context"""
    encoder = getattr(
        settings, "PGHISTORY_JSON_ENCODER", "django.core.serializers.json.DjangoJSONEncoder"
    )

    if isinstance(encoder, str):  # pragma: no branch
        encoder = import_string(encoder)

    return encoder


def base_model():
    """The base model for event models"""
    event_model = import_string("pghistory.models.Event")
    base_model = getattr(settings, "PGHISTORY_BASE_MODEL", event_model)

    if isinstance(base_model, str):  # pragma: no cover
        base_model = import_string(base_model)

    assert issubclass(base_model, event_model)
    return base_model


def field():
    """The default configuration for all fields in event models"""
    field = getattr(settings, "PGHISTORY_FIELD", Field())
    assert isinstance(field, Field)
    return field


def related_field():
    """The default configuration for related fields in event models"""
    related_field = getattr(settings, "PGHISTORY_RELATED_FIELD", RelatedField())
    assert isinstance(related_field, RelatedField)
    return related_field


def foreign_key_field():
    """The default configuration for foreign keys in event models"""
    foreign_key_field = getattr(settings, "PGHISTORY_FOREIGN_KEY_FIELD", ForeignKey())
    assert isinstance(foreign_key_field, ForeignKey)
    return foreign_key_field


def context_field():
    """The default field config to use for context in event models"""

    # Note: We will be changing the default context field to have on_delete=PROTECT
    # in version 3.
    context_field = getattr(settings, "PGHISTORY_CONTEXT_FIELD", ContextForeignKey())
    assert isinstance(context_field, (ContextForeignKey, ContextJSONField))
    return context_field


def context_id_field():
    """
    The default field config to use for context ID in event models when context is denormalized
    """

    context_id_field = getattr(settings, "PGHISTORY_CONTEXT_ID_FIELD", ContextUUIDField())
    assert isinstance(context_id_field, ContextUUIDField)
    return context_id_field


def obj_field():
    """The default field config to use for object references in event models"""

    obj_field = getattr(settings, "PGHISTORY_OBJ_FIELD", ObjForeignKey())
    assert isinstance(obj_field, ObjForeignKey)
    return obj_field


def exclude_field_kwargs():
    """
    Provide a mapping of field classes to a list of keyword args to ignore
    when instantiating the field on the event model.

    For example, a field may not allow ``unique`` as a keyword argument.
    If so, set ``settings.PGHISTORY_EXCLUDE_FIELD_KWARGS = {"field.FieldClass": ["unique"]}``
    """
    exclude_field_kwargs = getattr(settings, "PGHISTORY_EXCLUDE_FIELD_KWARGS", {})
    assert isinstance(exclude_field_kwargs, dict)
    for val in exclude_field_kwargs.values():
        assert isinstance(val, (list, tuple))

    # Import strings
    exclude_field_kwargs = {
        import_string(key) if isinstance(key, str) else key: value
        for key, value in exclude_field_kwargs.items()
    }

    return exclude_field_kwargs


def admin_ordering():
    """The default ordering for the events admin"""
    ordering = getattr(settings, "PGHISTORY_ADMIN_ORDERING", "-pgh_created_at") or []

    if not isinstance(ordering, (list, tuple)):
        ordering = [ordering]

    return ordering


def admin_model():
    """The default list display for the events admin"""
    return apps.get_model(getattr(settings, "PGHISTORY_ADMIN_MODEL", "pghistory.Events"))


def admin_queryset():
    """The default queryset for the events admin"""
    return getattr(
        settings, "PGHISTORY_ADMIN_QUERYSET", admin_model().objects.order_by(*admin_ordering())
    )


def admin_class():
    """The admin class to use for the events admin.

    Must be a subclass of pghistory.admin.EventsAdmin"""

    events_admin = import_string("pghistory.admin.EventsAdmin")
    admin_class = getattr(settings, "PGHISTORY_ADMIN_CLASS", events_admin)

    if isinstance(admin_class, str):  # pragma: no cover
        admin_class = import_string(admin_class)

    assert issubclass(admin_class, events_admin)

    return admin_class


def admin_all_events():
    """True if all events should be shown in the admin when there are no filters"""
    return getattr(settings, "PGHISTORY_ADMIN_ALL_EVENTS", True)


def admin_list_display():
    """The default list display for the events admin"""
    defaults = ["pgh_created_at", "pgh_operation", "pgh_obj_model", "pgh_obj_id", "pgh_diff"]

    if admin_queryset().model._meta.label == "pghistory.MiddlewareEvents":
        defaults.extend(["user", "url"])

    return getattr(settings, "PGHISTORY_ADMIN_LIST_DISPLAY", defaults)


def _get_kwargs(vals):
    return {
        key: val
        for key, val in vals.items()
        if key not in ("self", "kwargs", "__class__") and val is not constants.UNSET
    }


class Field:
    """Configuration for fields.

    Provides these default parameters:

    * **primary_key** (default=False)
    * **unique** (default=False)
    * **blank**
    * **null**
    * **db_index** (default=False)
    * **editable**
    * **unique_for_date** (default=None)
    * **unique_for_month** (default=None)
    * **unique_for_year** (default=None)

    The default values for the above parameters ensure that
    event models don't have unnecessary uniqueness constraints
    carried over from the tracked model.
    """

    def __init__(
        self,
        *,
        primary_key=constants.UNSET,
        unique=constants.UNSET,
        blank=constants.UNSET,
        null=constants.UNSET,
        db_index=constants.UNSET,
        editable=constants.UNSET,
        unique_for_date=constants.UNSET,
        unique_for_month=constants.UNSET,
        unique_for_year=constants.UNSET,
    ):
        self._kwargs = _get_kwargs(locals())
        self._finalized = False

    @property
    def kwargs(self):
        return {
            key: val
            for key, val in {**self.get_default_kwargs(), **self._kwargs}.items()
            if val is not constants.DEFAULT
        }

    def get_default_kwargs(self):
        return {
            **Field(
                primary_key=False,
                unique=False,
                db_index=False,
                unique_for_date=None,
                unique_for_month=None,
                unique_for_year=None,
            )._kwargs,
            **field()._kwargs,
        }


class RelatedField(Field):
    """Configuration for related fields.

    The following parameters can be used to configure
    defaults for all related fields:

    * **related_name** (default="+")
    * **related_query_name** (default="+")

    By default, related names are stripped to avoid
    unnecessary clashes.

    Note that all arguments from `Field` can also be supplied.
    """

    def __init__(
        self,
        *,
        related_name=constants.UNSET,
        related_query_name=constants.UNSET,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._kwargs.update(_get_kwargs(locals()))

    def get_default_kwargs(self):
        return {
            **super().get_default_kwargs(),
            **RelatedField(related_name="+", related_query_name="+")._kwargs,
            **related_field()._kwargs,
        }


class ForeignKey(RelatedField):
    """Configuration for foreign keys.

    The following parameters can be used:

    * **on_delete** (default=models.DO_NOTHING)
    * **db_constraint** (default=False)

    Arguments for `RelatedField` and `Field` can also be supplied.
    Note that db_index is overridden to `True` for all foreign keys
    """

    def __init__(self, *, on_delete=constants.UNSET, db_constraint=constants.UNSET, **kwargs):
        super().__init__(**kwargs)
        self._kwargs.update(_get_kwargs(locals()))

    def get_default_kwargs(self):
        return {
            **super().get_default_kwargs(),
            **ForeignKey(on_delete=models.DO_NOTHING, db_index=True, db_constraint=False)._kwargs,
            **foreign_key_field()._kwargs,
        }


class ContextForeignKey(ForeignKey):
    """Configuration for the ``pgh_context`` field when a foreign key is used.

    Overrides null to ``True``.
    """

    def __init__(self, *, null=True, related_query_name=constants.DEFAULT, **kwargs):
        # Note: We will be changing the default context field to have on_delete=PROTECT
        # in version 3.
        super().__init__(null=null, related_query_name=related_query_name, **kwargs)
        self._kwargs.update(_get_kwargs(locals()))


class ContextJSONField(Field):
    """Configuration for the ``pgh_context`` field when denormalized context is used."""

    def __init__(self, *, null=True, **kwargs):
        super().__init__(null=null, **kwargs)
        self._kwargs.update(_get_kwargs(locals()))


class ContextUUIDField(Field):
    """Configuration for the ``pgh_context_id`` field when denormalized context is used."""

    def __init__(self, *, null=True, **kwargs):
        super().__init__(null=null, **kwargs)
        self._kwargs.update(_get_kwargs(locals()))


class ObjForeignKey(ForeignKey):
    """Configuration for the ``pgh_obj`` field"""

    def __init__(
        self, *, related_name=constants.DEFAULT, related_query_name=constants.DEFAULT, **kwargs
    ):
        # Note: We will be changing the default object field to nullable with on_delete=SET_NULL
        # in version 3. related_name will also default to "+"
        super().__init__(
            related_name=related_name, related_query_name=related_query_name, **kwargs
        )
        self._kwargs.update(_get_kwargs(locals()))
