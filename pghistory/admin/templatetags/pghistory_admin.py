import collections

from django import template, urls
from django.apps import apps
from django.contrib import admin

from pghistory import config, models
from pghistory.admin import EventModelAdmin

register = template.Library()


@register.filter
def events_are_tracked(model):
    model = apps.get_model(model)
    return any(
        model._meta.concrete_model == m.pgh_tracked_model._meta.concrete_model
        for m in apps.get_models()
        if issubclass(m, models.Event) and m.pgh_tracked_model
    )


@register.simple_tag()
def events_admin_url():
    """Retrieves the admin url of the events"""
    model = config.admin_queryset().model

    return urls.reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")


@register.filter
def event_admins(model):
    """Retrieves the admins of all event models associated with the primary model"""
    model = apps.get_model(model)._meta.concrete_model
    tracked_models = collections.defaultdict(set)

    for m in apps.get_models():
        if issubclass(m, models.Event) and m.pgh_tracked_model and hasattr(m, "pgh_obj"):
            tracked_models[m.pgh_tracked_model._meta.concrete_model].add(m._meta.concrete_model)

    admin_registry = {
        m._meta.concrete_model: admin
        for m, admin in admin.site._registry.items()
        if isinstance(admin, EventModelAdmin)
    }
    return [admin_registry[m].model._meta for m in tracked_models[model] if m in admin_registry]
