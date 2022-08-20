import copy
import re
import sys
import uuid

import django
from django.apps import apps
from django.db import connection
from django.db import connections
from django.db import models
from django.db.models.fields.related import RelatedField
from django.db.models.sql import Query
from django.db.models.sql.compiler import SQLCompiler

import pghistory.constants
import pghistory.trigger

# Django>=3.1 changes the location of JSONField
if (django.VERSION[0] >= 3 and django.VERSION[1] >= 1) or django.VERSION[0] >= 4:
    from django.db.models import JSONField
else:
    from django.contrib.postgres.fields import JSONField


# Create a consistent load path for JSONField regardless of django
# version. This is just to prevent migration issues for people
# on different django versions
class PGHistoryJSONField(JSONField):
    pass


class Context(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = PGHistoryJSONField(default=dict)

    @classmethod
    def install_pgh_attach_context_func(cls):
        """
        Installs a custom store procedure for upserting context
        for historical events. The upsert is aware of when tracking is
        enabled in the app (i.e. using pghistory.context())

        This stored procedure is automatically installed in pghistory.apps
        after migration
        """
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE OR REPLACE FUNCTION _pgh_attach_context()
                RETURNS {cls._meta.db_table}.id%TYPE AS $$
                    DECLARE
                        _pgh_context_id UUID;
                        _pgh_context_metadata JSONB;
                    BEGIN
                        BEGIN
                            SELECT INTO _pgh_context_id
                                CURRENT_SETTING('pghistory.context_id');
                            SELECT INTO _pgh_context_metadata
                                CURRENT_SETTING('pghistory.context_metadata');
                            EXCEPTION WHEN OTHERS THEN
                        END;
                        IF _pgh_context_id IS NOT NULL AND _pgh_context_metadata IS NOT NULL THEN
                            INSERT INTO {cls._meta.db_table} (id, metadata, created_at, updated_at)
                                VALUES (_pgh_context_id, _pgh_context_metadata, NOW(), NOW())
                                ON CONFLICT (id) DO UPDATE
                                    SET metadata = EXCLUDED.metadata,
                                        updated_at = EXCLUDED.updated_at;
                            RETURN _pgh_context_id;
                        ELSE
                            RETURN NULL;
                        END IF;
                    END;
                $$ LANGUAGE plpgsql;
                """
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
    field = copy.deepcopy(tracked_model._meta.get_field(field))

    if isinstance(field, models.AutoField):
        field = models.IntegerField()
    elif isinstance(field, models.OneToOneField):
        field.__class__ = models.ForeignKey

    if isinstance(field, RelatedField):
        field.db_constraint = False
        field.remote_field.on_delete = models.DO_NOTHING
        field.remote_field.related_name = "+"
        field.remote_field.related_query_name = "+"
    else:
        field.db_index = False

    field.primary_key = False
    field._unique = False

    return field


def _generate_related_name(base_model, fields):
    """
    Generates a related name to the tracking model based on the base
    model and traked fields
    """
    related_name = base_model._meta.object_name.lower()
    return "_".join(fields) + f"_{related_name}" if fields else related_name


def _validate_event_model_path(*, app_label, name, abstract):
    if app_label not in apps.app_configs:
        raise ValueError(f'App label "{app_label}" is invalid')

    app = apps.app_configs[app_label]
    models_module = app.module.__name__ + ".models"
    if not abstract and hasattr(sys.modules[models_module], name):
        raise ValueError(
            f"App {app_label} already has {name} model. You must"
            " explicitly declare an unused model name for the pghistory model."
        )
    elif models_module.startswith("django."):
        raise ValueError(
            "A history model cannot be generated under third party app"
            f' "{app_label}". You must explicitly pass an app label'
            " when configuring tracking."
        )


def create_event_model(
    base_class,
    tracked_model,
    fields=None,
    exclude=None,
    obj_fk=pghistory.constants.unset,
    context_fk=pghistory.constants.unset,
    abstract=True,
    related_name=None,
    name=None,
    app_label=None,
    attrs=None,
    meta=None,
):
    """
    The primary factory function for dynamically creating a history
    model.

    Args:
        base_class (models.Model): The base class from which the created
            model will inherit
        tracked_model (models.Model): The model being tracked
        fields (List[str], default=None): The fields to track. If None,
            all fields on tracked_model are tracked.
        exclude (List[str], default=None): If no fields are provided, exclude
            these fields from tracking.
        obj_fk (models.ForeignKey, default=unset): For overriding the
            foreign key that references the tracked object. If unset, defaults
            to a non-nullable foreign key that cascades. The related name
            defaults to ``related_name`` if all fields are tracked. Otherwise
            defaults to a combintion of ``related_name`` and ``fields``. Use
            ``None`` to create a tracking model without a foreign key to
            the tracked model.
        context_fk (models.ForeignKey, default=unset): The foreign key to
            tracked context, if any. Use ``None`` to avoid attaching historical
            context altogether.
        abstract (bool, default=True): True if the created model should be
            abstract
        related_name (str): The primary way to identify the relation of
            the created model and the tracked model
        name (str, default=None): The name of the created model. If None,
            defaults to a combination of the ``related_name``,
            ``tracked_model``, and ``fields``.
        app_label (str, default=None): The app_label for the created model.
            Defaults to the app_label of ``tracked_model``. Note, when tracking
            a Django model (User) or a model of a third-party app, one must
            manually specify the app_label of an internal app to use for
            the tracking model.
        attrs (dict, default=None): Additional attributes to add to the created
            model.
        meta (dict, default=None): Additional options to add to the model
            Meta
    """
    related_name = related_name or _generate_related_name(base_class, fields)
    name = name or _generate_event_model_name(base_class, tracked_model, fields)
    app_label = app_label or tracked_model._meta.app_label
    _validate_event_model_path(app_label=app_label, name=name, abstract=abstract)
    app = apps.app_configs[app_label]
    models_module = app.module.__name__ + ".models"

    attrs = attrs or {}
    meta = meta or {}
    context_fk = (
        models.ForeignKey(
            Context,
            null=True,
            on_delete=models.DO_NOTHING,
            related_name="+",
            db_constraint=False,
        )
        if context_fk is pghistory.constants.unset
        else context_fk
    )

    obj_fk = (
        models.ForeignKey(
            tracked_model,
            null=False,
            on_delete=models.DO_NOTHING,
            db_constraint=False,
            related_name=related_name,
        )
        if obj_fk is pghistory.constants.unset
        else obj_fk
    )
    exclude = exclude or []
    fields = fields or [f.name for f in tracked_model._meta.fields if f.name not in exclude]

    class_attrs = {
        "__module__": models_module,
        "Meta": type("Meta", (), {"abstract": abstract, "app_label": app_label, **meta}),
        "pgh_tracked_model": tracked_model,
        **{field: _generate_history_field(tracked_model, field) for field in fields},
        **attrs,
    }

    if context_fk:
        class_attrs["pgh_context"] = context_fk

    if obj_fk:
        class_attrs["pgh_obj"] = obj_fk

    event_model = type(name, (base_class,), class_attrs)
    if not abstract:
        setattr(sys.modules[models_module], name, event_model)

    return event_model


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


class Event(models.Model):
    """
    An abstract model for base elements of a event
    """

    pgh_id = models.AutoField(primary_key=True)
    pgh_created_at = models.DateTimeField(auto_now_add=True)
    pgh_label = models.TextField(help_text="The event label.")
    pgh_events = None
    pgh_tracked_model = None

    class Meta:
        abstract = True

    @classmethod
    def pghistory_setup(cls):
        """
        Called when the class is prepared (see apps.py)
        to finalize setup of the model and register triggers
        """
        if not cls._meta.abstract or not cls._meta.managed:  # pragma: no branch
            for event in cls.pgh_events or []:
                event.setup(cls)

    @classmethod
    def factory(
        cls,
        model,
        *events,
        fields=None,
        exclude=None,
        obj_fk=pghistory.constants.unset,
        context_fk=pghistory.constants.unset,
        abstract=True,
        related_name=None,
        name=None,
        app_label=None,
    ):
        return create_event_model(
            cls,
            model,
            fields=fields,
            exclude=exclude,
            obj_fk=obj_fk,
            context_fk=context_fk,
            abstract=abstract,
            related_name=related_name,
            name=name,
            app_label=app_label,
            attrs={"pgh_events": events},
        )


class AggregateEventQueryCompiler(SQLCompiler):
    def _get_empty_aggregate_event_select(self):
        """
        When targetting a model that has no event tables, there are
        no valid tables from which a CTE can be generated.

        This method generates a CTE that returns an empty table in the
        schema of the AggregateEvent table. Note that it's impossible to
        create an empty CTE, so we select NULL VALUES and LIMIT to 0.
        """
        col_name_clause = ", ".join([field.column for field in self.query.model._meta.fields])
        col_select_clause = ",\n".join(
            [
                f"_pgh_obj_event.{field.column}::"
                f"{field.rel_db_type(self.connection)} AS {field.attname}"
                for field in self.query.model._meta.fields
            ]
        )
        values_list = ["(NULL)" for field in self.query.model._meta.fields]
        return f"""
            SELECT
              {col_select_clause}
            FROM (
              VALUES ({', '.join(values_list)}) LIMIT 0
            ) AS _pgh_obj_event({col_name_clause})
            WHERE pgh_table IS NOT NULL
        """

    def _class_for_target(self, obj):
        if isinstance(obj, models.QuerySet):
            return obj.model
        elif isinstance(obj, list):
            return obj[0].__class__
        return obj.__class__

    def _get_aggregate_event_select(self, obj, event_model):
        cls = self._class_for_target(obj)
        related_fields = [
            field.column
            for field in event_model._meta.fields
            if getattr(field, "related_model", None) == cls
        ]
        if not related_fields:
            raise ValueError(f"Event model {event_model} does not reference {cls}")

        event_table = event_model._meta.db_table
        if isinstance(obj, models.QuerySet) or isinstance(obj, list):
            opt = "IN"
            pks = "','".join(f"{o.pk}" for o in obj)
            pks = f"('{pks}')"
        else:
            opt = "="
            pks = f"'{obj.pk}'"
        where_filter = " OR ".join(f"_event.{col} {opt} {pks}" for col in related_fields)

        context_join_clause = ""
        final_context_columns_clause = "".join(
            [
                f"_pgh_obj_event.{field.column},\n"
                for field in self.query.model._meta.fields
                if not field.attname.startswith("pgh_")
            ]
        )
        if hasattr(event_model, "pgh_context_id"):
            context_column_clause = "pgh_context_id"

            # If the aggregate event model has any non-pgh fields,
            # pull these directly from the context metadata
            annotated_context_columns_clause = "".join(
                [
                    f"(_pgh_context.metadata->>'{field.name}')::"
                    f"{field.rel_db_type(self.connection)} AS {field.column},\n"
                    for field in self.query.model._meta.fields
                    if not field.attname.startswith("pgh_")
                ]
            )
            if annotated_context_columns_clause:
                context_join_clause = f"""
                    LEFT OUTER JOIN {Context._meta.db_table} _pgh_context
                        ON _pgh_context.id = _event.pgh_context_id
                """
        else:
            context_column_clause = "NULL::uuid AS pgh_context_id"

            # If the aggregate event model has any non-pgh fields,
            # make them null since there is no context on this event
            annotated_context_columns_clause = "".join(
                [
                    f"NULL::{field.rel_db_type(self.connection)}" f" AS {field.attname},\n"
                    for field in self.query.model._meta.fields
                    if not field.attname.startswith("pgh_")
                ]
            )

        prev_data_clause = """
            LAG(row_to_json(_event))
              OVER (
                PARTITION BY _event.pgh_obj_id, _event.pgh_label
                ORDER BY _event.pgh_id
              ) AS _prev_data
        """
        if not hasattr(event_model, "pgh_obj_id"):
            prev_data_clause = "NULL::jsonb AS _prev_data"

        return f"""
            SELECT
              _pgh_obj_event.pgh_id,
              _pgh_obj_event.pgh_created_at,
              _pgh_obj_event.pgh_label,
              {final_context_columns_clause}
              '{event_table}' AS pgh_table,
              (
                  SELECT jsonb_object_agg(filtered.key, filtered.value)
                  FROM
                    (
                        SELECT key, value
                        FROM jsonb_each(_pgh_obj_event._curr_data::jsonb)
                    ) filtered
                  WHERE filtered.key NOT LIKE 'pgh_%%'
              ) AS pgh_data,
              (
                SELECT jsonb_object_agg(curr.key, array[prev.value, curr.value])
                FROM
                  (
                    SELECT key, value
                    FROM jsonb_each(_pgh_obj_event._curr_data::jsonb)
                  ) curr
                  LEFT OUTER JOIN
                  (
                    SELECT key, value
                    FROM jsonb_each(_pgh_obj_event._prev_data::jsonb)
                  ) prev
                  ON curr.key = prev.key
                WHERE curr.key NOT LIKE 'pgh_%%'
                  AND curr.value != prev.value
                  AND prev IS NOT NULL
              ) AS pgh_diff,
              _pgh_obj_event.pgh_context_id
            FROM (
              SELECT
                pgh_id,
                pgh_created_at,
                pgh_label,
                row_to_json(_event) AS _curr_data,
                {annotated_context_columns_clause}
                {prev_data_clause},
                {context_column_clause}
              FROM {event_table} _event
              {context_join_clause}
              WHERE {where_filter}
            ) _pgh_obj_event
        """

    def get_aggregate_event_cte(self):
        """
        Returns the CTE clause for the aggregate event query
        """
        obj = self.query.target
        if not obj:
            raise ValueError("Must use .target() to target an object for event aggregation")

        event_models = self.query.across
        cls = self._class_for_target(obj)
        if not event_models:
            event_models = [
                model
                for model in apps.get_models()
                if issubclass(model, Event)
                and not issubclass(model, BaseAggregateEvent)
                and any(
                    getattr(field, "related_model", None) == cls for field in model._meta.fields
                )
            ]

        agg_event_table = self.query.model._meta.db_table
        inner_cte = "UNION ALL ".join(
            [self._get_aggregate_event_select(obj, event_model) for event_model in event_models]
        )
        if not inner_cte:
            inner_cte = self._get_empty_aggregate_event_select()

        return f"WITH {agg_event_table} AS (\n" + inner_cte + "\n)\n"

    def as_sql(self, *args, **kwargs):
        base_sql, base_params = super().as_sql(*args, **kwargs)

        # Create the CTE that will be queried and insert it into the
        # main query
        cte = self.get_aggregate_event_cte()

        return cte + base_sql, base_params


class AggregateEventQuery(Query):
    """A query over an aggregate event CTE"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = None
        self.across = []

    def get_compiler(self, using=None, connection=None):  # pragma: no cover
        """
        Overrides the Query method get_compiler in order to return
        an AggregateEventCompiler.

        Copies the body of Django's get_compiler and overrides the return,
        so we ignore covering this method.
        """
        # Copy the body of this method from Django except the final
        # return statement.
        if using is None and connection is None:
            raise ValueError("Need either using or connection")

        if using:
            connection = connections[using]

        # Check that the compiler will be able to execute the query
        for _, aggregate in self.annotation_select.items():
            connection.ops.check_expression_support(aggregate)

        # Instantiate the custom compiler.
        return AggregateEventQueryCompiler(self, connection, using)

    def __chain(self, _name, klass=None, *args, **kwargs):
        clone = getattr(super(), _name)(self.__class__, *args, **kwargs)
        clone.target = self.target
        clone.across = self.across
        return clone

    if django.VERSION < (2, 0):  # pragma: no cover

        def clone(self, klass=None, *args, **kwargs):
            return self.__chain("clone", klass, *args, **kwargs)

    else:

        def chain(self, klass=None):
            return self.__chain("chain", klass)


class AggregateEventQuerySet(models.QuerySet):
    """QuerySet with support for Common Table Expressions"""

    def __init__(self, model=None, query=None, using=None, hints=None):
        # Only create an instance of a Query if this is the first invocation in
        # a query chain.
        if query is None:
            query = AggregateEventQuery(model)
        super().__init__(model, query, using, hints)

    def across(self, *event_models):
        """Aggregates events across the provided event models"""
        qs = self._clone()
        qs.query.across = event_models
        return qs

    def target(self, obj):
        """Target an object to aggregate events against"""
        qs = self._clone()
        qs.query.target = obj
        return qs


class BaseAggregateEvent(Event):
    """
    A proxy model for aggregating events together across tables and
    rendering diffs
    """

    pgh_table = models.CharField(
        max_length=64, help_text="The table under which the event is stored"
    )
    pgh_data = PGHistoryJSONField(help_text="The raw data of the event row")
    pgh_diff = PGHistoryJSONField(
        help_text="The diff between the previous event and the current event"
    )
    pgh_context = models.ForeignKey(
        Context,
        null=True,
        help_text="The context, if any, associated with the event",
        on_delete=models.DO_NOTHING,
    )

    objects = AggregateEventQuerySet.as_manager()

    class Meta:
        abstract = True


class AggregateEvent(BaseAggregateEvent):
    """
    A proxy model for aggregating events together across tables and
    rendering diffs
    """

    class Meta:
        managed = False
