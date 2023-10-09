import pgtrigger
from django.db import models

from pghistory import utils


def _get_pgh_obj_pk_col(history_model):
    """
    Returns the column name of the PK field tracked by the history model
    """
    return history_model._meta.get_field("pgh_obj").related_model._meta.pk.column


class Event(pgtrigger.Trigger):
    """
    Events a model with a label when a condition happens
    """

    label = None
    snapshot = "NEW"
    event_model = None
    when = pgtrigger.After

    def __init__(
        self,
        *,
        name=None,
        operation=None,
        condition=None,
        when=None,
        label=None,
        snapshot=None,
        event_model=None,
    ):
        self.label = label or self.label
        if not self.label:  # pragma: no cover
            raise ValueError('Must provide "label"')

        self.event_model = event_model or self.event_model
        if not self.event_model:  # pragma: no cover
            raise ValueError('Must provide "event_model"')

        self.snapshot = snapshot or self.snapshot
        if not self.snapshot:  # pragma: no cover
            raise ValueError('Must provide "snapshot"')

        super().__init__(name=name, operation=operation, condition=condition, when=when)

    def get_func(self, model):
        tracked_model_fields = {f.name for f in self.event_model.pgh_tracked_model._meta.fields}
        fields = {
            f.column: f'{self.snapshot}."{f.column}"'
            for f in self.event_model._meta.fields
            if not isinstance(f, models.AutoField)
            and f.name in tracked_model_fields
            and f.concrete
        }
        fields["pgh_created_at"] = "NOW()"
        fields["pgh_label"] = f"'{self.label}'"

        if hasattr(self.event_model, "pgh_obj"):
            fields["pgh_obj_id"] = f'{self.snapshot}."{_get_pgh_obj_pk_col(self.event_model)}"'

        if hasattr(self.event_model, "pgh_context"):
            if isinstance(self.event_model._meta.get_field("pgh_context"), models.ForeignKey):
                fields["pgh_context_id"] = "_pgh_attach_context()"
            elif isinstance(self.event_model._meta.get_field("pgh_context"), utils.JSONField):
                fields["pgh_context"] = (
                    "COALESCE(NULLIF(CURRENT_SETTING('pghistory.context_metadata', TRUE), ''),"
                    " NULL)::JSONB"
                )
            else:
                raise AssertionError

        if hasattr(self.event_model, "pgh_context_id") and isinstance(
            self.event_model._meta.get_field("pgh_context_id"), models.UUIDField
        ):
            fields[
                "pgh_context_id"
            ] = "COALESCE(NULLIF(CURRENT_SETTING('pghistory.context_id', TRUE), ''), NULL)::UUID"

        fields = {key: fields[key] for key in sorted(fields)}

        cols = ", ".join(f'"{col}"' for col in fields)
        vals = ", ".join(val for val in fields.values())
        sql = f"""
            INSERT INTO "{self.event_model._meta.db_table}"
                ({cols}) VALUES ({vals});
            RETURN NULL;
        """
        return " ".join(line.strip() for line in sql.split("\n") if line.strip()).strip()
