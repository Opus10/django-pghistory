.. _tutorial:

Tutorial
========

There are two main components of ``django-pghistory``:

1. Event. Events are configured to track various historical events
   that happen in an application. ``django-pghistory`` has
   several utilities for automatically tracking events
   based off of changes in the database. Events range from
   snapshotting all model changes, tracking specific events based
   on changes in the database, and still allowing users to manually
   track events that cannot be expressed at a database level. Users
   have flexibility in how event models are structured.
2. Context. An application can track as many events across as many
   models as desired, which can result in multiple tables and
   events for even a single request. ``django-pghistory`` provides
   the ability to contextualize all of these events and group
   them under the same context. Along with this, the application
   can also add as much free-form metadata to the context of events
   as desired. ``django-pghistory`` comes with middleware that
   will automatically group events in a request under the
   same context and annotate additional information about the
   events (e.g. the URL and the authenticated user).

These two concepts, along with advanced usage examples,
will be covered in more detail over the tutorial.

Tracking Snapshots of Models When Fields Change
-----------------------------------------------

We dive into ``django-pghistory``'s event tracking by first showing
how to configure it to track any changes to relevant models. After
these examples, we'll dive deeper into how to configure ``django-pghistory``
to automatically track custom events and also show examples of how
to manually track events in an application.

The `pghistory.track` decorator is the primary interface for
configuring event tracking. Using this decorator not only configures
event tracking for a model, but it will also create another tracking
model dynamically that tracks all changes.

For example, let's say that we have a ``TestModel`` like so:

.. code-block:: python

    from django.db import models

    class TestModel(models.Model):
        int_field = models.IntegerField()
        char_field = models.CharField(max_length=16)

Tracking model changes can be configured with:

.. code-block:: python

    import pghistory


    @pghistory.track(
        pghistory.Snapshot('test_model.snapshot')
    )
    class TestModel(models.Model):
        ...

Here's an overview of what's going on above:

1. We've registered the ``test_model.snapshot`` event to be tracked.
   This is a `pghistory.Snapshot` event that will snapshot the model
   when it is created and anytime a field is updated.
2. Tracking happens automatically at the database level via
   `Postgres Triggers <https://www.postgresql.org/docs/12/sql-createtrigger.html>`__.
   Triggers are installed when migrations run.
3. The tracked changes are stored in an automatically-generated tracking
   model. By default, the tracking model has a nearly identical structure
   as the model being tracked, along with some additional metadata inserted
   by ``django-pghistory``. These models will appear when calling
   ``manage.py makemigrations``, and other parameters to
   `pghistory.track` can be configured to limit which fields are tracked
   among other things. Every event tracked in this table will have a
   label of ``test_model.snapshot``.

For this particular scenario, the automatically-generated event
model looks like this:

.. code-block:: python

    class TestModelEvent(pghistory.models.Event):
        pgh_obj = models.ForeignKey(TestModel, on_delete=models.DO_NOTHING, related_name='event')
        pgh_label = models.TextField()
        pgh_context = models.ForeignKey('pghistory.Context', null=True, on_delete=models.DO_NOTHING, related_name='+')
        pgh_created_at = models.DatetimeField(auto_now_add=True)

        id = models.IntegerField()
        int_field = models.IntegerField()
        char_field = models.CharField(max_length=16)


When ``TestModel`` is inserted or updated, a ``TestModelEvent``
is created with the new values of the ``TestModel`` object.
Events fire only when fields change, so no event will be stored if
any empty update happens. This
provides a complete history of all of the values of that particular model.
One can query all updates to the model with ``test_model_instance.event.all()``.

The ``pgh_obj`` is a foreign key that references the original
object. This foreign key can be modified via the ``fk_obj`` parameter
to `pghistory.track`. See `pghistory.track` for more
information.

The ``pgh_context`` is a foreign key that points to context about the historical
event. The context object, along with tracking free-form metadata from the app,
allows grouping of similar events. More on this later.

Since the event model is automatically tracking fields, it
will also be migrated whenever the original model is changed.
It is up to the user to write appropriate data migrations for these
circumstances.

.. note::

    You may have noticed the use of ``DO_NOTHING`` on the deletion of
    foreign keys. By default, all ``django-pghistory`` event models
    create foreign keys that are unconstrained, even for the foreign keys
    of the tracked model. This helps ensure
    the tracked values are accurate for the point in time at which
    they were tracked and that Django does not try to modify them
    during deletions. It is up to the user to handle referential integrity
    errors from tracking models as a result or to override the generated
    tracking models if referential integrity is important. More on
    this in a later section.

``django-pghistory`` provides the ability to specify tracking for only
a subset of fields, or even potentially having different event models
for different field updates. For example, this will create two
different event models: one for changes to ``int_field`` and one
for changes to ``char_field``:

.. code-block:: python

    @pghistory.track(pghistory.Snapshot('test_model.int_field_snapshot'), fields=['int_field'])
    @pghistory.track(pghistory.Snapshot('test_model.char_field_snapshot'), fields=['char_field'])
    class TestModel(models.Model):
        ...


In the above, two different tracking models would be created with the following
structure:

.. code-block:: python

    class TestModelIntFieldEvent(pghistory.models.Event):
        pgh_obj = models.ForeignKey(TestModel, on_delete=models.DO_NOTHING, related_name='int_field_event')
        pgh_label = models.TextField()
        pgh_context = models.ForeignKey('pghistory.Context', null=True, on_delete=models.DO_NOTHING, related_name='+')
        pgh_created_at = models.DatetimeField(auto_now_add=True)

        int_field = models.IntegerField()

    class TestModelCharFieldEvent(pghistory.models.Snapshot):
        pgh_obj = models.ForeignKey(TestModel, on_delete=models.DO_NOTHING, related_name='char_field_event')
        pgh_label = models.TextField()
        pgh_context = models.ForeignKey('pghistory.Context', null=True, on_delete=models.DO_NOTHING, related_name='+')
        pgh_created_at = models.DatetimeField(auto_now_add=True)

        char_field = models.CharField(max_length=16)


The ``fields`` argument to `pghistory.track` can take any combination of
fields that should be snapshot when any field in the group is changed.

Tracking Specific Model Events
------------------------------

Oftentimes changes of specific fields to specific values directly
corresponds to events in an application. For example, the creation of a
new user could mean that a new user has signed up. The change of a ``status``
field of a model might indicate a model has progressed to a new stage.

Similar to the `pghistory.Snapshot` event, ``django-pghistory`` comes
with some utilities for automatically storing events based on conditional
changes in the database. For example, let's take our previous example
of storing an event when a user is created:

.. code-block:: python

    @pghistory.event(
        pghistory.AfterInsert('user.create'),
    )
    class User(models.Model):
        username = models.CharField(max_length=64)

In the above, we've registered a `pghistory.AfterInsert` event. When
an insert happens, an event will be created with the label of ``user.create``.

The event model is generated in an identical way to the previous snapshot
examples. By default, every value of the model will be snapshot alongside
the event label. If it isn't important to have all of this additional
information alongside the event, one can override this behavior with the
``fields`` argument. For example, the following will only track the ``username``
field when a ``user.create`` event happens:

.. code-block:: python

    @pghistory.track(
        pghistory.AfterInsert('user.create'),
        fields=['username']
    )
    class User(models.Model):
        username = models.CharField(max_length=64)
        password = models.PasswordField()

``django-pghistory`` comes with five utility classes for automatically
creating events based on changes in rows:

1. `pghistory.AfterInsert`: For creating an event based on the fields
   after an insert. Values from the ``NEW`` row (from the Postgres trigger)
   will be stored.
2. `pghistory.BeforeUpdate`: For creating an event based on the fields
   before the update. Values from the ``OLD`` row will be stored.
3. `pghistory.AfterUpdate`: For creating an event based on the fields
   after an update. Values from the ``NEW`` row will be stored.
4. `pghistory.BeforeDelete`: For creating an event based on the fields
   before a delete. Values from the ``OLD`` row will be stored.
5. `pghistory.AfterInsertOrUpdate`: A helper to create an event after
   an insert or an update based on the rows after the operation.
   Values from the ``NEW`` row will be stored.

Similar to snapshots, these five event types directly map to Postgres triggers
that are installed in the database, meaning
that they all can be given a ``condition`` argument to specify when they
should be fired. It is up to the application developer to understand
when it makes sense to snapshot the ``OLD`` or the ``NEW`` row
when using `pghistory.BeforeUpdate` or `pghistory.AfterUpdate`.

Manually Tracking Events
------------------------

Sometimes it is not possible to express an event based on a series
of changes to a model. `pghistory.create_event` can be used for
circumstances where the event needs to be manually instrumented.
These events must still be declared with the model though, for
example:

.. code-block:: python

    @pghistory.track(
        pghistory.Event('user.create'),
        fields=['username']
    )
    class User(models.Model):
        username = models.CharField(max_length=64)
        password = models.PasswordField()


In the above, we have defined the ``user.create`` event like before, but
it will not automatically be created. We will have to instrument our
code to create the event before a user is created:

.. code-block:: python


    user = User.objects.create(...)
    pghistory.create_event(user, label='user.create')

.. note::

    Manually-created events will still be linked with context if
    context tracking has been enabled. More on context tracking
    in a later section.

Creating a Custom Event Model
-----------------------------

``django-pghistory`` also provides the ability for the user to create
a custom event model if one needs to override field declarations
or add custom attributes to fields (e.g. an index).
`pghistory.get_event_model` is used like so:


.. code-block:: python

      class TestModel(models.Model):
          ...


      class MySnapshotModel(pghistory.get_event_model(
          TestModel,
          pghistory.Snapshot('test_model.snapshot'),
          fields=['int_field'],
      )):
          pass


The call signature for `pghistory.get_event_model` is almost
identical to `pghistory.track` with the exception that the
tracked model is the first argument.

Grouping Changes and Metadata
-----------------------------

By default, all ``django-pghistory`` event models come with
a ``pgh_context`` foreign key that points to the `pghistory.models.Context`
object associated with the event. The `pghistory.models.Context`
model has a UUID ``id`` primary key field and a ``metadata`` JSON field.
In order to group changes under the same context, use `pghistory.context`:

.. code-block:: python

    with pghistory.context(key='val'):
        # Do changes here...


When using `pghistory.context`, all contained changes will point to the
same ``Context`` object. The ``Context`` object in this example will also
have ``{"key": "val"}`` in its metadata.

Context can be added anywhere in an application. For example, imagine one
has a core system of their application that imports data and they want
to add context about a file that was imported to any change that happens.
This can be done by entering ``pghistory.context(additional='metadata')``
before the import happens and attaching additional metadata.
The metadata will be accumulated into the shared ``Context`` object associated
with all changes since the root `pghistory.context` call happened.

Normally an application will group changes together at the following
levels of granularity:

1. Request. Changes for an entire POST request can be grouped together by
   using the middleware in `pghistory.middleware.HistoryMiddleware`. The
   default middleware attaches the authenticated user and the URL of the
   request to the context metadata. Note: be sure to add the middleware
   after ``django.contrib.auth`` in order to track the correct user.
2. Management Command. If users run a management command outside of a
   request, one can instrument ``manage.py`` with `pghistory.context`
   to apply the same context for all changes in the management command.
3. Task. When running periodic or asynchronous tasks, one can instrument
   the core task objects to contextualize all changes in the same task
   run.

.. note::

  If one does not wrap database changes in `pghistory.context`, the
  associated events will have a ``pgh_context`` set to ``None``.
  If one directly connects to the database and runs raw SQL, for example,
  the changes would still be tracked, but there would be missing context
  as to why the change happened.

``django-pghistory`` context is meant to group together events
and bring more clarity around why a particular event happened in an
application. It is ultimately up to the application developers to
decide what core sets of free-form metadata should be tracked alongside
structured events.


Advanced Usage Examples
-----------------------

Tracking Third-Party Model Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``django-pghistory`` can track changes to third-party models like Django's
``User`` model. There are two things to keep in mind when tracking
events to a model outside of your application:

1. You must register the tracking in the ``.ready()`` of an app config
   in your project.
2. You must provide an app label that is inside of your project to
   use for the generated model. This is
   required to ensure that migrations for the event model are created
   inside of your project and not in a folder of a third-party app.

Here's an example of configuring events for the Django ``User`` model:


.. code-block:: python

  import django.apps
  from django.contrib.auth import get_user_model

  import pghistory


  class MyAppConfig(django.apps.AppConfig):
      name = 'my_app'

      def ready(self):
          User = get_user_model()
          # Snapshot the user model and exclude password updates
          pghistory.track(
              pghistory.Snapshot('user.snapshot'),
              exclude=['password'],
              app_label='my_app'
          )(User)


Tracking Many-To-Many Events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Events in many-to-many fields, such as user groups or permissions,
can be configured by tracking the "through" model of the many-to-many
relationship. When creating a many-to-many relationship, Django
automatically generates a "through" model that is populated based
on changes to the many-to-many field (and one can override this behavior
with their own custom "through" model).

``django-pghistory``'s tracking functions can be called manually on
the "through" model or used as a decorator on any custom "through" models.
Here we show an example of how to track group "add" and "remove" events
for Django's ``User`` model.

As discussed in the previous section, we need to set up a ``.ready()``
handler in an app config of our project to track third-party model changes
and pass it a custom ``app_label`` to use.
Here we reference the "through" model with ``User.groups.through``:

.. code-block:: python

  import django.apps
  from django.contrib.auth import get_user_model
  from django.db import models


  class MyAppConfig(django.apps.AppConfig):
      name = 'my_app'

      def ready(self):
          User = get_user_model()
          # Track events to user group relationships
          pghistory.track(
              pghistory.AfterInsert('group.add'),
              pghistory.BeforeDelete('group.remove'),
              obj_fk=None,
              app_label='my_app',
          )(User.groups.through)

Two events are set up to track additions and deletions to the "through" model,
which will in turn track every time a user is added or removed from a group.

.. note::

   Django does not allow foreign keys to auto-generated "through" models.
   Setting ``obj_fk=None`` will create an event model that does not contain
   a reference to the original "through" model.

Assuming one has created and executed migrations, the following code
will show tracked changes to user group relationships:

.. code-block:: python

  # Note: this is pseudo-code
  >>> user = User.objects.create_user('username')
  >>> group = Group.objects.create(name='group')
  >>> user.groups.add(group)
  >>> user.groups.remove(group)
  >>> print(my_app_models.UserGroupsEvent.objects.values('pgh_label', 'user', 'group'))

  [
    {'user': user.id, 'group': group.id, 'pgh_label': 'group.add'},
    {'user': user.id, 'group': group.id, 'pgh_label': 'group.remove'},
  ]


Configuring Context Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When using `pghistory.middleware.HistoryMiddleware`, all POST, PUT,
and PATCH requests
will automatically be tracked with `pghistory.context` and events will
reference the same context object in their associated models (i.e.
the ``pgh_context`` foreign key). By default, the
authenticated user is added as the ``user`` key and the URL is added
as the ``url`` key.

.. note::

    Packages like ``django-rest-framework`` add the user to the ``request``
    object in the view layer. `pghistory.middleware.HistoryMiddleware`
    modifies the Django request object so that any changes to ``request.user``
    in the view lifecycle will be captured.

Users, however, can enter `pghistory.context` at any point in their
application code to attach more information to the context.

For example, this will attach an ``is_import`` flag whenever an import
of data is triggered:

.. code-block:: python

    import pghistory

    @pghistory.context(is_import=True)
    def import_data():
        ...

Note that ``is_import=True`` is attached to the current context. Events
will be grouped together under the same context based on the highest level
at which `pghistory.context` was started. So, for example, if an import
is issued in a request and the middleware is configured, all changes in
the request will have an ``is_import`` flag in their context. If the
middleware was not enabled and this was the first time the application entered
`pghistory.context`, only changes inside of this function would be grouped
under the same context.

If one desires to only add context if a parent function has already entered
`pghistory.context` (e.g. the middleware), one can call `pghistory.context`
directly:

.. code-block:: python

    pghistory.context(my='context')

The context from the above example will *not* be added if a parent process
has not entered `pghistory.context`.

It is up to the application developer to determine the levels of granularity
at which history should be grouped together and how this will be used in
their application. A general rule of thumb is to group changes by
web requests. Things outside of web requests, such as Celery tasks or management
commands, can be instrumented at their own levels individually.

Celery Tasks
############

One can override the Celery base task like so to group all
task events under the same context with the same task name:

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


Management Commands
###################

To capture all events issued under a management command, one
can instrument ``manage.py`` like so:

.. code-block:: python

    #!/usr/bin/env python
    import contextlib
    import sys

    import pghistory


    if __name__ == "__main__":

        if (
            len(sys.argv) > 1
            and not sys.argv[1].startswith('runserver')
        ):
            # Group history context under the same management command if
            # we aren't running a server.
            history_context = pghistory.context(command=sys.argv[1])
        else:
            # Otherwise, history will be grouped together every request
            # in the middleware
            history_context = contextlib.ExitStack()

        import configurations.management

        with history_context:
            configurations.management.execute_from_command_line(sys.argv)


In the above, we ignore tracking context for ``runserver`` commands. Otherwise
every single change in a development session would be grouped under the
same context.

.. note::

    This example uses `django-configurations <https://github.com/jazzband/django-configurations>`__
    for settings management. The default ``manage.py`` generated by Django
    will look different, but ``pghistory`` instrumentation will be the
    same.
