import django.apps
from django.contrib import admin

from pghistory import config


class PGHistoryAdminConfig(django.apps.AppConfig):
    name = "pghistory.admin"
    label = "pghistory_admin"

    def ready(self):
        admin.site.register(config.admin_queryset().model, config.admin_class())
