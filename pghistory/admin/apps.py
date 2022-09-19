import django.apps
from django.contrib import admin

from pghistory import config
from pghistory.admin import core


class PGHistoryAdminConfig(django.apps.AppConfig):
    name = "pghistory.admin"
    label = "pghistory_admin"

    def ready(self):
        admin.site.register(config.admin_queryset().model, core.EventsAdmin)
