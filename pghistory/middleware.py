from django.core.handlers.asgi import ASGIRequest as DjangoASGIRequest
from django.core.handlers.wsgi import WSGIRequest as DjangoWSGIRequest

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
            pghistory.context(user=value.pk if value and hasattr(value, "pk") else None)

        return super().__setattr__(attr, value)


class WSGIRequest(DjangoRequest, DjangoWSGIRequest):
    pass


class ASGIRequest(DjangoRequest, DjangoASGIRequest):
    pass


def HistoryMiddleware(get_response):
    """
    Annotates the user/url in the pghistory context.
    """

    def middleware(request):
        if request.method in config.middleware_methods():
            user = (
                request.user.pk
                if hasattr(request, "user") and hasattr(request.user, "pk")
                else None
            )
            with pghistory.context(user=user, url=request.path):
                if isinstance(request, DjangoWSGIRequest):  # pragma: no branch
                    request.__class__ = WSGIRequest
                elif isinstance(request, DjangoASGIRequest):  # pragma: no branch
                    request.__class__ = ASGIRequest

                return get_response(request)
        else:
            return get_response(request)

    return middleware
