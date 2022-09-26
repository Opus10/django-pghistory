import django

from pghistory.config import (
    ContextForeignKey,
    ContextJSONField,
    ContextUUIDField,
    Field,
    ForeignKey,
    ObjForeignKey,
    RelatedField,
)
from pghistory.core import (
    AfterInsert,
    AfterInsertOrUpdate,
    AfterUpdate,
    BeforeDelete,
    BeforeUpdate,
    create_event,
    create_event_model,
    DatabaseEvent,
    Event,
    ProxyField,
    Snapshot,
    track,
)
from pghistory.tracking import context
from pghistory.version import __version__


__all__ = [
    "AfterInsert",
    "AfterInsertOrUpdate",
    "AfterUpdate",
    "BeforeDelete",
    "BeforeUpdate",
    "context",
    "ContextForeignKey",
    "ContextJSONField",
    "ContextUUIDField",
    "create_event",
    "create_event_model",
    "DatabaseEvent",
    "Event",
    "Field",
    "ForeignKey",
    "ObjForeignKey",
    "ProxyField",
    "RelatedField",
    "Snapshot",
    "track",
    "__version__",
]

if django.VERSION < (3, 2):
    default_app_config = "pghistory.apps.PGHistoryConfig"

del django
