"""Core functionality and interface of pghistory"""
import copy
import re
import sys
import warnings

from django.apps import apps
from django.db import connection
from django.db import models
from django.db.models import sql
from django.db.models.fields.related import RelatedField
from django.db.models.sql import compiler
from django.utils.module_loading import import_string
import pgtrigger
from psycopg2.extensions import AsIs

from pghistory import config, constants, trigger, utils


_registered_events = {}


def _get_name_from_label(label):
    """Given a history event label, generate a trigger name"""
    if label:
        return re.sub("[^0-9a-zA-Z]+", "_", label)
    else:  # pragma: no cover
        return None


class Event:
    """For storing an event when a condition happens on a model

    Events that inherit this base class are assumed to be
    manually created by the user. Only a "label" for the event is
    required.

    Events that are automatically created in a Postgres trigger should
    inherit `DatabaseEvent`
    """

    label = None

    def __init__(self, label=None):
        self.label = label or self.label
        if not self.label:
            raise ValueError(f'{self.__class__.__name__} must have "label" attribute')

    def setup(self, event_model):
        """Set up the event for the particular event model"""
        pass


class DatabaseEvent(Event):
    """For tracking an event automatically based on database changes."""

    when = None
    condition = None
    operation = None
    snapshot = None

    def __init__(
        self,
        label=None,
        *,
        when=None,
        condition=None,
        operation=None,
        snapshot=None,
    ):
        super().__init__(label=label)

        self.when = when or self.when
        self.condition = condition or self.condition
        self.operation = operation or self.operation
        self.snapshot = snapshot or self.snapshot

    def setup(self, event_model):
        pgtrigger.register(
            trigger.Event(
                event_model=event_model,
                label=self.label,
                name=_get_name_from_label(self.label),
                snapshot=self.snapshot,
                when=self.when,
                operation=self.operation,
                condition=self.condition,
            )
        )(event_model.pgh_tracked_model)


class Snapshot(DatabaseEvent):
    """
    A special database event that tracks changes to fields.
    A snapshot event always fires for an insert and also fires
    for updates when any fields change.

    NOTE: Two triggers must be created since Insert triggers do
    not allow comparison against the OLD values. We could also
    place this in one trigger and do the condition in the plpgsql code.
    """

    def __init__(self, label=None):
        return super().__init__(label=label)

    def setup(self, event_model):

        insert_trigger = trigger.Event(
            event_model=event_model,
            label=self.label,
            name=_get_name_from_label(f"{self.label}_insert"),
            snapshot="NEW",
            when=pgtrigger.After,
            operation=pgtrigger.Insert,
        )

        condition = pgtrigger.Q()
        for field in event_model._meta.fields:
            if hasattr(event_model.pgh_tracked_model, field.name):
                condition |= pgtrigger.Q(
                    **{f"old__{field.name}__df": pgtrigger.F(f"new__{field.name}")}
                )

        update_trigger = trigger.Event(
            event_model=event_model,
            label=self.label,
            name=_get_name_from_label(f"{self.label}_update"),
            snapshot="NEW",
            when=pgtrigger.After,
            operation=pgtrigger.Update,
            condition=condition,
        )

        pgtrigger.register(insert_trigger, update_trigger)(event_model.pgh_tracked_model)


class PreconfiguredDatabaseEvent(DatabaseEvent):
    """
    A base database event that only takes a condition. Subclasses
    preconfigure the other parameters
    """

    def __init__(self, label=None, *, condition=None):
        return super().__init__(label=label, condition=condition)


class AfterInsertOrUpdate(PreconfiguredDatabaseEvent):
    """
    A database event that happens after insert/update
    """

    operation = pgtrigger.Insert | pgtrigger.Update
    snapshot = "NEW"


class AfterInsert(PreconfiguredDatabaseEvent):
    """For events that happen after a database insert"""

    operation = pgtrigger.Insert
    snapshot = "NEW"


class BeforeUpdate(PreconfiguredDatabaseEvent):
    """
    For events that happen before a database update. The OLD values of the row
    will be snapshot to the event model
    """

    operation = pgtrigger.Update
    snapshot = "OLD"


class AfterUpdate(PreconfiguredDatabaseEvent):
    """
    For events that happen after a database update. The NEW values of the row
    will be snapshot to the event model
    """

    operation = pgtrigger.Update
    snapshot = "NEW"


class BeforeDelete(PreconfiguredDatabaseEvent):
    """
    For events that happen before a database deletion.
    """

    operation = pgtrigger.Delete
    snapshot = "OLD"


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


def _generate_history_field(tracked_model, field):
    """
    When generating a history model from a tracked model, ensure the fields
    are set up properly so that related names and other information
    from the tracked model do not cause errors.
    """
    field = tracked_model._meta.get_field(field)

    if isinstance(field, models.AutoField):
        return models.IntegerField()
    elif isinstance(field, models.BigAutoField):  # pragma: no cover
        return models.BigIntegerField()

    # The "swappable" field causes issues during deconstruct()
    # since it tries to load models. Patch it and set it back to the original
    # value later
    field = copy.deepcopy(field)
    swappable = getattr(field, "swappable", constants.unset)
    field.swappable = False
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

    field = cls(*args, **kwargs)

    if swappable is not constants.unset:
        field.swappable = swappable

    return field


def _generate_related_name(base_model, fields):
    """
    Generates a related name to the tracking model based on the base
    model and traked fields
    """
    related_name = base_model._meta.object_name.lower()
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


def _get_obj_field(*, obj_field, tracked_model, obj_fk, related_name, base_model, fields):
    if obj_fk is not constants.unset:
        warnings.warn(
            "The django-pghistory 'obj_fk' argument is deprecated. Use 'obj_field' instead.",
            DeprecationWarning,
        )
        return obj_fk
    elif obj_field is None:  # pragma: no cover
        return None
    elif obj_field is constants.unset:
        obj_field = config.obj_field()

        if related_name is not None:
            warnings.warn(
                "The django-pghistory 'related_name' argument is deprecated. Use the"
                " 'related_name' option of 'obj_field' instead.",
                DeprecationWarning,
            )

        obj_field._kwargs["related_name"] = related_name or _generate_related_name(
            base_model, fields
        )

    if isinstance(obj_field, config.ObjForeignKey):
        return models.ForeignKey(tracked_model, **obj_field.kwargs)
    else:  # pragma: no cover
        raise TypeError("obj_field must be of type pghistory.ObjForeignKey.")


def _get_context_field(*, context_field, context_fk):
    if context_fk is not constants.unset:
        warnings.warn(
            "The django-pghistory 'context_fk' argument is deprecated. Use "
            "'context_field' instead.",
            DeprecationWarning,
        )
        return context_fk
    elif context_field is None:  # pragma: no cover
        return None
    elif context_field is constants.unset:
        context_field = config.context_field()

    if isinstance(context_field, config.ContextForeignKey):
        return models.ForeignKey("pghistory.Context", **context_field.kwargs)
    elif isinstance(context_field, config.ContextJSONField):
        return models.JSONField(**context_field.kwargs)
    else:  # pragma: no cover
        raise TypeError(
            "context_field must be of type pghistory.ContextForeignKey"
            " or pghistory.ContextJSONField."
        )


def _get_context_id_field(*, context_id_field):
    if context_id_field is None:
        return None
    elif context_id_field is constants.unset:  # pragma: no branch
        context_id_field = config.context_id_field()

    if isinstance(context_id_field, config.ContextUUIDField):
        return models.UUIDField(**context_id_field.kwargs)
    else:  # pragma: no cover
        raise TypeError("context_id_field must be of type pghistory.ContextUUIDField.")


def create_event_model(
    tracked_model,
    *events,
    fields=None,
    exclude=None,
    obj_fk=constants.unset,
    context_fk=constants.unset,
    obj_field=constants.unset,
    context_field=constants.unset,
    context_id_field=constants.unset,
    related_name=None,
    name=None,
    model_name=None,
    app_label=None,
    base_model=None,
    attrs=None,
    meta=None,
    abstract=True,
):
    """
    Obtain a base event model.

    Instead of using `pghistory.track`, which dynamically generates an event
    model, one can instead construct a event model themselves, which
    will also set up event tracking for the tracked model.

    Usage:

        class MyEventModel(create_event_model(
            TrackedModel,
            pghistory.AfterInsert('model_create'),
        )):
            # Add custom indices or change default field declarations...

    Args:
        tracked_model (models.Model): The model that is being tracked.
        *events (List[`Event`]): The events to track. When using any event that
            inherits `pghistory.DatabaseEvent`, such as
            `pghistory.AfterInsert`, a Postgres trigger will be installed that
            automatically tracks the event with a generated event model. Events
            that do not inherit `pghistory.DatabaseEvent` are assumed to be
            manually tracked by the user.
        fields (List[str], default=None): The list of fields to snapshot
            when the event takes place. When no fields are provided, the entire
            model is snapshot when the event happens. Note that snapshotting
            of the OLD or NEW row is configured by the ``snapshot``
            attribute of the `DatabaseEvent` object. Manual events must specify
            these fields during manual creation.
        exclude (List[str], default=None): Instead of providing a list
            of fields to snapshot, a user can instead provide a list of fields
            to not snapshot.
        obj_field (pghistory.ObjForeignKey, default=unset): The foreign key field
            configuration that references the tracked object. Defaults to an
            unconstrained non-nullable foreign key. Use ``None`` to create a event model
            with no reference to the tracked object.
        context_field (Union[pghistory.ContextForeignKey, pghistory.ContextJSONField], default=unset):
            The context field configuration. Defaults to a nullable unconstrained foreign key.
            Use ``None`` to avoid attaching historical context altogether.
        context_id_field (pghistory.ContextUUIDField, default=unset): The context ID field
            configuration when using a ContextJSONField for the context_field. When using
            a denormalized context field, the ID field is used to track the UUID of the
            context. Use ``None`` to avoid using this field for denormalized context.
        model_name (str, default=None): Use a custom model name
            when the event model is generated. Otherwise a default
            name based on the tracked model and fields will be created.
        app_label (str, default=None): The app_label for the generated
            event model. Defaults to the app_label of the tracked model. Note,
            when tracking a Django model (User) or a model of a third-party
            app, one must manually specify the app_label of an internal app to
            use so that migrations work properly.
        base_model (models.Model, default=pghistory.Event): The base model for the event
            model. Must inherit pghistory.Event.
        attrs (dict, default=None): Additional attributes to add to the event model
        meta (dict, default=None): Additional attributes to add to the Meta class of the
            event model.
        abstract (bool, default=True): ``True`` if the generated model should
            be an abstract model.
    """  # noqa
    event_model = import_string("pghistory.models.Event")
    base_model = base_model or config.base_model()
    assert issubclass(base_model, event_model)

    obj_field = _get_obj_field(
        obj_field=obj_field,
        tracked_model=tracked_model,
        obj_fk=obj_fk,
        related_name=related_name,
        base_model=base_model,
        fields=fields,
    )
    context_field = _get_context_field(context_field=context_field, context_fk=context_fk)
    context_id_field = _get_context_id_field(context_id_field=context_id_field)

    if name is not None:  # pragma: no cover
        warnings.warn(
            "The 'name' argument for pghistory.create_event_model is"
            " deprecated. Use the 'model_name' argument",
            DeprecationWarning,
        )
        model_name = name

    model_name = model_name or _generate_event_model_name(base_model, tracked_model, fields)
    app_label = app_label or tracked_model._meta.app_label
    _validate_event_model_path(app_label=app_label, model_name=model_name, abstract=abstract)
    app = apps.app_configs[app_label]
    models_module = app.module.__name__ + ".models"

    attrs = attrs or {}
    attrs.update({"pgh_events": events})
    meta = meta or {}
    exclude = exclude or []
    fields = fields or [f.name for f in tracked_model._meta.fields if f.name not in exclude]

    class_attrs = {
        "__module__": models_module,
        "Meta": type("Meta", (), {"abstract": abstract, "app_label": app_label, **meta}),
        "pgh_tracked_model": tracked_model,
        **{field: _generate_history_field(tracked_model, field) for field in fields},
        **attrs,
    }

    if isinstance(context_field, models.JSONField) and context_id_field:
        class_attrs["pgh_context_id"] = context_id_field

    if context_field:
        class_attrs["pgh_context"] = context_field

    if obj_field:
        class_attrs["pgh_obj"] = obj_field

    event_model = type(model_name, (base_model,), class_attrs)
    if not abstract:
        setattr(sys.modules[models_module], model_name, event_model)

    return event_model


def get_event_model(*args, **kwargs):
    warnings.warn(
        "The django-pghistory 'get_event_model' function is deprecated. Use"
        " 'create_event_model' instead.",
        DeprecationWarning,
    )
    return create_event(*args, **kwargs)


def ProxyField(proxy, field):
    """
    Proxies a JSON field from a model and adds it as a field in the queryset.

    Args:
        proxy (str): The value to proxy, e.g. "user__email"
        field (Type[django.models.Field]): The field that will be used to cast
            the resulting value

    """
    if not isinstance(field, models.Field):
        raise TypeError(f'"{field} is not a Django model Field instace')

    field.pgh_proxy = proxy
    return field


def track(
    *events,
    fields=None,
    exclude=None,
    obj_fk=constants.unset,
    context_fk=constants.unset,
    obj_field=constants.unset,
    context_field=constants.unset,
    context_id_field=constants.unset,
    related_name=None,
    model_name=None,
    app_label=None,
    base_model=None,
    attrs=None,
    meta=None,
):
    """
    A decorator for tracking events for a model.

    When using this decorator, an event model is dynamically generated
    that snapshots the entire model or supplied fields of the model
    based on the ``events`` supplied. The snapshot is accompanied with
    the label that identifies the event.

    Args:
        *events (List[`Event`]): The events to track. When using any event that
            inherits `pghistory.DatabaseEvent`, such as
            `pghistory.AfterInsert`, a Postgres trigger will be installed that
            automatically tracks the event with a generated event model. Events
            that do not inherit `pghistory.DatabaseEvent` are assumed to be
            manually tracked by the user.
        fields (List[str], default=None): The list of fields to snapshot
            when the event takes place. When no fields are provided, the entire
            model is snapshot when the event happens. Note that snapshotting
            of the OLD or NEW row is configured by the ``snapshot``
            attribute of the `DatabaseEvent` object. Manual events must specify
            these fields during manual creation.
        exclude (List[str], default=None): Instead of providing a list
            of fields to snapshot, a user can instead provide a list of fields
            to not snapshot.
        obj_field (pghistory.ObjForeignKey, default=unset): The foreign key field
            configuration that references the tracked object. Defaults to an
            unconstrained non-nullable foreign key. Use ``None`` to create a event model
            with no reference to the tracked object.
        context_field (Union[pghistory.ContextForeignKey, pghistory.ContextJSONField], default=unset):
            The context field configuration. Defaults to a nullable unconstrained foreign key.
            Use ``None`` to avoid attaching historical context altogether.
        context_id_field (pghistory.ContextUUIDField, default=unset): The context ID field
            configuration when using a ContextJSONField for the context_field. When using
            a denormalized context field, the ID field is used to track the UUID of the
            context. Use ``None`` to avoid using this field for denormalized context.
        model_name (str, default=None): Use a custom model name
            when the event model is generated. Otherwise a default
            name based on the tracked model and fields will be created.
        app_label (str, default=None): The app_label for the generated
            event model. Defaults to the app_label of the tracked model. Note,
            when tracking a Django model (User) or a model of a third-party
            app, one must manually specify the app_label of an internal app to
            use so that migrations work properly.
        base_model (models.Model, default=pghistory.Event): The base model for the event
            model. Must inherit pghistory.Event.
        attrs (dict, default=None): Additional attributes to add to the event model
        meta (dict, default=None): Additional attributes to add to the Meta class of the
            event model.
    """  # noqa

    def _model_wrapper(model_class):
        event_model = create_event_model(
            model_class,
            *events,
            fields=fields,
            exclude=exclude,
            obj_fk=obj_fk,
            context_fk=context_fk,
            obj_field=obj_field,
            context_field=context_field,
            context_id_field=context_id_field,
            model_name=model_name,
            related_name=related_name,
            app_label=app_label,
            abstract=False,
            base_model=base_model,
            attrs=attrs,
            meta=meta,
        )
        for event in events:
            _registered_events[(model_class, event.label)] = event_model

        return model_class

    return _model_wrapper


class _InsertEventCompiler(compiler.SQLInsertCompiler):
    def as_sql(self, *args, **kwargs):
        ret = super().as_sql(*args, **kwargs)
        assert len(ret) == 1
        params = [
            param if field.name != "pgh_context" else AsIs("_pgh_attach_context()")
            for field, param in zip(self.query.fields, ret[0][1])
        ]
        return [(ret[0][0], params)]


def create_event(obj, *, label, using="default"):
    """Manually create a event for an object.

    Events are automatically linked with any context being tracked
    via `pghistory.context`.

    Args:
        obj (models.Model): An instance of a model.
        label (str): The event label.

    Raises:
        ValueError: If the event label has not been registered for the model.

    Returns:
        models.Model: The created event model.
    """
    # Verify that the provided event is registered to the object model
    if (obj.__class__, label) not in _registered_events:
        raise ValueError(
            f'"{label}" is not a registered event for model' f" {obj._meta.object_name}."
        )

    event_model = _registered_events[(obj.__class__, label)]
    event_model_kwargs = {
        "pgh_label": label,
        **{
            field.attname: getattr(obj, field.attname)
            for field in event_model._meta.fields
            if not field.name.startswith("pgh_")
        },
    }
    if hasattr(event_model, "pgh_obj"):
        event_model_kwargs["pgh_obj"] = obj

    event_obj = event_model(**event_model_kwargs)

    # The event model is inserted manually with a custom SQL compiler
    # that attaches the context using the _pgh_attach_context
    # stored procedure. Django does not allow one to use F()
    # objects to reference stored procedures, so we have to
    # inject it with a custom SQL compiler here.
    query = sql.InsertQuery(event_model)
    query.insert_values(
        [field for field in event_model._meta.fields if not isinstance(field, models.AutoField)],
        [event_obj],
    )

    vals = _InsertEventCompiler(query, connection, using="default").execute_sql(
        event_model._meta.fields
    )

    # Django <= 2.2 does not support returning fields from a bulk create,
    # which requires us to fetch fields again to populate the context
    # NOTE (@wesleykendall): We will eventually test multiple Django versions
    if isinstance(vals, int):  # pragma: no cover
        return event_model.objects.get(pgh_id=vals)
    else:
        # Django >= 3.1 returns the values as a list of one element
        if isinstance(vals, list) and len(vals) == 1:  # pragma: no branch
            vals = vals[0]

        for field, val in zip(event_model._meta.fields, vals):
            setattr(event_obj, field.attname, val)

        return event_obj


def event_models(
    models=None, references_model=None, tracks_model=None, include_missing_pgh_obj=False
):
    """
    Retrieve and filter all events models.

    Args:
        models (List[Model], default=None): The starting list of event models.
        references_model (Model, default=None): Filter by event models that reference this model.
        tracks_model (Model, default=None): Filter by models that directly track this model
            and have pgh_obj fields
        including_missing_pgh_obj (bool, default=False): Return tracked models even if the pgh_obj
            field is not available.
    """
    from pghistory.models import Event, BaseAggregateEvent  # noqa

    models = models or [
        model
        for model in apps.get_models()
        if issubclass(model, Event)
        and not issubclass(model, BaseAggregateEvent)
        and not model._meta.abstract
        and not model._meta.proxy
        and model._meta.managed
    ]

    if references_model:
        models = [
            model
            for model in models
            if any(utils.related_model(field) == references_model for field in model._meta.fields)
        ]

    if tracks_model and not include_missing_pgh_obj:
        models = [
            model
            for model in models
            if "pgh_obj" in (f.name for f in model._meta.fields)
            and utils.related_model(model._meta.get_field("pgh_obj")) == tracks_model
        ]
    elif tracks_model and include_missing_pgh_obj:
        models = [
            model
            for model in models
            if model.pgh_tracked_model._meta.concrete_model == tracks_model
        ]

    return models
