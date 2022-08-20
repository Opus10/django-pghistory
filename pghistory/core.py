"""Core functionality and interface of pghistory"""
import re

from django.db import connection
from django.db import models
from django.db.models import sql
from django.db.models.sql import compiler
import pgtrigger
from psycopg2.extensions import AsIs

import pghistory.constants


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
            pghistory.trigger.Event(
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

        insert_trigger = pghistory.trigger.Event(
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

        update_trigger = pghistory.trigger.Event(
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


def get_event_model(
    model,
    *events,
    fields=None,
    exclude=None,
    obj_fk=pghistory.constants.unset,
    context_fk=pghistory.constants.unset,
    related_name=None,
    name=None,
    app_label=None,
    abstract=True,
):
    """
    Obtain a base event model.

    Instead of using `pghistory.track`, which dynamically generates an event
    model, one can instead construct a event model themselves, which
    will also set up event tracking for the original model.

    Usage:

        class MyEventModel(get_event_model(
            TrackedModel,
            pghistory.AfterInsert('model_create'),
        )):
            # Add custom indices or change default field declarations...

    Args:
        model (models.Model): The model that is being tracked.
        *events (List[`Event`]): See "events" help from
            `pghistory.track`.
        fields (List[str], default=None): See "fields" help from
            `pghistory.track`.
        exclude (List[str], default=None): See "exclude" help from
            `pghistory.track`.
        obj_fk (models.ForeignKey): See "obj_fk" help from
            `pghistory.track`.
        related_name (str, default=None): See "related_name" help from
            `pghistory.track`.
        name (str, default=None): See "model_name" help from
            `pghistory.track`.
        app_label (str, default=None): See "app_label" help
            from `pghistory.track`.
        abstract (bool, default=True): ``True`` if the generated model should
            be an abstract model.
    """
    # Avoid importing models in the core module since these functions
    # are imported at the top level of the package
    import pghistory.models

    event_model = pghistory.models.Event.factory(
        model,
        *events,
        fields=fields,
        exclude=exclude,
        obj_fk=obj_fk,
        context_fk=context_fk,
        related_name=related_name,
        name=name,
        app_label=app_label,
        abstract=abstract,
    )

    return event_model


def track(
    *events,
    fields=None,
    exclude=None,
    obj_fk=pghistory.constants.unset,
    context_fk=pghistory.constants.unset,
    related_name=None,
    model_name=None,
    app_label=None,
):
    """
    A decorator for tracking events for a mdoel.

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
        obj_fk (models.ForeignKey, default=unset): The foreign key field that
            references the eventged object. Defaults to a non-nullable foreign
            key that cascade deletes.  Use ``None`` to create a event model
            with no reference to the tracked object. See ``related_name``
            attribute for how the related_name is determined.
        context_fk (models.ForeignKey, default=unset): The foreign key to
            tracked context, if any. Use ``None`` to avoid attaching historical
            context altogether.
        related_name (str, default=None): The related name of the event
            model. If not provided, defaults to "event" if one is tracking
            changes to the entire model, otherwise defaults to a name based on
            the combination of fields.
        model_name (str, default=None): Use a custom model name
            when the event model is generated. Otherwise a default
            name based on the tracked model and fields will be created.
        app_label (str, default=None): The app_label for the generated
            event model. Defaults to the app_label of the tracked model. Note,
            when tracking a Django model (User) or a model of a third-party
            app, one must manually specify the app_label of an internal app to
            use so that migrations work properly.
    """

    def _model_wrapper(model_class):
        event_model = get_event_model(
            model_class,
            *events,
            fields=fields,
            exclude=exclude,
            obj_fk=obj_fk,
            context_fk=context_fk,
            name=model_name,
            related_name=related_name,
            app_label=app_label,
            abstract=False,
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
