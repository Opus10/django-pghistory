import django
import pgtrigger

from pghistory.config import (
    ContextForeignKey,
    ContextJSONField,
    ContextUUIDField,
    Field,
    ForeignKey,
    ObjForeignKey,
    RelatedField,
)
from pghistory.constants import DEFAULT
from pghistory.core import (
    DeleteEvent,
    InsertEvent,
    ManualEvent,
    ProxyField,
    RowEvent,
    Tracker,
    UpdateEvent,
    create_event,
    create_event_model,
    track,
)
from pghistory.runtime import context
from pghistory.version import __version__

Condition = pgtrigger.Condition
"""For specifying free-form SQL in the condition of a trigger."""

AnyChange = pgtrigger.AnyChange
"""If any supplied fields change, trigger the event.

Args:
    *fields (str): If any supplied fields change, trigger the event.
        If no fields are supplied, defaults to all tracked fields.
    exclude (List[str]): Fields to exclude.
    exclude_auto (bool): Exclude all `auto_now` and `auto_now_add` fields automatically.
"""

AnyDontChange = pgtrigger.AnyDontChange
"""If any supplied fields don't change, trigger the event.

Args:
    *fields (str): If any supplied fields don't change, trigger the event.
        If no fields are supplied, defaults to all tracked fields.
    exclude (List[str]): Fields to exclude.
    exclude_auto (bool): Exclude all `auto_now` and `auto_now_add` fields automatically.
"""

AllChange = pgtrigger.AllChange
"""If all supplied fields change, trigger the event.

Args:
    *fields (str): If all supplied fields change, trigger the event.
        If no fields are supplied, defaults to all tracked fields.
    exclude (List[str]): Fields to exclude.
    exclude_auto (bool): Exclude all `auto_now` and `auto_now_add` fields automatically.
"""

AllDontChange = pgtrigger.AllDontChange
"""If all supplied fields don't change, trigger the event.

Args:
    *fields (str): If all supplied fields don't change, trigger the event.
        If no fields are supplied, defaults to all tracked fields.
    exclude (List[str]): Fields to exclude.
    exclude_auto (bool): Exclude all `auto_now` and `auto_now_add` fields automatically.
"""

F = pgtrigger.F
"""
Similar to Django's `F` object, allows referencing the old and new
rows in a trigger condition.
"""

Q = pgtrigger.Q
"""
Similar to Django's `Q` object, allows building filter clauses based on
the old and new rows in a trigger condition.
"""

Delete = pgtrigger.Delete
"""
For specifying `DELETE` as the trigger operation.
"""

Insert = pgtrigger.Insert
"""
For specifying `INSERT` as the trigger operation.
"""

Update = pgtrigger.Update
"""
For specifying `UPDATE` as the trigger operation.
"""

New = "NEW"
"""
For storing the trigger's "NEW" row in a [pghistory.RowEvent][]
"""

Old = "OLD"
"""
For storing the trigger's "OLD" row in a [pghistory.RowEvent][]
"""

__all__ = [
    "AnyChange",
    "AllChange",
    "AnyDontChange",
    "AllDontChange",
    "Condition",
    "context",
    "ContextForeignKey",
    "ContextJSONField",
    "ContextUUIDField",
    "create_event",
    "create_event_model",
    "DEFAULT",
    "Delete",
    "DeleteEvent",
    "F",
    "Field",
    "ForeignKey",
    "Insert",
    "InsertEvent",
    "ManualEvent",
    "New",
    "ObjForeignKey",
    "Old",
    "ProxyField",
    "Q",
    "RelatedField",
    "RowEvent",
    "track",
    "Tracker",
    "Update",
    "UpdateEvent",
    "__version__",
]

if django.VERSION < (3, 2):  # pragma: no cover
    default_app_config = "pghistory.apps.PGHistoryConfig"

del django
del pgtrigger
