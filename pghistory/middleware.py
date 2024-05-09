from django.core.handlers.wsgi import WSGIRequest as DjangoWSGIRequest
from django.db import connection

import pghistory
from pghistory import config


class WSGIRequest(DjangoWSGIRequest):
    """
    Although Django's auth middleware sets the user in middleware,
    apps like django-rest-framework set the user in the view layer.
    This creates issues for pghistory tracking since the context needs
    to be set before DB operations happen.

    This special WSGIRequest updates pghistory context when
    the request.user attribute is updated.
    """

    def __setattr__(self, attr, value):
        if attr == "user":
            user = (
                value._meta.pk.get_db_prep_value(value.pk, connection)
                if value and hasattr(value, "_meta")
                else None
            )
            pghistory.context(user=user)

        return super().__setattr__(attr, value)


def HistoryMiddleware(get_response):
    """
    Annotates the user/url in the pghistory context.
    """

    def middleware(request):
        if request.method in config.middleware_methods():
            user = (
                request.user._meta.pk.get_db_prep_value(request.user.pk, connection)
                if hasattr(request, "user") and hasattr(request.user, "_meta")
                else None
            )
            with pghistory.context(user=user, url=request.path):
                if isinstance(request, DjangoWSGIRequest):  # pragma: no branch
                    request.__class__ = WSGIRequest

                return get_response(request)
        else:
            return get_response(request)

    return middleware
