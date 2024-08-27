# Frequently Asked Questions

## How does `django-pghistory` track everything?

By using [Postgres triggers](https://www.postgresql.org/docs/current/sql-createtrigger.html). In other words, historical event records are created in the database alongside the database operation, providing a reliable way to track events regardless of where it happens in your code.

## Are triggers supported by Django?

Triggers are not supported by Django directly, but `django-pghistory` uses [django-pgtrigger](https://github.com/Opus10/django-pgtrigger) to seamlessly integrate them with your Django models.

## How do I know triggers are working?

For those that are new to triggers and want additional confidence in their behavior, try the following:

* Always write tests. Perform updates on your tracked models in automated tests and verify that the event models are created.
* Run `python manage.py pgtrigger ls` to verify that all triggers are installed.
* Run `python manage.py check` to ensure that there are no missing migrations for triggers.

## What are the performance impacts?

Although triggers will be issuing additional SQL statements to write events, keep in mind that this happens within the database instance itself. In other words, writing events does not incur additional expensive round-trip database calls. This results in a reduced performance impact when compared to other history tracking methods implemented in software.

Note that currently `django-pghistory` uses row-level triggers, meaning a bulk update such as `Model.objects.update` over one hundred elements could perform one hundred queries within the database instance. We're planning to address this in a future version of `django-pghistory` by using statement-level triggers instead.

See the [Performance and Scaling](performance.md) section for tips and tricks on large history tables.

## How do I revert models?

Check out the [Reverting Objects](reversion.md) section.

## How do I only track a subset of models?

Add a condition to your tracker. See the [Conditional Tracking](event_tracking.md#conditional_tracking) subsection.

## How do I track models with concrete inheritance?

Currently concrete inheritance isn't well supported since `django-pghistory` simply snapshots the fields on the underlying table. Since concrete inheritance uses foreign keys to other tables, you'll need to set up trackers on all tables.

We plan to add a guide on this in the future.

## Can my event models be cascade deleted?

By default, event models use unconstrained foreign keys and instruct Django to do nothing when tracked models are deleted. This applies not only to the `pgh_obj` field that maintains a reference to the tracked model, but every foreign key that's tracked.

You can configure the `pgh_obj` key globally by setting the `settings.PGHISTORY_OBJ_FIELD` with the proper configuration or by setting it on a per-event-model basis with the `obj_field` option to [pghistory.track][].

See the [Configuring Event Models](event_models.md) section for details on how to set configuration options for event models.

## How can I make my event models immutable?

Use `append_only=True` for [pghistory.track][] or set `settings.PGHISTORY_APPEND_ONLY = True` to configure this as the default behavior globally. When configured, event models will have triggers that protect updates and deletes from happening, ensuring your event log is immutable.

## Can I query event models in my application?

Yes, one of the strengths of `django-pghistory` is that it uses structured event models that can be tailored to fit your application use case. By default, you can use `my_model_object.events` to query events of a particular model instance. `MyModel.pgh_event_model` also contains a reverence to the event model if you want to do table-level filtering over the events.

## How can I keep the values of fields that have been removed?

The short answer is that you can't. `django-pghistory` is designed to create event models that mirror the models they track, meaning the removal of a field in a tracked model will also be removed in the event model.

If you need data for fields that have been dropped, we recommend two approaches:

1. Make the field nullable instead of removing it.
2. Use [django-pgtrigger](https://github.com/Opus10/django-pgtrigger) to create a custom trigger that dumps a JSON record of the row at that point in time.

## How can I report issues or request features

Open a [discussion](https://github.com/Opus10/django-pghistory/discussions) for a feature request. You're welcome to pair this with a pull request, but it's best to open a discussion first if the feature request is not trivial.

For bugs, open an [issue](https://github.com/Opus10/django-pghistory/issues).

## How can I support the author?

By sponsoring [Wes Kendall](https://github.com/sponsors/wesleykendall). Even the smallest sponsorships are a nice motivation to maintain and enhance Opus10 libraries like django-pghistory.
