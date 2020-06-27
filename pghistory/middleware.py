from django.core.handlers.wsgi import WSGIRequest as DjangoWSGIRequest

import pghistory


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
        if attr == 'user':
            pghistory.context(user=value.id if value else None)

        return super().__setattr__(attr, value)


def HistoryMiddleware(get_response):
    """
    Tracks POST requests and annotates the user/url in the pghistory
    context.
    """

    def middleware(request):
        if request.method in ('POST', 'PUT', 'PATCH'):
            with pghistory.context(
                user=request.user.id if hasattr(request, 'user') else None,
                url=request.path,
            ):
                if isinstance(request, DjangoWSGIRequest):  # pragma: no branch
                    request.__class__ = WSGIRequest

                return get_response(request)
        else:
            return get_response(request)

    return middleware
