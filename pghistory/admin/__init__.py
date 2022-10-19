import django

from pghistory.admin.core import (
    EventModelAdmin,
    EventsAdmin,
)

__all__ = [
    "EventModelAdmin",
    "EventsAdmin",
]

if django.VERSION < (3, 2):
    default_app_config = "pghistory.admin.apps.PGHistoryAdminConfig"

del django
