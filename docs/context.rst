.. _context:

Collecting Context
==================

By default, all ``django-pghistory`` event models come with
a nullable ``pgh_context`` foreign key to the `pghistory.models.Context` model.
This model has a ``metadata`` JSONField that is populated by calling
`pghistory.context`.

Using ``pghistory.context``
---------------------------

`pghistory.context` can be used as a decorator or context manager. When it
is entered the first time, it creates a session with a UUID, collects
metadata, and stores this metadata in the ``metadata`` field of
the `pghistory.models.Context` model. Any nested calls will add or
override the metadata for that session.

For example, here we've started context collection and added a few
keys and values in the midst of database queries:

.. code-block:: python

    with pghistory.context(key1="val1"):
        # Do changes...

        with pghistory.context(key2="val2"):
            # Do more changes...

In the above example, all events will reference the same ``Context`` object with
``metadata`` of:

.. code-block:: python

    {
        "key1": "val1",
        "key2": "val2",
    }

Remember, context collection allows you to not only track free-form metadata, but
also group events together.
Normally an application will group events for each request. Tasks like management
commands or Celery jobs can also be instrumented. We'll cover
these examples later.

If you'd like to avoid starting a context session and only
attach context to a pre-existing session, call `pghistory.context`
as a function. If `pghistory.context` hasn't been previously entered as a decorator
or context manager, the context will not be stored.

.. tip::

    If you're attaching context that cannot be serialized to JSON, override
    the default JSON encoder class with ``settings.PGHISTORY_JSON_ENCODER``.
    It defaults to ``django.core.serializers.json.DjangoJSONEncoder``.

.. _middleware:

Middleware
----------

``django-pghistory`` comes with the `pghistory.middleware.HistoryMiddleware`
middleware to add context to requests.
It adds the URL of the request to the ``url`` attribute
and the authenticated user ID to the ``user`` attribute.

Since the middleware starts context collection at the beginning of the request,
all tracked changes in the request will reference the same context.

Use ``settings.PGHISTORY_MIDDLEWARE_METHODS`` to configure the requests
that are tracked. It defaults to
``("GET", "POST", "PUT", "PATCH", "DELETE")``.

Management Commands
-------------------

To capture all events issued under a management command,
instrument ``manage.py`` like so:

.. code-block:: python

    #!/usr/bin/env python
    import contextlib
    import os
    import sys

    import pghistory


    if __name__ == "__main__":
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
        from django.core.management import execute_from_command_line

        if (
            len(sys.argv) > 1
            and not sys.argv[1].startswith("runserver")
        ):
            # Group history context under the same management command if
            # we aren't running a server.
            history_context = pghistory.context(command=sys.argv[1])
        else:
            history_context = contextlib.ExitStack()

        with history_context:
            execute_from_command_line(sys.argv)


Above we ignore tracking context for ``runserver`` commands. Otherwise
every single change in a development session would be grouped under the
same context.

Celery Tasks
------------

Override the Celery base task to group all
task events:

.. code-block:: python

    import celery
    import pghistory


    class Task(celery.Task):
        def __call__(self, *args, **kwargs):
            with pghistory.context(task=self.name):
                return super().__call__(*args, **kwargs)


    # Override the celery task decorator for your application
    app = create_celery_app('my-app')
    task = app.task(base=Task)
