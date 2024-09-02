# Event Models

When trackers are added to models, an auto-generated event model is created and populated by triggers installed by [django-pgtrigger](https://github.com/Opus10/django-pgtrigger).

Here we overview what these models look like, how they can be configured, and advanced options such as [custom event models](#custom_event_models) and [denormalizing context](#denormalizing_context).

## Event Model Overview

Say we have a model called `TrackedModel` tracked by [pghistory.track][]. The default event model will be named `TrackedModelEvent` and will have the following fields:

```python
class TrackedModelEvent(pghistory.models.Event):
    # The primary key
    pgh_id = models.AutoField(primary_key=True)

    # An unconstrained foreign key to the tracked model
    pgh_obj = models.ForeignKey(TrackedModel, on_delete=models.DO_NOTHING, related_name="event", db_constraint=False)

    # An identifying label for the event. Configurable in the tracker.
    # Defaults to "insert" for insert events and "update" for update events.
    pgh_label = models.TextField()

    # Additional context stored in JSON in the pghistory.Context model
    pgh_context = models.ForeignKey("pghistory.Context", null=True, on_delete=models.DO_NOTHING, related_name="+", db_constraint=False)

    # When the event was created
    pgh_created_at = models.DatetimeField(auto_now_add=True)

    # These fields are copied from the original model. Primary
    # keys and non-foreign key indices are removed. Foreign keys
    # are unconstrained. This behavior can be overridden
    id = models.IntegerField()
    int_field = models.IntegerField()
    char_field = models.CharField(max_length=16)
    user = models.ForeignKey("auth.User", on_delete=models.DO_NOTHING, db_constraint=False)
```

Here are some important notes about the default event models:

* Event models are dynamically created inside the same module as the tracked model when using [pghistory.track][]. Although event models aren't in models.py, they're still imported, migrated, and accessed like a normal model.
* All `pgh_*` fields store metadata. For example, the `pgh_context` collects [context from the application](context.md).
* All other fields are snapshot from the original model. To ensure we don't have integrity issues, foreign keys are unconstrained and unique constraints are dropped.
* The `pgh_label` field is provided by the tracker. By default, [pghistory.InsertEvent][] and [pghistory.UpdateEvent][] trackers use "insert" and "update" as the label. Override this by providing the label as the first argument, i.e. `pghistory.DeleteEvent("my_custom_label")`.

Event models can be configured in a number of ways. First we'll go over the general hierarchy and then discuss specific configuration options.

## Configuration Overview

To configure event models, do either of:

- Apply model-specific defaults with [pghistory.track][] or by [creating a custom event model](#custom_event_models).
- Apply global defaults with settings.

See the [arguments to `pghistory.track`][] for most configuration options, which typically have a corresponding setting. For example, say we'd like to override the default `pgh_obj` field. Do this on an individual model with:

```python
@pghistory.track(
    obj_field=pghistory.ObjForeignKey(
        on_delete=models.CASCADE,
        db_constraint=True
    )
)
class TrackedModel(models.Model):
    ...
```

Or globally with:

```python
PGHISTORY_OBJ_FIELD = pghistory.ForeignKey(
    on_delete=models.CASCADE,
    db_constraint=True
)
```

There are a few settings that influence the default fields, related fields, or foreign key field behavior:

- `PGHISTORY_FIELD` - Default field configuration for all fields on event models.
- `PGHISTORY_RELATED_FIELD` - Default related field configuration for all related fields on event models.
- `PGHISTORY_FOREIGN_KEY_FIELD` - Default foreign key field configuration for all foreign keys on event models.

For example, do `PGHISTORY_RELATED_FIELD = pghistory.RelatedField(null=True)` to ensure all related fields are nullable by default. We cover this in more detail below.

## Default Fields

Every field on an event model, including the ones derived from the tracked model, have attributes overridden by the default [pghistory.Field][] instance, which is configured by `settings.PGHISTORY_FIELD`.

The [pghistory.Field][] object has the following attributes that can be configured, some of which already have overrides:

- `primary_key=False`
- `unique=False`
- `blank=pghistory.DEFAULT`
- `null=pghistory.DEFAULT`
- `db_index=False`
- `editable=pghistory.DEFAULT`
- `unique_for_date=None`
- `unique_for_month=None`
- `unique_for_year=None`

Any attribute with `pghistory.DEFAULT` means it will use the attribute from the tracked field. All others are overrides.

In other words, tracked models will have all primary keys stripped and unique constraints removed by default. Indices are also removed from all tracked fields unless overridden.

If, for example, you'd like event models to not override the `db_index` attribute of tracked fields, you can do `settings.PGHISTORY_FIELD = pghistory.Field(db_index=pghistory.DEFAULT)`. All default overrides, such as `unique_for_date=None` will still be applied.

!!! note

    The `Meta` of the tracked model is never used by the event model, so custom indices here will have to be manually provided by either the `meta` option to [pghistory.track][] or by [making a custom event model](#custom_event_models).

## Related Fields

One can override the behavior of related fields by using the `pghistory.RelatedField` class and setting it with `settings.PGHISTORY_RELATED_FIELD`.

This configuration class uses all of the attributes of [pghistory.Field][] and provides these additional attributes:

- `related_name="+"`
- `related_query_name="+"`

In other words, related names are reset to prevent clashes. Let's say you'd like related names to not be overridden, along with ensuring every related field has `null=True`. You would do this:

```python
PGHISTORY_RELATED_FIELD = pghistory.RelatedField(
    related_name=pghistory.DEFAULT,
    related_query_name=pghistory.DEFAULT,
    null=True
)
```

!!! important

    Remember, the related field configuration will inherit any custom overrides of the default field configuration.

## Foreign Keys

Going a step beyond related fields, one can specifically target foreign keys (and one-to-one fields) with the `pghistory.ForeignKey` configuration object and `settings.PGHISTORY_FOREIGN_KEY_FIELD` setting.

This configuration class uses all of the attributes of `pghistory.RelatedField` field and provides these attributes:

- `on_delete=models.DO_NOTHING`
- `db_constraint=False`

In other words, all foreign keys are unconstrained by default. Event models will *not* be cascade deleted by default. Along with this, `pghistory.ForeignKey` overrides  `db_index=True` to ensure all foreign keys are indexed by default.

If, for example, one wants event models to always be cascade deleted and have referential integrity, do:

```python
PGHISTORY_FOREIGN_KEY_FIELD = pghistory.ForeignKey(
    on_delete=models.CASCADE,
    db_constraint=True
)
```

!!! important

    Just like `pghistory.RelatedField`, `pghistory.ForeignKey` inherits overrides from the base field and related field configuration.

## `pgh_obj` Field

The default `pgh_obj` field of event models can be set with `settings.PGHISTORY_OBJ_FIELD` or by supplying the `obj_field` argument to [pghistory.track][] or [pghistory.create_event_model][]. It must be set to a [pghistory.ObjForeignKey][] instance, which overrides the following attributes:

- `related_name=pghistory.DEFAULT`
- `related_query_name=pghistory.DEFAULT`

In other words, `pgh_obj` will have the default related name applied. Since `pgh_obj` is generated by `django-pghistory`, the default related name is "events". In version 3, this behavior will be changed to remove the related name.

Use `None` to ignore creating the `pgh_obj` field on the event model.

## `pgh_context` Field

The default `pgh_context` field of event models can be set with `settings.PGH_CONTEXT_FIELD` or by supplying the `context_field` argument to [pghistory.track][] or [pghistory.create_event_model][]. It must be set to either a [pghistory.ContextForeignKey][] or [pghistory.ContextJSONField][] instance. When using the former, event models will reference a shared [pghistory.context][] model. When using the latter, context will be denormalized. We discuss this in detail in [Denormalizing Context](#denormalizing_context).

By default, the context foreign key object uses `null=True` to ensure that context is optional.

Similar to `pgh_obj`, the `pgh_context` argument and setting can be `None` if one wishes to ignore context tracking.m

## `pgh_context_id` Field

When denormalizing context, one can configure the default ID field used with `settings.PGH_CONTEXT_ID_FIELD` or by supplying the `context_id_field` to [pghistory.track][] or [pghistory.create_event_model][]. It must be set to a [pghistory.ContextUUIDField][] instance. We discuss this in detail in the [Denormalizing Context](#denormalizing_context) subsection.

Set this to `None` to ignore storing the ID when denormalizing context.

## Append-only Protection

One can protect event models from being updated or deleted with `settings.PGHISTORY_APPEND_ONLY` or by supplying the `append_only=True` argument to [pghistory.track][] or [pghistory.create_event_model][]. It defaults to `False`. If true, any updates or deletes to event models will throw internal database errors.

## Configuration with `pghistory.track`

[pghistory.track][] takes `obj_field`, `context_field`, and `context_id_field` arguments for overriding event fields on a per-model basis. These must be supplied configuration instances just like global settings. For example, `obj_field` takes [pghistory.ObjForeignKey][] instances.

Keep in mind that these overrides still follow the configuration hierachy and inherit any overrides from the settings.

[pghistory.track][] also takes the following attributes:

* `base_model`: For overriding the base model of the event model.
* `meta`: For supplying additional attributes to the `Meta` of the generated model.
* `attrs`: For supplying additional attributes to the event model class.

!!! tip

    We recommend [creating a custom event model](#custom_event_models) if needing to use these attributes.

## Ignoring Object and Context References

If you'd like to remove the `pgh_obj` and `pgh_context` fields, set them to `None`. This will ignore object and context tracking, along with removing the fields from the models entirely. This can be done globally with settings or on a per-event-model basis with the arguments to [pghistory.track][].

<a id="custom_event_models"></a>
## Custom Event Models

Instead of decorating models with [pghistory.track][], users can also use [pghistory.create_event_model][] to create the event model. This interface has the following advantages:

1. You can declare event models directly in `models.py`.
2. Fields and `Meta` classes can be defined that directly override the auto-generated fields. Custom field overrides do *not* follow the configuration hierarchy.

For example, let's revisit our `TrackedModel` from a previous section:

```python
class TrackedModel(models.Model):
    int_field = models.IntegerField()
    char_field = models.CharField(max_length=16, db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
```

Now let's track snapshots for every insert and update of `TrackedModel` with [pghistory.create_event_model][]:

```python
import pghistory

class TrackedModel(models.Model):
    ...

BaseTrackedModelEvent = pghistory.create_event_model(TrackedModel)

class TrackedModelEvent(BaseTrackedModelEvent):
    class Meta:
        indexes = [
            models.Index(fields=["int_field"])
        ]
```

The arguments for [pghistory.create_event_model][] closely match [pghistory.track][]. By default, event models are abstract unless `abstract=False` is provided. If you want to create a non-abstract model, be sure to pass the `model_name` argument like so:

```python
import pghistory

class TrackedModel(models.Model):
    ...

TrackedModelEvent = pghistory.create_event_model(
    TrackedModel,
    model_name="TrackedModelEvent"
)
```

Overridden event models can directly override `pgh_*` fields or the tracked fields of the model. We recommend overriding fields with the arguments to [pghistory.create_event_model][] when possible.

<a id="denormalizing_context"></a>
## Denormalizing Context

By default, event models have a foreign key to a central context table. As a result, this table is frequently updated and inserted during event tracking.

If performance is a concern or you want to partition event tables, context can be denormalized with [pghistory.ContextJSONField][]. You can do this globally with `settings.PGHISTORY_CONTEXT_FIELD = pghistory.ContextJSONField()` or on a per-event-model basis with the `context_field` argument to [pghistory.track][] and [pghistory.create_event_model][].

When used, a `JSONField` is created directly on the event model for the `pgh_context` field. The `pgh_context_id` field defaults to a `UUIDField` so that events can be grouped together.

Behavior of the `pgh_context_id` field can be overridden in a similar way as other fields by using [pghistory.ContextUUIDField][] and globally setting `settings.PGHISTORY_CONTEXT_ID_FIELD` or supplying the `context_id_field` argument to relevant functions.

!!! note

    `context_id_field` can be `None` if you don't want to track the UUID of the context or have a `pgh_context_id` field on your denormalized event models.

When using denormalized context, keep in mind that context tracking behavior is going to produce different results if your application overrides context keys. Take the following example:

```python
with pghistory.context(key="val1"):
    # Do updates here that produce the first set of events

    with pghistory.context(key="val2"):
        # Do updates here that produce the second set of events
```

When using denormalized context, the first set of events will have `key: "val1"` in their context. The second set of events will have `key: "val2"`. When using a shared context table, all events will have `key: "val2"`.

<a id="event_proxy"></a>
## Querying Context as Structured Fields

Context data is free-form JSON, but `django-pghistory` provides a [pghistory.ProxyField][] utility that you can use to proxy JSON fields on event models.

!!! note

    This feature only works on Django 3.2 and above.

For example, let's create a snapshot tracker of a model and then proxy the `user` key from the context in an event model:

```python
@pghistory.track()
class MyModel(models.model):
    ...

class MyModelEventProxy(MyModel.pgh_event_model):
    user = pghistory.ProxyField(
        "pgh_context__metadata__user",
        models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.DO_NOTHING,
            help_text="The user associated with the event.",
        ),
    )

    class Meta:
        proxy = True
```

!!! tip

    You can use the `pgh_event_model` attribute of the tracked model as a quick way to inherit the generated event model like above.

Above we've proxied the `pgh_context__metadata__user` attribute through a `ForeignKey` field. This allows us to now treat the `user` attribute in our context as a foreign key:

```python
MyEventProxy.objects.values("user__email")
```

[pghistory.ProxyField][] is just taking a relationship and proxying it to a field. If, for example, you use denormalized context, the relationship would be `pgh_context__user`.

!!! tip

    Any relationship can be proxied with this utility, not just JSON fields.

## Debugging

There are a few ways in which event model attributes can be changed, whether through global settings, [pghistory.track][] or [pghistory.create_event_model][] overrides, or through directly overriding the fields on a base model.

In order to debug how configuration affects your event models, we recommend running `makemigrations` after a change and closely inspecting the output to see what happened.
