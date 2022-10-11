import django

# Django>=3.1 changes the location of JSONField
if django.VERSION >= (3, 1):
    from django.db.models import JSONField as DjangoJSONField
else:
    from django.contrib.postgres.fields import JSONField as DjangoJSONField


class JSONField(DjangoJSONField):
    """
    Creates a consistent import path for JSONField regardless of Django
    version.
    """


def related_model(field):
    """Return the concrete model a field references"""
    if hasattr(field, "related_model") and field.related_model:
        return field.related_model._meta.concrete_model
