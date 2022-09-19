def related_model(field):
    """Return the concrete model a field references"""
    if hasattr(field, "related_model") and field.related_model:
        return field.related_model._meta.concrete_model
