from django import template
from pghistory.models import AggregateEvent


register = template.Library()


@register.simple_tag(takes_context=True)
def get_aggregate_events(context):
    return (
        AggregateEvent.objects.target(context["object"])
        .order_by("pgh_created_at")
        .select_related("pgh_context")
    )
