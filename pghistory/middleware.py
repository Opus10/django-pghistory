from typing import Any, Dict

from django.core.handlers.asgi import ASGIRequest as DjangoASGIRequest
from django.core.handlers.wsgi import WSGIRequest as DjangoWSGIRequest
from django.db import connection

import pghistory
from pghistory import config


class DjangoRequest:
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


class WSGIRequest(DjangoRequest, DjangoWSGIRequest):
    pass


class ASGIRequest(DjangoRequest, DjangoASGIRequest):
    pass


class HistoryMiddleware:
    """
    Annotates the user/url in the pghistory context.

    Add more context by inheriting the middleware and overriding the `get_context` method.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def get_context(self, request) -> Dict[str, Any]:
        user = (
            request.user._meta.pk.get_db_prep_value(request.user.pk, connection)
            if hasattr(request, "user") and hasattr(request.user, "_meta")
            else None
        )
        return {"user": user, "url": request.path}

    def __call__(self, request):
        if request.method in config.middleware_methods():
            with pghistory.context(**self.get_context(request)):
                if isinstance(request, DjangoWSGIRequest):  # pragma: no branch
                    request.__class__ = WSGIRequest
                elif isinstance(request, DjangoASGIRequest):  # pragma: no cover
                    request.__class__ = ASGIRequest

                return self.get_response(request)
        else:
            return self.get_response(request)
