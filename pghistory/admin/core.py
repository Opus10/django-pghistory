import warnings

import django
from django.apps import apps
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.utils.encoding import force_str

from pghistory import config, core


def _get_model(model):
    if model:
        try:
            return apps.get_model(model)
        except Exception:
            pass


def _get_obj(model_pk):
    """Gets an object from a model:pk string"""
    if model_pk and ":" in model_pk:
        model, pk = model_pk.split(":", 1)
        model = _get_model(model)
        if model:
            return model(pk=pk)


class MethodFilter(admin.SimpleListFilter):
    title = "method"
    parameter_name = "method"

    def lookups(self, request, model_admin):
        return (("tracks", "tracks"), ("references", "references"))

    def queryset(self, request, queryset):
        obj = request.GET.get("obj")
        obj = _get_obj(obj)
        if obj and self.value() == "tracks":
            queryset = queryset.tracks(obj)
        elif obj and self.value() == "references":  # pragma: no branch
            queryset = queryset.references(obj)

        return queryset

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == force_str(lookup),
                "query_string": changelist.get_query_string({self.parameter_name: lookup}, []),
                "display": title,
            }


def _filter_event_models(request):
    obj = _get_obj(request.GET.get("obj"))
    method = request.GET.get("method")
    model = _get_model(request.GET.get("model"))

    if obj and method == "tracks":
        return core.event_models(tracks_model=obj.__class__)
    elif obj and method == "references":
        return core.event_models(references_model=obj.__class__)
    elif model:
        return core.event_models(tracks_model=model, include_missing_pgh_obj=True)
    else:
        return core.event_models()


class LabelFilter(admin.SimpleListFilter):
    title = "label"
    parameter_name = "label"

    def lookups(self, request, model_admin):
        from pghistory.models import Event  # noqa

        if issubclass(model_admin.model, Event):
            event_models = [model_admin.model]
        else:
            event_models = _filter_event_models(request)

        labels = {
            tracker.label
            for event_model in event_models
            for tracker in event_model.pgh_trackers or []
        }
        return sorted([(label, label) for label in labels])

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(pgh_label=self.value())

        return queryset


class EventModelFilter(admin.SimpleListFilter):
    title = "event model"
    parameter_name = "event_model"

    def lookups(self, request, model_admin):
        event_models = _filter_event_models(request)
        return sorted(
            (event_model._meta.label_lower, event_model._meta.label)
            for event_model in event_models
        )

    def queryset(self, request, queryset):
        model = _get_model(request.GET.get("model"))
        if self.value():
            queryset = queryset.across(self.value())
        elif model:
            queryset = queryset.across(*_filter_event_models(request))

        return queryset


class DynamicFilter(admin.SimpleListFilter):
    title = ""

    def queryset(self, request, queryset):
        return queryset

    def lookups(self, request, model_admin):
        if self.parameter_name in request.GET:
            return [(request.GET[self.parameter_name], request.GET[self.parameter_name])]
        else:  # pragma: no cover
            return []


class ObjFilter(DynamicFilter):
    title = "object"
    parameter_name = "obj"

    def queryset(self, request, queryset):
        if (
            "method" not in request.GET
            and hasattr(queryset.model, "pgh_obj")
            and ":" in self.value()
        ):
            queryset = queryset.filter(pgh_obj=self.value().split(":", 1)[1])

        return queryset


class ModelFilter(DynamicFilter):
    title = "model"
    parameter_name = "model"


class BackFilter(DynamicFilter):
    parameter_name = "back"
    template = "pghistory_admin/hidden_filter.html"


class BaseEventAdmin(admin.ModelAdmin):
    change_list_template = "pghistory_admin/events_change_list.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = {"title": self.model._meta.verbose_name_plural.capitalize()}
        obj = _get_obj(request.GET.get("obj"))
        method = request.GET.get("method")
        model = _get_model(request.GET.get("model"))
        if obj:
            obj.refresh_from_db()
            if method:
                extra_context["subtitle"] = f"{method.title()} {obj}"
            else:
                extra_context["subtitle"] = f"{obj}"
        elif model:
            extra_context["subtitle"] = f"{model._meta.label}"

        if "back" in request.GET:
            extra_context["pgh_back"] = request.GET["back"]

        return super().changelist_view(request, extra_context=extra_context)


class EventModelAdmin(BaseEventAdmin):
    """The base admin for event models"""

    list_filter = [LabelFilter, ObjFilter, BackFilter]


class EventsChangeList(ChangeList):
    def get_queryset(self, request):
        # Note: Call get_queryset first so that has_active_filters is accurate
        qset = super().get_queryset(request)

        if not config.admin_all_events():
            if django.VERSION < (3, 1):  # pragma: no cover
                warnings.warn("PGHISTORY_ADMIN_ALL_EVENTS only works for Django 3.1 and above")
            elif not self.has_active_filters:  # pragma: no branch
                return self.root_queryset.model.no_objects.all()

        return qset


class EventsAdmin(BaseEventAdmin):
    def get_changelist(self, request, **kwargs):
        return EventsChangeList

    def get_list_display(self, request):
        return config.admin_list_display()

    def get_list_filter(self, request):
        filters = [LabelFilter, EventModelFilter]
        if "obj" in request.GET:
            filters.extend([MethodFilter, ObjFilter, BackFilter])
        elif "model" in request.GET:
            filters.extend([ModelFilter, BackFilter])

        return filters

    def get_queryset(self, request):
        return config.admin_queryset()
