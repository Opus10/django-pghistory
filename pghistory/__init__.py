import django

from pghistory.core import AfterInsert
from pghistory.core import AfterInsertOrUpdate
from pghistory.core import AfterUpdate
from pghistory.core import BeforeDelete
from pghistory.core import BeforeUpdate
from pghistory.core import create_event
from pghistory.core import DatabaseEvent
from pghistory.core import Event
from pghistory.core import get_event_model
from pghistory.core import Snapshot
from pghistory.core import track
from pghistory.tracking import context
from pghistory.version import __version__


__all__ = [
    "AfterInsert",
    "AfterInsertOrUpdate",
    "AfterUpdate",
    "BeforeDelete",
    "BeforeUpdate",
    "context",
    "create_event",
    "DatabaseEvent",
    "get_event_model",
    "Snapshot",
    "Event",
    "track",
    "__version__",
]

if django.VERSION < (3, 2):
    default_app_config = "pghistory.apps.PGHistoryConfig"

del django
