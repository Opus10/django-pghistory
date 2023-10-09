import uuid
import warnings

import django
from django.apps import apps
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connections, models
from django.db.models.functions import Cast
from django.db.models.sql import Query
from django.db.models.sql.compiler import SQLCompiler

from pghistory import core, utils

# This class is to preserve backwards compatibility with migrations
PGHistoryJSONField = utils.JSONField


class Context(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = utils.JSONField(default=dict)

    @classmethod
    def install_pgh_attach_context_func(cls, using=DEFAULT_DB_ALIAS):
        """
        Installs a custom store procedure for upserting context
        for historical events. The upsert is aware of when tracking is
        enabled in the app (i.e. using pghistory.context())

        This stored procedure is automatically installed in pghistory migration 0004.
        """
        with connections[using].cursor() as cursor:
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


class EventQueryCompiler(SQLCompiler):
    def _get_cte(self):
        """
        Returns a CTE that selects from proxied fields
        """
        event_model = self.query.model

        annotations = {
            f"_{field.column}": Cast(field.pgh_proxy, output_field=field)
            for field in self.proxy_fields
        }
        values = [
            field.name for field in event_model._meta.fields if not hasattr(field, "pgh_proxy")
        ] + [f"_{field.column}" for field in self.proxy_fields]

        qset = models.QuerySet(event_model).annotate(**annotations).values(*values)

        sql, params = qset.query.as_sql(self, self.connection)
        with self.connection.cursor() as cursor:
            sql = cursor.mogrify(sql, params)
            if isinstance(sql, bytes):  # psycopg 2/3 return different types
                sql = sql.decode("utf-8")

        for field in self.proxy_fields:
            sql = sql.replace(f"_{field.column}", field.column)

        sql = sql.replace("->", "->>")
        return "WITH pgh_event_cte AS (\n" + sql + "\n)\n"

    @property
    def proxy_fields(self):
        return [f for f in self.query.model._meta.fields if hasattr(f, "pgh_proxy")]

    def as_sql(self, *args, **kwargs):
        """
        If there are proxied fields on the event model, return a select from a CTE.
        Otherwise don't do anything special
        """
        sql, params = super().as_sql(*args, **kwargs)

        if any(self.proxy_fields):
            if django.VERSION < (3, 2):  # pragma: no cover
                raise RuntimeError("Must use Django 3.2 or above to proxy fields on event models")

            cte = self._get_cte()
            sql = cte + sql.replace(f'"{self.query.model._meta.db_table}"', '"pgh_event_cte"')

        return sql, params


class EventQuery(Query):
    """A query over an event CTE when proxy fields are used"""

    def get_compiler(self, *args, **kwargs):
        """
        Overrides the Query method get_compiler in order to return
        an EventQueryCompiler.
        """
        compiler = super().get_compiler(*args, **kwargs)
        compiler.__class__ = EventQueryCompiler
        return compiler


class EventQuerySet(models.QuerySet):
    """QuerySet with support for proxy fields"""

    def __init__(self, model=None, query=None, using=None, hints=None):
        if query is None:
            query = EventQuery(model)

        super().__init__(model, query, using, hints)


class PghEventModel:
    "A descriptor for accessing the pgh_event_model field on a tracked model"

    def __get__(self, instance, owner):
        if len(owner.pgh_event_models) == 1:
            return owner.pgh_event_models[list(owner.pgh_event_models)[0]]
        else:
            raise ValueError(
                f"{owner.__name__} has more than one tracker."
                " Use the pgh_event_models dictionary to retrieve the event"
                " model by label."
            )


class Event(models.Model):
    """
    An abstract model for base elements of a event
    """

    pgh_id = models.AutoField(primary_key=True)
    pgh_created_at = models.DateTimeField(auto_now_add=True)
    pgh_label = models.TextField(help_text="The event label.")
    pgh_trackers = None
    pgh_tracked_model = None

    objects = EventQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def can_revert(self):
        """True if the event model can revert the tracked model"""
        model_fields = {f.name for f in self.pgh_tracked_model._meta.fields}
        tracked_fields = {f.name for f in self._meta.fields}
        return model_fields.issubset(tracked_fields)

    def revert(self, using=DEFAULT_DB_ALIAS):
        """
        Reverts the tracked model based on the event fields.

        Raises a RuntimeError if the event model doesn't track all fields
        """
        if not self.can_revert:
            raise RuntimeError(
                f'Event model "{self.__class__.__name__}" cannot revert'
                f' "{self.pgh_tracked_model.__class__.__name__}" because it'
                " doesn't track every field."
            )

        qset = models.QuerySet(model=self.pgh_tracked_model, using=using)

        pk = getattr(self, self.pgh_tracked_model._meta.pk.name)
        return qset.update_or_create(
            pk=pk,
            defaults={
                field.name: getattr(self, field.name)
                for field in self.pgh_tracked_model._meta.fields
                if field != self.pgh_tracked_model._meta.pk
            },
        )[0]

    @classmethod
    def pghistory_setup(cls):
        """
        Called when the class is prepared (see apps.py)
        to finalize setup of the model and register triggers
        """
        if (
            not cls._meta.abstract and cls._meta.managed and not cls._meta.proxy
        ):  # pragma: no branch
            for tracker in cls.pgh_trackers or []:
                tracker.pghistory_setup(cls)

            # Set up the event model utility properties. Don't overwrite any
            # existing attributes
            if not hasattr(cls.pgh_tracked_model, "pgh_event_models"):
                cls.pgh_tracked_model.pgh_event_models = {}

            # Use dir here, otherwise the property is evaluated
            if "pgh_event_model" not in dir(cls.pgh_tracked_model):
                cls.pgh_tracked_model.pgh_event_model = PghEventModel()

            if isinstance(cls.pgh_tracked_model.pgh_event_models, dict):  # pragma: no branch
                cls.pgh_tracked_model.pgh_event_models.update(
                    {tracker.label: cls for tracker in cls.pgh_trackers or []}
                )

    @classmethod
    def check(cls, **kwargs):
        """
        Allow proxy models to inherit this model and define their own fields
        that are dynamically pulled from context
        """
        errors = super().check(**kwargs)

        # If all local fields are proxied, ignored error E017 and allow the fields to be declared
        if any(error for error in errors if error.id == "models.E017") and all(
            hasattr(field, "pgh_proxy") for field in cls._meta.local_fields
        ):
            return [error for error in errors if error.id != "models.E017"]
        else:
            return errors


class EventsQueryCompiler(SQLCompiler):
    def _get_empty_select(self):
        """
        When targetting a model that has no event tables, there are
        no valid tables from which a CTE can be generated.

        This method generates a CTE that returns an empty table in the
        schema of the Events table. Note that it's impossible to
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
            WHERE pgh_model IS NOT NULL
        """

    def _validate(self):
        if (
            isinstance(self.references, (list, tuple))
            and len({r.__class__ for r in self.references}) > 1
        ):
            raise ValueError("The objects passed to references() are not of the same type.")
        elif (
            isinstance(self.tracks, (list, tuple)) and len({o.__class__ for o in self.tracks}) > 1
        ):
            raise ValueError("The objects passed to tracks() are not of the same type.")
        elif self.references_model and self.tracks_model:
            raise ValueError("Cannot use both tracks() and references().")

    @property
    def references_model(self):
        if isinstance(self.references, models.QuerySet):
            return self.references.model._meta.concrete_model
        elif isinstance(self.references, (list, tuple)) and self.references:
            return self.references[0].__class__._meta.concrete_model

    @property
    def references(self):
        return self.query.references

    @property
    def tracks_model(self):
        if isinstance(self.tracks, models.QuerySet):
            return self.tracks.model._meta.concrete_model
        elif isinstance(self.tracks, (list, tuple)) and self.tracks:
            return self.tracks[0].__class__._meta.concrete_model

    @property
    def tracks(self):
        return self.query.tracks

    @property
    def across(self):
        return core.event_models(
            models=self.query.across,
            references_model=self.references_model,
            tracks_model=self.tracks_model,
        )

    def _get_context_clauses(self, event_model):
        """
        Get the clauses for obtaining context based on the event model

        We have the following cases to handle:
        1. No pgh_context
        2. A pgh_context foreign key is used
        3. A pgh_context JSON is used with pgh_context_id
        4. A pgh_context JSON is used without pgh_context_id
        """
        proxy_fields = []
        for field in self.query.model._meta.fields:
            if hasattr(field, "pgh_proxy"):
                if not field.pgh_proxy.startswith("pgh_context__"):  # pragma: no cover
                    raise RuntimeError(
                        "Proxy fields on Events models can only proxy the pgh_context field."
                        " E.g. pgh_context__url"
                    )

                proxy_fields.append((field, field.pgh_proxy.split("__", 1)[1]))
            elif not field.attname.startswith("pgh_"):
                warnings.warn(
                    f"django-pghistory extra field '{field}' in event model"
                    f" '{self.query.model._meta.label}' declared. Use"
                    " 'pghistory.ProxyField' to define a proxy fields instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                proxy_fields.append((field, field.name))

        context_join_clause = ""
        final_context_columns_clause = "".join(
            [f"_pgh_obj_event.{field.column},\n" for field, _ in proxy_fields]
        )

        if not hasattr(event_model, "pgh_context"):
            context_id_column_clause = "NULL::UUID AS pgh_context_id"
            context_column_clause = "NULL::JSONB AS pgh_context"

            # If the aggregate event model has any proxy fields,
            # make them null since there is no context on this event
            annotated_context_columns_clause = "".join(
                [
                    f"NULL::{field.rel_db_type(self.connection)} AS {field.column},\n"
                    for field, _ in proxy_fields
                ]
            )
        elif isinstance(event_model._meta.get_field("pgh_context"), models.ForeignKey):
            context_id_column_clause = "pgh_context_id"
            context_column_clause = "_pgh_context.metadata AS pgh_context"

            # If the aggregate event model has any proxy fields,
            # pull these directly from the context metadata
            annotated_context_columns_clause = "".join(
                [
                    f"(_pgh_context.metadata->>'{attr}')::"
                    f"{field.rel_db_type(self.connection)} AS {field.column},\n"
                    for field, attr in proxy_fields
                ]
            )
            context_join_clause = f"""
                LEFT OUTER JOIN {Context._meta.db_table} _pgh_context
                    ON _pgh_context.id = _event.pgh_context_id
            """
        elif isinstance(event_model._meta.get_field("pgh_context"), utils.DjangoJSONField):
            context_column_clause = "pgh_context"
            annotated_context_columns_clause = "".join(
                [
                    f"(pgh_context->>'{attr}')::"
                    f"{field.rel_db_type(self.connection)} AS {field.column},\n"
                    for field, attr in proxy_fields
                ]
            )

            if hasattr(event_model, "pgh_context_id"):
                context_id_column_clause = "pgh_context_id"
            else:
                context_id_column_clause = "NULL::UUID AS pgh_context_id"
        else:
            raise AssertionError

        return (
            final_context_columns_clause,
            context_column_clause,
            context_id_column_clause,
            context_join_clause,
            annotated_context_columns_clause,
        )

    def _get_where_clause(self, event_model):
        if self.references:
            rows = self.references
            cols = [
                field.column
                for field in event_model._meta.fields
                if utils.related_model(field) == self.references_model
            ]
        elif self.tracks:
            rows = self.tracks
            cols = [event_model._meta.get_field("pgh_obj").column]
        else:
            return ""

        if isinstance(rows, models.QuerySet) or len(rows) > 1:
            opt = "IN"
            # TODO: Use a subquery
            pks = "','".join(f"{o.pk}" for o in rows)
            pks = f"('{pks}')"
        else:
            opt = "="
            pks = f"'{rows[0].pk}'"

        return "WHERE " + " OR ".join(f"_event.{col} {opt} {pks}" for col in cols)

    def _get_select(self, event_model):
        where_clause = self._get_where_clause(event_model)

        (
            final_context_columns_clause,
            context_column_clause,
            context_id_column_clause,
            context_join_clause,
            annotated_context_columns_clause,
        ) = self._get_context_clauses(event_model)

        prev_data_clause = """
            LAG(row_to_json(_event))
              OVER (
                PARTITION BY _event.pgh_obj_id, _event.pgh_label
                ORDER BY _event.pgh_id
              ) AS _prev_data
        """
        pgh_obj_id_column_clause = "pgh_obj_id::TEXT"
        if not hasattr(event_model, "pgh_obj_id"):
            prev_data_clause = "NULL::JSONB AS _prev_data"
            pgh_obj_id_column_clause = "NULL::TEXT AS pgh_obj_id"

        event_table = event_model._meta.db_table
        return f"""
            SELECT
              CONCAT('{event_model._meta.label}', ':', _pgh_obj_event.pgh_id) AS pgh_slug,
              _pgh_obj_event.pgh_id,
              _pgh_obj_event.pgh_created_at,
              _pgh_obj_event.pgh_label,
              {final_context_columns_clause}
              _pgh_obj_event.pgh_obj_id,
              '{event_model._meta.label}' AS pgh_model,
              '{event_model.pgh_tracked_model._meta.label}' AS pgh_obj_model,
              (
                  SELECT JSONB_OBJECT_AGG(filtered.key, filtered.value)
                  FROM
                    (
                        SELECT key, value
                        FROM JSONB_EACH(_pgh_obj_event._curr_data::JSONB)
                    ) filtered
                  WHERE filtered.key NOT LIKE 'pgh_%%'
              ) AS pgh_data,
              (
                SELECT JSONB_OBJECT_AGG(curr.key, array[prev.value, curr.value])
                FROM
                  (
                    SELECT key, value
                    FROM JSONB_EACH(_pgh_obj_event._curr_data::JSONB)
                  ) curr
                  LEFT OUTER JOIN
                  (
                    SELECT key, value
                    FROM JSONB_EACH(_pgh_obj_event._prev_data::JSONB)
                  ) prev
                  ON curr.key = prev.key
                WHERE curr.key NOT LIKE 'pgh_%%'
                  AND curr.value != prev.value
                  AND prev IS NOT NULL
              ) AS pgh_diff,
              _pgh_obj_event.pgh_context_id,
              _pgh_obj_event.pgh_context
            FROM (
              SELECT
                pgh_id,
                pgh_created_at,
                pgh_label,
                row_to_json(_event) AS _curr_data,
                {annotated_context_columns_clause}
                {prev_data_clause},
                {context_id_column_clause},
                {context_column_clause},
                {pgh_obj_id_column_clause}
              FROM {event_table} _event
              {context_join_clause}
              {where_clause}
              ORDER BY _event.pgh_id
            ) _pgh_obj_event
        """

    def _get_cte(self):
        """
        Returns the CTE clause for the aggregate event query
        """
        events_table = self.query.model._meta.db_table
        inner_cte = "UNION ALL ".join(
            [self._get_select(event_model) for event_model in self.across]
        )
        if not inner_cte:
            inner_cte = self._get_empty_select()

        return f"WITH {events_table} AS (\n" + inner_cte + "\n)\n"

    def as_sql(self, *args, **kwargs):
        self._validate()

        base_sql, base_params = super().as_sql(*args, **kwargs)

        # Create the CTE that will be queried and insert it into the
        # main query
        cte = self._get_cte()

        return cte + base_sql, base_params


class EventsQuery(Query):
    """A query over an aggregate event CTE"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.references = []
        self.tracks = []
        self.across = []

    def get_compiler(self, *args, **kwargs):
        compiler = super().get_compiler(*args, **kwargs)
        compiler.__class__ = EventsQueryCompiler
        return compiler

    def __chain(self, _name, klass=None, *args, **kwargs):
        clone = getattr(super(), _name)(self.__class__, *args, **kwargs)
        clone.references = self.references
        clone.tracks = self.tracks
        clone.across = self.across
        return clone

    def chain(self, klass=None):
        return self.__chain("chain", klass)


class EventsQuerySet(models.QuerySet):
    """QuerySet with support for Common Table Expressions"""

    def __init__(self, model=None, query=None, using=None, hints=None):
        # Only create an instance of a Query if this is the first invocation in
        # a query chain.
        if query is None:
            query = EventsQuery(model)

        super().__init__(model, query, using, hints)

    def across(self, *event_models):
        """Aggregates events across the provided event models"""
        qs = self._clone()
        qs.query.across = [
            apps.get_model(model) if isinstance(model, str) else model for model in event_models
        ]
        return qs

    def references(self, *objs):
        """Query any rows that reference the objs.

        If, for example, a foreign key or pgh_obj field points to the
        object, it will be aggregated.
        """
        assert len(objs) >= 1

        if isinstance(objs[0], (list, tuple, models.QuerySet)):
            assert len(objs) == 1
            objs = objs[0]

        qs = self._clone()
        qs.query.references = objs
        return qs

    def tracks(self, *objs):
        """Query any rows with pgh_obj equal to the objs."""
        assert len(objs) >= 1

        if isinstance(objs[0], (list, tuple, models.QuerySet)):
            assert len(objs) == 1
            objs = objs[0]

        qs = self._clone()
        qs.query.tracks = objs
        return qs


class NoObjectsManager(models.Manager):
    """
    Django's dumpdata and other commands will not work with Events models
    by default because of how they aggregate multiple tables based on objects.

    We use this as the default manager for aggregate events so that dumpdata
    and other management commands still work with these models
    """

    def get_queryset(self, *args, **kwargs):
        return models.QuerySet(self.model, using=self._db).none()


class Events(models.Model):
    """
    A proxy model for aggregating events together across tables and
    rendering diffs
    """

    pgh_slug = models.TextField(
        primary_key=True, help_text="The unique identifier across all event tables."
    )
    pgh_model = models.CharField(max_length=64, help_text="The event model.")
    pgh_id = models.BigIntegerField(help_text="The primary key of the event.")
    pgh_created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the event was created."
    )
    pgh_label = models.TextField(help_text="The event label.")
    pgh_data = utils.JSONField(help_text="The raw data of the event.")
    pgh_diff = utils.JSONField(help_text="The diff between the previous event of the same label.")
    pgh_context_id = models.UUIDField(null=True, help_text="The context UUID.")
    pgh_context = utils.JSONField(
        null=True,
        help_text="The context associated with the event.",
    )
    pgh_obj_model = models.CharField(max_length=64, help_text="The object model.")
    pgh_obj_id = models.TextField(null=True, help_text="The primary key of the object.")

    objects = EventsQuerySet.as_manager()
    no_objects = NoObjectsManager()

    class Meta:
        managed = False
        verbose_name_plural = "events"
        # See the docs for NoObjectsManager about why this is the default
        # manager
        default_manager_name = "no_objects"

    @classmethod
    def check(cls, **kwargs):
        """
        Allow proxy models to inherit this model and define their own fields
        that are dynamically pulled from context
        """
        errors = super().check(**kwargs)
        return [error for error in errors if error.id != "models.E017"]


class MiddlewareEvents(Events):
    """
    A proxy model for aggregating events. Includes additional fields that
    are captured by the pghistory middleware
    """

    user = core.ProxyField(
        "pgh_context__user",
        models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.DO_NOTHING,
            help_text="The user associated with the event.",
        ),
    )
    url = core.ProxyField(
        "pgh_context__url",
        models.TextField(help_text="The url associated with the event."),
    )

    class Meta:
        proxy = True
        verbose_name_plural = "middleware events"


# These models are deprecated
from pghistory import deprecated  # noqa


class BaseAggregateEvent(Event):
    """
    A proxy model for aggregating events together across tables and
    rendering diffs
    """

    pgh_table = models.CharField(
        max_length=64, help_text="The table under which the event is stored"
    )
    pgh_data = utils.JSONField(help_text="The raw data of the event row")
    pgh_diff = utils.JSONField(
        help_text="The diff between the previous event and the current event"
    )
    pgh_context = models.ForeignKey(
        "pghistory.Context",
        null=True,
        help_text="The context, if any, associated with the event",
        on_delete=models.DO_NOTHING,
    )

    objects = deprecated.AggregateEventQuerySet.as_manager()
    no_objects = deprecated.NoObjectsManager()

    class Meta:
        abstract = True
        # See the docs for NoObjectsManager about why this is the default
        # manager
        default_manager_name = "no_objects"


class AggregateEvent(BaseAggregateEvent):
    """
    A proxy model for aggregating events together across tables and
    rendering diffs
    """

    class Meta:
        managed = False
