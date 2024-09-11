"""Core functionality and interface of pghistory"""

import copy
import re
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union

import pgtrigger
import pgtrigger.core
from django.apps import apps
from django.db import connections, models
from django.db.models import sql
from django.db.models.fields.related import RelatedField
from django.db.models.sql import compiler
from django.utils.module_loading import import_string
from django.utils.text import slugify

from pghistory import config, constants, runtime, trigger, utils

if TYPE_CHECKING:
    from pghistory import ContextForeignKey, ContextJSONField, ContextUUIDField, ObjForeignKey

if utils.psycopg_maj_version == 2:
    from psycopg2.extensions import AsIs as Literal
elif utils.psycopg_maj_version == 3:
    import psycopg.adapt

    class Literal:
        def __init__(self, val):
            self.val = val

    class LiteralDumper(psycopg.adapt.Dumper):
        def dump(self, obj):
            return obj.val.encode("utf-8")

        def quote(self, obj):
            return self.dump(obj)

else:
    raise AssertionError


_registered_trackers = {}


class Tracker:
    """For tracking an event when a condition happens on a model."""

    label: Optional[str] = None

    def __init__(self, label=None):
        self.label = label or self.label

        if not self.label:  # pragma: no cover
            raise ValueError("Must supply label attribute to event")

    def setup(self, event_model):
        """Set up the tracker for the event model"""
        pass

    def pghistory_setup(self, event_model):
        """Registers the tracker for the event model and calls user-defined setup"""
        tracked_model = event_model.pgh_tracked_model

        if _registered_trackers.get((tracked_model, self.label), event_model) != event_model:
            raise ValueError(
                f'Tracker with label "{self.label}" already exists for a different'
                f' event model of "{tracked_model._meta.label}". Supply a'
                " different label as the first argument to the tracker."
            )

        _registered_trackers[(tracked_model, self.label)] = event_model

        self.setup(event_model)


class ManualEvent(Tracker):
    """For manually tracking an event."""


class RowEvent(Tracker):
    """For tracking an event automatically based on row-level changes."""

    condition: Union[Optional[pgtrigger.Condition], constants.Unset] = constants.UNSET
    operation: Optional[pgtrigger.Operation] = None
    row: Optional[str] = None
    trigger_name: Optional[str] = None

    def __init__(
        self,
        label: Optional[str] = None,
        *,
        condition: Union[Optional[pgtrigger.Condition], constants.Unset] = constants.UNSET,
        operation: Optional[pgtrigger.Operation] = None,
        row: Optional[str] = None,
        trigger_name: Optional[str] = None,
    ):
        super().__init__(label=label)

        self.condition = condition or self.condition
        self.operation = operation or self.operation
        self.row = row or self.row
        self.trigger_name = trigger_name or self.trigger_name or f"{self.label}_{self.operation}"

        if self.condition is constants.UNSET:
            self.condition = pgtrigger.AnyChange() if self.operation == pgtrigger.Update else None

        if self.row not in ("OLD", "NEW"):  # pragma: no cover
            raise ValueError("Row must be specified as pghistory.Old or pghistory.New")
        elif self.operation == pgtrigger.Insert and self.row == "OLD":  # pragma: no cover
            raise ValueError('There is no "OLD" row on insert events')
        elif self.operation == pgtrigger.Delete and self.row == "NEW":  # pragma: no cover
            raise ValueError('There is no "NEW" row on delete events')

        if not self.operation:  # pragma: no cover
            raise ValueError("Must provide operation to RowEvent")

    def add_event_trigger(self, event_model):
        pgtrigger.register(
            trigger.Event(
                event_model=event_model,
                label=self.label,
                name=self.trigger_name,
                row=self.row,
                operation=self.operation,
                condition=self.condition,
            )
        )(event_model.pgh_tracked_model)

    def setup(self, event_model):
        # If any _Change condition is used, modify the default fields to the tracked fields
        if isinstance(self.condition, pgtrigger.core._Change) and not self.condition.fields:
            self.condition = copy.deepcopy(self.condition)
            model_fields = {f.name for f in event_model.pgh_tracked_model._meta.fields}
            self.condition.fields = [
                field.name for field in event_model._meta.fields if field.name in model_fields
            ]

        self.add_event_trigger(event_model)


class InsertEvent(RowEvent):
    """Creates events based on inserts to a model

    The default label used is "insert".
    """

    label: Optional[str] = "insert"
    row: Optional[str] = "NEW"
    operation: Optional[pgtrigger.Operation] = pgtrigger.Insert


class UpdateEvent(RowEvent):
    """Creates events based on updates to a model.

    By default,

    - The label used is "update".
    - Attributes from the "new" row of the update are stored.
    - It only fires when fields of the event model are changed.

    All of this behavior can be overridden by supplying a label,
    a condition, or the row to snapshot.
    """

    label: Optional[str] = "update"
    row: Optional[str] = "NEW"
    operation: Optional[pgtrigger.Operation] = pgtrigger.Update


class DeleteEvent(RowEvent):
    """Creates events based on deletes to a model

    The default label used is "delete".
    """

    label: Optional[str] = "delete"
    row: Optional[str] = "OLD"
    operation: Optional[pgtrigger.Operation] = pgtrigger.Delete


def _pascalcase(string):
    """Convert string into pascal case."""

    string = re.sub(r"^[\-_\.]", "", str(string))
    if not string:  # pragma: no branch
        return string

    return string[0].upper() + re.sub(
        r"[\-_\.\s]([a-z])",
        lambda matched: matched.group(1).upper(),
        string[1:],
    )


def _generate_event_model_name(base_model, tracked_model, fields):
    """Generates a default history model name"""
    name = tracked_model._meta.object_name
    if fields:
        name += "_" + "_".join(fields)

    name += f"_{base_model._meta.object_name.lower()}"
    return _pascalcase(name)


def _get_field_construction(field):
    _, _, args, kwargs = field.deconstruct()

    if isinstance(field, models.ForeignKey):
        default = config.foreign_key_field()
    elif isinstance(field, RelatedField):  # pragma: no cover
        default = config.related_field()
    else:
        default = config.field()

    kwargs.update(default.kwargs)

    cls = field.__class__
    if isinstance(field, models.OneToOneField):
        cls = models.ForeignKey
    elif isinstance(field, models.FileField):
        kwargs.pop("primary_key", None)

    for field_class, exclude_kwargs in config.exclude_field_kwargs().items():
        if isinstance(field, field_class):
            for exclude_kwarg in exclude_kwargs:
                kwargs.pop(exclude_kwarg, None)

    return cls, args, kwargs


def _generate_history_field(tracked_model, field):
    """
    When generating a history model from a tracked model, ensure the fields
    are set up properly so that related names and other information
    from the tracked model do not cause errors.
    """
    field = tracked_model._meta.get_field(field)

    if isinstance(field, models.BigAutoField):
        return models.BigIntegerField()
    elif isinstance(field, models.AutoField):
        return models.IntegerField()
    elif not field.concrete:  # pragma: no cover
        # Django doesn't have any non-concrete fields that appear
        # in ._meta.fields, but packages like django-prices have
        # non-concrete fields
        return field

    # The "swappable" field causes issues during deconstruct()
    # since it tries to load models. Patch it and set it back to the original
    # value later
    field = copy.deepcopy(field)
    swappable = getattr(field, "swappable", constants.UNSET)
    field.swappable = False
    cls, args, kwargs = _get_field_construction(field)
    field = cls(*args, **kwargs)

    if swappable is not constants.UNSET:
        field.swappable = swappable

    return field


def _generate_related_name(base_model, fields):
    """
    Generates a related name to the tracking model based on the base
    model and traked fields
    """
    related_name = slugify(base_model._meta.verbose_name_plural).replace("-", "_")
    return "_".join(fields) + f"_{related_name}" if fields else related_name


def _validate_event_model_path(*, app_label, model_name, abstract):
    if app_label not in apps.app_configs:
        raise ValueError(f'App label "{app_label}" is invalid')

    app = apps.app_configs[app_label]
    models_module = app.module.__name__ + ".models"
    if not abstract and hasattr(sys.modules[models_module], model_name):
        raise ValueError(
            f"App {app_label} already has {model_name} model. You must"
            " explicitly declare an unused model name for the pghistory model."
        )
    elif models_module.startswith("django."):
        raise ValueError(
            "A history model cannot be generated under third party app"
            f' "{app_label}". You must explicitly pass an app label'
            " when configuring tracking."
        )


def _get_obj_field(*, obj_field, tracked_model, base_model, fields):
    if obj_field is None:  # pragma: no cover
        return None
    elif obj_field is constants.UNSET:
        obj_field = config.obj_field()
        if obj_field._kwargs.get("related_name", constants.DEFAULT) == constants.DEFAULT:
            obj_field._kwargs["related_name"] = _generate_related_name(base_model, fields)

    if isinstance(obj_field, config.ObjForeignKey):
        return models.ForeignKey(tracked_model, **obj_field.kwargs)
    else:  # pragma: no cover
        raise TypeError("obj_field must be of type pghistory.ObjForeignKey.")


def _get_context_field(context_field):
    if context_field is None:  # pragma: no cover
        return None
    elif context_field is constants.UNSET:
        context_field = config.context_field()

    if isinstance(context_field, config.ContextForeignKey):
        return models.ForeignKey("pghistory.Context", **context_field.kwargs)
    elif isinstance(context_field, config.ContextJSONField):
        return utils.JSONField(**context_field.kwargs)
    else:  # pragma: no cover
        raise TypeError(
            "context_field must be of type pghistory.ContextForeignKey"
            " or pghistory.ContextJSONField."
        )


def _get_context_id_field(context_id_field):
    if context_id_field is None:
        return None
    elif context_id_field is constants.UNSET:  # pragma: no branch
        context_id_field = config.context_id_field()

    if isinstance(context_id_field, config.ContextUUIDField):
        return models.UUIDField(**context_id_field.kwargs)
    else:  # pragma: no cover
        raise TypeError("context_id_field must be of type pghistory.ContextUUIDField.")


def _get_append_only(append_only):
    return config.append_only() if append_only is constants.UNSET else append_only


def create_event_model(
    tracked_model: Type[models.Model],
    *trackers: Tracker,
    fields: Union[List[str], None] = None,
    exclude: Union[List[str], None] = None,
    obj_field: Union["ObjForeignKey", constants.Unset] = constants.UNSET,
    context_field: Union[
        "ContextForeignKey", "ContextJSONField", constants.Unset
    ] = constants.UNSET,
    context_id_field: Union["ContextUUIDField", constants.Unset] = constants.UNSET,
    append_only: Union[bool, constants.Unset] = constants.UNSET,
    model_name: Union[str, None] = None,
    app_label: Union[str, None] = None,
    base_model: Optional[Type[models.Model]] = None,
    attrs: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    abstract: bool = True,
) -> Type[models.Model]:
    """
    Create an event model.

    Instead of using [pghistory.track][], which dynamically generates an event
    model, one can instead construct a event model themselves, which
    will also set up event tracking for the tracked model.

    Args:
        tracked_model: The model that is being tracked.
        *trackers: The event trackers. When using any tracker that inherits
            [pghistory.RowEvent][], such as [pghistory.InsertEvent][], a
            Postgres trigger will be installed that automatically stores the event
            into the generated event model. Trackers that do not inherit
            [pghistory.RowEvent][] must be manually created. If no events are
            supplied, defaults to `pghistory.InsertEvent` and `pghistory.UpdateEvent`.
        fields: The list of fields to store when the event takes place. When
            no fields are provided, all fields are stored. Note that storing
            the OLD or NEW row is configured by the `row` attribute of the `RowEvent` object.
            Manual events must specify these fields during manual creation.
        exclude: Instead of providing a list of fields to snapshot, a user can
            instead provide a list of fields to not snapshot.
        obj_field: The foreign key field configuration that references the tracked object.
            Defaults to an unconstrained non-nullable foreign key. Use `None` to create a
            event model with no reference to the tracked object.
        context_field: The context field configuration. Defaults to a nullable
            unconstrained foreign key. Use `None` to avoid attaching historical context altogether.
        context_id_field: The context ID field configuration when using a ContextJSONField
            for the context_field. When using a denormalized context field, the ID
            field is used to track the UUID of the context. Use `None` to avoid using this
            field for denormalized context.
        append_only: True if the event model is protected against updates and deletes.
        model_name: Use a custom model name when the event model is generated. Otherwise
            a default name based on the tracked model and fields will be created.
        app_label: The app_label for the generated event model. Defaults to the app_label
            of the tracked model. Note, when tracking a Django model (User) or a model
            of a third-party app, one must manually specify the app_label of an internal
            app to use so that migrations work properly.
        base_model: The base model for the event model. Must inherit pghistory.models.Event.
        attrs: Additional attributes to add to the event model
        meta: Additional attributes to add to the Meta class of the event model.
        abstract: `True` if the generated model should be an abstract model.

    Returns:
        The event model class.

    Example:
        Create a custom event model:

            class MyEventModel(create_event_model(
                TrackedModel,
                pghistory.InsertEvent(),
            )):
                # Add custom indices or change default field declarations...
    """  # noqa
    if not trackers:
        trackers = config.default_trackers() or (InsertEvent(), UpdateEvent())

    event_model = import_string("pghistory.models.Event")
    base_model = base_model or config.base_model()
    assert issubclass(base_model, event_model)

    obj_field = _get_obj_field(
        obj_field=obj_field,
        tracked_model=tracked_model,
        base_model=base_model,
        fields=fields,
    )
    context_field = _get_context_field(context_field)
    context_id_field = _get_context_id_field(context_id_field)
    append_only = _get_append_only(append_only)

    model_name = model_name or _generate_event_model_name(base_model, tracked_model, fields)
    app_label = app_label or tracked_model._meta.app_label
    _validate_event_model_path(app_label=app_label, model_name=model_name, abstract=abstract)
    app = apps.app_configs[app_label]
    models_module = app.module.__name__ + ".models"

    attrs = attrs or {}
    attrs.update({"pgh_trackers": trackers})
    meta = meta or {}
    exclude = exclude or []
    all_fields = (tracked_model._meta.concrete_model or tracked_model)._meta.local_fields
    fields = (
        fields if fields is not None else [f.name for f in all_fields if f.name not in exclude]
    )

    if append_only:
        meta["triggers"] = [
            *meta.get("triggers", []),
            pgtrigger.Protect(name="append_only", operation=pgtrigger.Update | pgtrigger.Delete),
        ]

    class_attrs = {
        "__module__": models_module,
        "Meta": type("Meta", (), {"abstract": abstract, "app_label": app_label, **meta}),
        "pgh_tracked_model": tracked_model,
        **{field: _generate_history_field(tracked_model, field) for field in fields},
        **attrs,
    }

    if isinstance(context_field, utils.JSONField) and context_id_field:
        class_attrs["pgh_context_id"] = context_id_field

    if context_field:
        class_attrs["pgh_context"] = context_field

    if obj_field:
        class_attrs["pgh_obj"] = obj_field

    event_model = type(model_name, (base_model,), class_attrs)
    if not abstract:
        setattr(sys.modules[models_module], model_name, event_model)

    return event_model


def ProxyField(proxy: str, field: Type[models.Field]):
    """
    Proxies a JSON field from a model and adds it as a field in the queryset.

    Args:
        proxy: The value to proxy, e.g. "user__email"
        field: The field that will be used to cast the resulting value
    """
    if not isinstance(field, models.Field):  # pragma: no cover
        raise TypeError(f'"{field}" is not a Django model Field instace')

    field.pgh_proxy = proxy
    return field


def track(
    *trackers: Tracker,
    fields: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    obj_field: Union[Optional["ObjForeignKey"], constants.Unset] = constants.UNSET,
    context_field: Union[
        "ContextForeignKey", "ContextJSONField", constants.Unset
    ] = constants.UNSET,
    context_id_field: Union["ContextUUIDField", constants.Unset] = constants.UNSET,
    append_only: Union[bool, constants.Unset] = constants.UNSET,
    model_name: Optional[str] = None,
    app_label: Optional[str] = None,
    base_model: Optional[Type[models.Model]] = None,
    attrs: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    """
    A decorator for tracking events for a model.

    When using this decorator, an event model is dynamically generated
    that snapshots the entire model or supplied fields of the model
    based on the `events` supplied. The snapshot is accompanied with
    the label that identifies the event.

    Args:
        *trackers: The event trackers. When using any tracker that inherits
            [pghistory.RowEvent][], such as [pghistory.InsertEvent][], a
            Postgres trigger will be installed that automatically stores the event
            into the generated event model. Trackers that do not inherit
            [pghistory.RowEvent][] must be manually created. If no events are
            supplied, defaults to `pghistory.InsertEvent` and `pghistory.UpdateEvent`.
        fields: The list of fields to snapshot when the event takes place. When no fields
            are provided, the entire model is snapshot when the event happens. Note that
            snapshotting of the OLD or NEW row is configured by the `snapshot`
            attribute of the `DatabaseTracker` object. Manual events must specify
            these fields during manual creation.
        exclude: Instead of providing a list of fields to snapshot, a user can instead
            provide a list of fields to not snapshot.
        obj_field: The foreign key field configuration that references the tracked object.
            Defaults to an unconstrained non-nullable foreign key. Use `None` to create a
            event model with no reference to the tracked object.
        context_field: The context field configuration. Defaults to a nullable unconstrained
            foreign key. Use `None` to avoid attaching historical context altogether.
        context_id_field: The context ID field configuration when using a ContextJSONField for
            the context_field. When using a denormalized context field, the ID field is used to
            track the UUID of the context. Use `None` to avoid using this field for denormalized
            context.
        append_only: True if the event model is protected against updates and deletes.
        model_name: Use a custom model name when the event model is generated. Otherwise a default
            name based on the tracked model and fields will be created.
        app_label: The app_label for the generated event model. Defaults to the app_label of the
            tracked model. Note, when tracking a Django model (User) or a model of a third-party
            app, one must manually specify the app_label of an internal app to
            use so that migrations work properly.
        base_model: The base model for the event model. Must inherit `pghistory.models.Event`.
        attrs: Additional attributes to add to the event model
        meta: Additional attributes to add to the Meta class of the event model.
    """

    def _model_wrapper(model_class):
        create_event_model(
            model_class,
            *trackers,
            fields=fields,
            exclude=exclude,
            obj_field=obj_field,
            context_field=context_field,
            context_id_field=context_id_field,
            append_only=append_only,
            model_name=model_name,
            app_label=app_label,
            abstract=False,
            base_model=base_model,
            attrs=attrs,
            meta=meta,
        )

        return model_class

    return _model_wrapper


class _InsertEventCompiler(compiler.SQLInsertCompiler):
    def as_sql(self, *args, **kwargs):
        ret = super().as_sql(*args, **kwargs)
        assert len(ret) == 1
        params = [
            param if field.name != "pgh_context" else Literal("_pgh_attach_context()")
            for field, param in zip(self.query.fields, ret[0][1])
        ]

        return [(ret[0][0], params)]


def create_event(obj: models.Model, *, label: str, using: str = "default") -> models.Model:
    """Manually create a event for an object.

    Events are automatically linked with any context being tracked
    via [pghistory.context][].

    Args:
        obj: An instance of a model.
        label: The event label.
        using: The database

    Raises:
        ValueError: If the event label has not been registered for the model.

    Returns:
        The created event model object
    """
    # Verify that the provided label is tracked
    if (obj.__class__, label) not in _registered_trackers:
        raise ValueError(
            f'"{label}" is not a registered tracker label for model {obj._meta.object_name}.'
        )

    event_model = _registered_trackers[(obj.__class__, label)]
    tracked_model_fields = {field.attname for field in obj._meta.fields}
    event_model_kwargs = {
        "pgh_label": label,
        **{
            field.attname: getattr(obj, field.attname)
            for field in event_model._meta.fields
            if not field.name.startswith("pgh_") and field.attname in tracked_model_fields
        },
    }
    if hasattr(event_model, "pgh_obj"):
        event_model_kwargs["pgh_obj"] = obj

    if hasattr(event_model, "pgh_context") and isinstance(
        event_model.pgh_context.field, utils.JSONField
    ):
        if hasattr(runtime._tracker, "value"):
            event_model_kwargs["pgh_context"] = runtime._tracker.value.metadata

            if hasattr(event_model, "pgh_context_id"):
                event_model_kwargs["pgh_context_id"] = runtime._tracker.value.id

        return event_model.objects.create(**event_model_kwargs)
    else:
        event_obj = event_model(**event_model_kwargs)

        # The event model is inserted manually with a custom SQL compiler
        # that attaches the context using the _pgh_attach_context
        # stored procedure. Django does not allow one to use F()
        # objects to reference stored procedures, so we have to
        # inject it with a custom SQL compiler here.
        query = sql.InsertQuery(event_model)
        query.insert_values(
            [
                field
                for field in event_model._meta.fields
                if not isinstance(field, models.AutoField)
            ],
            [event_obj],
        )

        if utils.psycopg_maj_version == 3:
            connections[using].connection.adapters.register_dumper(Literal, LiteralDumper)

        vals = _InsertEventCompiler(query, connections[using], using=using).execute_sql(
            event_model._meta.fields
        )

        # Django >= 3.1 returns the values as a list of one element
        if isinstance(vals, list) and len(vals) == 1:  # pragma: no branch
            vals = vals[0]

        for field, val in zip(event_model._meta.fields, vals):
            setattr(event_obj, field.attname, val)

        return event_obj


def event_models(
    models: Optional[List[Type[models.Model]]] = None,
    references_model: Optional[Type[models.Model]] = None,
    tracks_model: Optional[Type[models.Model]] = None,
    include_missing_pgh_obj: bool = False,
) -> List[Type[models.Model]]:
    """
    Retrieve and filter all events models.

    Args:
        models: The starting list of event models.
        references_model: Filter by event models that reference this model.
        tracks_model: Filter by models that directly track this model and have pgh_obj fields
        include_missing_pgh_obj: Return tracked models even if the pgh_obj field is not
            available.

    Returns:
        The list of event models
    """
    from pghistory.models import Event  # noqa

    models = models or [
        model
        for model in apps.get_models()
        if issubclass(model, Event)
        and not model._meta.abstract
        and not model._meta.proxy
        and model._meta.managed
    ]

    if references_model:
        if references_model._meta.proxy:  # pragma: no cover
            references_model = references_model._meta.concrete_model

        models = [
            model
            for model in models
            if any(utils.related_model(field) == references_model for field in model._meta.fields)
        ]

    if tracks_model:
        if tracks_model._meta.proxy:  # pragma: no cover
            tracks_model = tracks_model._meta.concrete_model

        if not include_missing_pgh_obj:
            models = [
                model
                for model in models
                if "pgh_obj" in (f.name for f in model._meta.fields)
                and utils.related_model(model._meta.get_field("pgh_obj")) == tracks_model
            ]
        else:
            models = [
                model
                for model in models
                if model.pgh_tracked_model._meta.concrete_model == tracks_model
            ]

    return models
