.. _basics:

Basics
======

Here we briefly overview some of the concepts of ``django-pghistory`` that
are useful to understand to make reading the docs and using the tool easier.

Triggers
--------

`Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__ are used
to reliably store relevant historical changes.

A trigger is a function executed in the database when tables operations like inserts or updates happen.
Triggers aren't natively supported by Django, so ``django-pghistory`` uses
`django-pgtrigger <https://github.com/Opus10/django-pgtrigger>`__ to
register and install triggers.

Although it's not required to understand how triggers work to use ``django-pghistory``, we recommend
reading the `basics section of the django-pgtrigger docs <https://django-pgtrigger.readthedocs.io/en/4.5.3/basics.html>`__
for an overview of ``django-pgtrigger`` and Postgres triggers in general.

Here are the main concepts to understand about triggers:

1. Like indices, triggers are installed in migrations and are attached to database tables.
2. Triggers can be configred to run based on insert, update, and delete operations on a table.
3. Triggers have access to copies of the rows being modified, known as the *old* and *new* rows.
4. Triggers can be conditionally executed based on the properites of the modified rows.

Trackers
--------

``django-pghistory`` provides *trackers* to track historical changes. Trackers are an abstraction on top
of triggers. For example, `pghistory.Snapshot` will install a trigger for inserts
and another for updates, ensuring all versions of models are stored when they change.

There are several other trackers that we'll go over later for more advanced use cases:
`pghistory.AfterInsert`, `pghistory.AfterUpdate`, `pghistory.BeforeUpdate`, `pghistory.AfterInsertOrUpdate`,
and `pghistory.BeforeDelete`. These trackers, like `pghistory.Snapshot`, are simply installing triggers
for pre-defined database operations.

Events
------

An *event* is a historical record stored by trackers. For example,
the `pghistory.Snapshot` tracker stores *snapshot* events.
Event models mirror the tracked model and add a few additional tracking fields, all of which
are configurable.

Let's revisit the quickstart example model:

.. code-block:: python

    @pghistory.track(pghistory.Snapshot("snapshot"))
    class TrackedModel(models.Model):
        int_field = models.IntegerField()
        text_field = models.TextField()

This generates an event model named ``TrackedModelEvent`` that has every field from
``TrackedModel`` plus some additional ``pgh_*``-labeled fields.
The additional fields help distinguish events, reference the tracked
object, and supply additional tracked context. We'll cover these fields in more detail later.

Context
-------

Event models can have free-form *context* attached to them using the `pghistory.context` context manager and decorator.
For example:

.. code-block::

    with pghistory.context(user_id=1):
        # Do changes

Every event will now point to the same context entry, which contains a JSON field with ``user: 1`` in it. Context tracking
is implemented by propagating local Postgres variables in the executed SQL, meaning no additional queries happen
when storing context from your application.

Context tracking allows for rich metadata to be attached to events. The ``django-pghistory``
middleware automatically attaches the authenticated user and URL of the request, and it's easy to sprinkle in
`pghistory.context` when needed in your application.
