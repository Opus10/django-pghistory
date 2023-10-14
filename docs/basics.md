# Basics

Here we briefly overview some of the concepts of `django-pghistory` that are useful to understand to make reading the docs and using the tool easier.

## Triggers

[Postgres triggers](https://www.postgresql.org/docs/current/sql-createtrigger.html) are used to reliably store relevant historical changes.

A trigger is a function executed in the database when tables operations like inserts or updates happen. Triggers aren't natively supported by Django, so `django-pghistory` uses [django-pgtrigger](https://github.com/Opus10/django-pgtrigger) to register and install triggers.

Although it's not required to understand how triggers work to use `django-pghistory`, we recommend reading the [basics section of the django-pgtrigger docs](https://django-pgtrigger.readthedocs.io/en/latest/basics/) for an overview of `django-pgtrigger` and Postgres triggers in general.

Here are the main concepts to understand about triggers:

1. Like database indices, triggers are installed in migrations and are attached to database tables.
2. Triggers are functions that run in the database itself after inserts, updates, and deletes.
3. Triggers have access to copies of the rows being modified, known as the *old* and *new* rows.
4. Triggers can be conditionally executed based on the properites of the modified rows.

## Trackers

`django-pghistory` uses *trackers* to track model events. Trackers are an abstraction on top of triggers. For example, the default usage of [pghistory.track][] will use both a [pghistory.InsertEvent][] and [pghistory.UpdateEvent][] tracker to track changes to the model, both of which are installed as triggers in the database.

The default tracker configuration works for most use cases, however, users can specify trackers directly to [pghistory.track][] or override `settings.PGHISTORY_DEFAULT_TRACKERS` to modify behavior or track customized events. For example, one can track deletions with [pghistory.DeleteEvent][] or add conditions such as [pghistory.AnyChange][] or [pghistory.Q][] to only track events based on specific changes to models.

## Events

An *event* is a historical version of a model stored by a tracker. For example, the [pghistory.InsertEvent][] tracker stores values of tracked fields after an insert into an *event model*.

By default, event models are created by `django-pghistory` and dynamically added to the models module where your tracked model resides. Although you won't see them declared in your `models.py`, you will see them show up in migrations.

Let's revisit the quickstart example model for the basic usage:

```python
@pghistory.track()
class TrackedModel(models.Model):
    int_field = models.IntegerField()
    text_field = models.TextField()
```

This generates an event model named `TrackedModelEvent` that has every field from `TrackedModel` plus some additional `pgh_*`-labeled fields. The additional fields help distinguish events, reference the tracked object, and supply additional tracked context. We'll cover this in more detail later.

## Context

Event models can have free-form *context* attached to them using the [pghistory.context][] context manager and decorator. For example:

```python
with pghistory.context(user_id=1):
    # Do changes
```

Every event that happens in this context manager will now:

1. Use the same `pgh_context` foreign key in their associated event model.
2. Have access to the `user_id: 1` metadata that's stored in the [pghistory.models.Context][] model, which has a free-form `metadata` JSON field.

Context tracking allows for rich metadata to be attached to events and grouping changes together. The [pghistory.middleware.HistoryMiddleware][] middleware automatically attaches the authenticated user and URL of the request, and it's easy to sprinkle in [pghistory.context][] in your application to aggregate more metadata about a particular request.
