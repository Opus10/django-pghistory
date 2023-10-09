import django
from django.apps import apps
from django.db import connections, models
from django.db.models.sql import Query
from django.db.models.sql.compiler import SQLCompiler

import pghistory.models as pgh_models


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
                    LEFT OUTER JOIN {pgh_models.Context._meta.db_table} _pgh_context
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
                if issubclass(model, pgh_models.Event)
                and not issubclass(model, pgh_models.BaseAggregateEvent)
                and not model._meta.proxy
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


class NoObjectsManager(models.Manager):
    """
    Django's dumpdata and other commands will not work with AggregateEvent models
    by default because of how they aggregate multiple tables based on objects.

    We use this as the default manager for aggregate events so that dumpdata
    and other management commands still work with these models
    """

    def get_queryset(self, *args, **kwargs):
        return models.QuerySet(self.model, using=self._db).none()
