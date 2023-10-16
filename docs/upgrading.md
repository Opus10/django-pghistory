# Upgrading

## Version 2

To upgrade to version 2, the majority of people can simply run `python manage.py makemigrations` to make the migrations for the triggers. If, however, you are tracking third-party models, you will need to register trackers on proxy models. Otherwise trigger migrations will be created outside of your project.

**Important** - Please be sure you have `django-pgtrigger>=4.5` installed, otherwise `django-pghistory` might be susceptible to some migration-related bugs

For example, this is how you can track changes to Django's user model:

```python
# Track the user model, excluding the password field
@pghistory.track(
    pghistory.Snapshot("user.snapshot"),
    exclude=["password"],
)
class UserProxy(User):
    class Meta:
        proxy = True
```

The same syntax is also used for default many-to-many "through" models. For example, this is how one tracks changes to group add/remove events on the user model:

```python
from django.contrib.auth.models import User
import pghistory

# Track add and remove events to user groups
@pghistory.track(
    pghistory.AfterInsert("group.add"),
    pghistory.BeforeDelete("group.remove"),
    obj_fk=None,
)
class UserGroups(User.groups.through):
    class Meta:
        proxy = True
```

### Maintaining legacy behavior

If you want to disable `django-pgtrigger` integration with migrations entirely, set `settings.PGTRIGGER_MIGRATIONS` to `False`. Setting this along with `settings.PGTRIGGER_INSTALL_ON_MIGRATE` to `True` will preserve the legacy behavior of how triggers were installed. It is not recommend to do this since migrations fix legacy trigger installation bugs.

## Version 2.5

Although version 2.5 remains backwards compatible, it deprecates arguments and functionality in preparation for removal in version 3.
Below are the deprecated changes.

### `pghistory.track`

* The `obj_fk` argument is deprecated in favor of `obj_field`. The new argument must be supplied a [pghistory.ObjForeignKey][] instance. See [Configuring Event Models](event_models.md) for more information on the new configuration methods.
* The `context_fk` argument is deprecated in favor of `context_field`. The new argument must be a [pghistory.ContextForeignKey][]. If you're denormalizing context, it must be a [pghistory.ContextJSONField][] argument. See [Configuring Event Models](event_models.md) for more information on the new configuration methods and context denormalization.
* The `related_name` argument is deprecated. Supply the `related_name` argument to the instance of the `obj_field` argument. For example, `obj_field=pghistory.ObjForeignKey(related_name="events")`.

### `pghistory.get_event_model`

* Deprecated and renamed to [pghistory.create_event_model][].
* Along with the changed arguments from [pghistory.track][], the `name` argument has been deprecated in favor of `model_name`.

### `pghistory.models.AggregateEvent`

* Deprecated in favor of [pghistory.models.Events][]. The core fields from the original model are there with other additions and renamed fields. See [Aggregating Events and Diffs](aggregating_events.md) for more information.
* `objects.target` is deprecated and renamed to `objects.references`
* Additional fields on proxy models must use [pghistory.ProxyField][] to declare the field. See [Querying Context as Structured Fields](aggregating_events.md#events_proxy) for more information.

### `pghistory.Event`

* Deprecated and renamed to [pghistory.Tracker][].

### `pghistory.DatabaseEvent`

* Deprecated and renamed to `pghistory.DatabaseTracker`.

## Version 3

There are two big breaking pieces of version three:

1. The deprecated code from version 2.5 was removed, meaning only the new configuration system and hierachy for event models can be used. See [configuring event models](event_models.md) for more information on how you can configure the default behavior of your event models using both settings and arguments to [pghistory.track][]
2. The `pghistory.Snapshot` tracker and every previous event tracker class was consolidated primarily into [pghistory.InsertEvent][], [pghistory.UpdateEvent][], and [pghistory.DeleteEvent][]. [pghistory.track][] also no longer requires an event tracker. It uses the default configuration. See the "New trackers" section below for how to migrate.

There are other subtle breaking changes:

1. New default `pgh_label` label values for event trackers
2. The replacement of the `pghistory.Changed` utility for creating conditions based on changes.
3. Minor query behavior changes for the [pghistory.models.Events][] event aggregation proxy model.

We cover all of these changes here in more detail, along with how to migrate or preserve old behavior.

### Deprecated code removed

- `pghistory.Event` was removed. Use [pghistory.Tracker][] instead as the base class for custom trackers.
- `pghistory.DatabaseEvent` was removed. Use [pghistory.RowEvent][] instead to customize row-level database events. Note that [pghistory.UpdateEvent][], [pghistory.InsertEvent][], and [pghistory.DeleteEvent][] may already suite needs of previous `pghistory.DatabaseEvent` usage.
- `pghistory.get_event_model` was removed. Use [pghistory.create_event_model][] instead.
- The `obj_fk` argument to `pghistory.create_event_model` and `pghistory.track` was removed. Supply a [pghistory.ObjForeignKey][] object to `obj_field` instead.
- The `context_fk` argument to `pghistory.create_event_model` and `pghistory.track` was removed. Supply a [pghistory.ContextForeignKey][] object to the`context_field` argument instead.
- The `related_name` argument to `pghistory.create_event_model` and `pghistory.track` was removed. Use the `related_name` argument of the [pghistory.ObjForeignKey][] class supplied to the `object_field` argument instead.
- The `name` argument to`pghistory.create_event_model` was removed. Use `model_name` instead.

### New trackers

Previously `django-pghistory` had the following trackers:

- `pghistory.Snapshot` for creating events based on inserts and updates to any tracked fields.
- `pghistory.AfterInsert`, `pghistory.AfterInsertOrUpdate`, `pghistory.AfterUpdate`, `pghistory.BeforeDelete`, `pghistory.BeforeUpdate`, and `pghistory.BeforeUpdateOrDelete` for customizing event tracking.

All trackers have been replaced with [pghistory.InsertEvent][], [pghistory.UpdateEvent][], and [pghistory.DeleteEvent][]. These utility classes already have defaults configured, and one can use [pghistory.RowEvent][] to have no defaults configured for a custom row-level event.

For example, `pghistory.track(pghistory.Snapshot())` is the same as doing `pghistory.track(pghistory.InsertEvent(), pghistory.UpdateEvent())`. [pghistory.UpdateEvent][], like the update trigger installed previously by `pghistory.Snapshot`, conditionally tracks updates only to the tracked model fields.

!!! note

    Previous usage of `pghistory.track(pghistory.Snapshot())` can simply be replaced with `pghistory.track()`. See the next section
    for more details.

Trackers other than `pghistory.Snapshot` had no conditions configured by default. For example, `pghistory.AfterUpdate` would fire after every update of the tracked model regardless of what fields were being tracked in the event model. This is *not* the default behavior for [pghistory.UpdateEvent][], which only fires if tracked fields change. One must manually do `pghistory.UpdateEvent(condition=None)` to override this behavior or use a bare [pghistory.RowEvent][]

With these subtle changes in mind, let's go over how to re-create the exact tracking behavior of the previous custom trackers:

- `pghistory.track(pghistory.AfterInsert())` = `pghistory.track(pghistory.InsertEvent())`
- `pghistory.track(pghistory.AfterInsertOrUpdate())` = `pghistory.track(pghistory.InsertEvent(), pghistory.UpdateEvent(condition=None))`
- `pghistory.track(pghistory.AfterUpdate())` = `pghistory.track(pghistory.UpdateEvent(condition=None))`
- `pghistory.track(pghistory.BeforeDelete())` = `pghistory.track(pghistory.DeleteEvent)`
- `pghistory.track(pghistory.BeforeUpdate())` = `pghistory.track(pghistory.UpdateEvent(row=pghistory.Old, condition=None))`
- `pghistory.track(pghistory.BeforeUpdateOrDelete())` = `pghistory.track(pghistory.UpdateEvent(row=pghistory.Old, condition=None), pghistory.DeleteEvent())`

### New default trackers and default arguments to `pghistory.track`

Previously one had to provide a tracker to [pghistory.track][], which was usually `pghistory.Snapshot`. Now one can use [pghistory.track][] with no arguments. The trackers default to `settings.PGHISTORY_DEFAULT_TRACKERS`, and this setting defaults to `(pghistory.InsertEvent, pghistory.UpdateEvent())`.

In other words, if you were using `pghistory.track(pghistory.Snapshot())` and no other trackers, you can now just do `pghistory.track()`.

### New default label names

For those depending on the `pgh_label` field of events, the default label names have changed.

Previously `pghistory.Snapshot` would default to using "snapshot" as the label for both insert and updates. The new tracker classes default to using different labels as follows:

- [pghistory.InsertEvent][] uses the "insert" label
- [pghistory.UpdateEvent][] uses the "update" label
- [pghistory.DeleteEvent][] uses the "delete" label

In other words, if you were previously using `pghistory.track(pghistory.Snapshot())` and migrate to calling `pghistory.track()` with the default trackers, your new `pgh_label` values in your events will be "insert" and "update" depending on what tracker made the event.

If your application depends on these labels being named "snapshot", configure the following in your settings to retain the original behavior:

```python
PGHISTORY_DEFAULT_TRACKERS = (
    pghistory.InsertEvent("snapshot"),
    pghistory.UpdateEvent("snapshot")
)
```

### Replacement of `pghistory.Changed`

The `pghistory.Changed` class was a utility for creating conditions based on changes to the event model. This helped one more succinctly create conditions for trackers like `pghistory.BeforeUpdate`.

This condition utility is now a first-class citizen in `django-pgtrigger`, which now offers utility classes to create conditions based on field changes. These classes have been mirrored in `django-pghistory`:

- [pghistory.AnyChange][]: Fires when any supplied fields change.
- [pghistory.AnyDontChange][]: Fires when any supplied fields don't change.
- [pghistory.AllChange][]: Fires when all supplied fields change.
- [pghistory.AllDontChange][]: Fires when all supplied fields don't change.

The conditions have the following behavior:

- If no fields are supplied, they default to the ones being tracked.
- One can use `exclude` to exclude fields instead of supplying a list of fields.
- One can use `exclude_auto` to automatically exclude `auto_now` and `auto_now_add` datetime fields from conditions.

By default, [pghistory.UpdateEvent][] uses [pghistory.AnyChange][] as its condition.

### Query difference in `pghistory.models.Events` proxy aggregate model

When using [pghistory.models.Events][] to aggregate events, one has the ability to render a diff between the current and previous event of the same event model. Previously the current and previous event would be determined by both the event model and the `pgh_label` of events.

Now the current and previous events are only determined only by those that share the same event model. The default usage of [pghistory.track][] (i.e. formerly `pghistory.track(pghistory.Snapshot())`) has no real breaking changes, but usage of multiple event labels may see different diffs computed.
