# Event Tracking

Here we overview how event tracking works and how to customize it. It's useful to read both the [Quick Start](index.md#quick_start) and [Basics](basics.md) sections for a primer on terminology and concepts.

## `pghistory.track`

[pghistory.track][] is the primary way to track model events. For example, let's say that we have the following model:

```python
class TrackedModel(models.Model):
    int_field = models.IntegerField()
    char_field = models.CharField(max_length=16, db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
```

Now let's track snapshots for every insert and update of `TrackedModel` with [pghistory.track][]:

```python
import pghistory

@pghistory.track()
class TrackedModel(models.Model):
    ...
```

By default, [pghistory.track][] registers [pghistory.InsertEvent][] and [pghistory.UpdateEvent][] trackers. See [custom trackers](#custom_trackers) below for how to override this behavior.

When trackers are added, an [auto-generated event model](event_models.md) is created and populated by triggers installed by [django-pgtrigger](https://github.com/Opus10/django-pgtrigger). By default, the model will be named `TrackedModelEvent`. It contains every field in `TrackedModel` plus a few additional tracking fields.

For example, let's create a `TrackedModel`, update it, and print the resulting event values:

```python
from myapp.models import TrackedModel

m = TrackedModel.objects.create(int_field=1, text_field="hello")
m.int_field = 2
m.save()

# "events" is the default related name of the event model.
print(m.events.values("pgh_obj", "pgh_label", "int_field"))

> [
>     {'pgh_obj': 1, 'pgh_label': 'insert', 'int_field': 1},
>     {'pgh_obj': 1, 'pgh_label': 'update', 'int_field': 2}
> ]
```

## Tracking Specific Fields

One may wish to only track a subset of fields in a model. This can be achieved by using the `fields` and `exclude` arguments to [pghistory.track][]. For example, here we create an event model that only tracks `int_field`:

```python
@pghistory.track(fields=["int_field"])
class TrackedModel(models.Model):
    int_field = models.IntegerField()
    char_field = models.CharField(max_length=16, db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
```

When doing this, keep the following in mind:

- The event model will only mirror the `int_field` of the tracked model. It won't store `char_field` or `user`.
- Updates to the event model will only create events if `int_field` is changed.

One can also exclude fields like so:

```python
@pghistory.track(exclude=["int_field"])
class TrackedModel(models.Model):
    int_field = models.IntegerField()
    char_field = models.CharField(max_length=16, db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
```

In this case, we'll track both `char_field` and `user`. Inserts and updates to either of these two fields will create events.

!!! note

    One can further override event model configuration, such as creating custom database indices, by directly creating a custom event model. [See this section for more details](event_models.md#custom_event_models).

<a id="custom_trackers"></a>
## Custom Trackers

We've only shown [pghistory.track][] with the default configuration. Let's say that we wish to only create events on model deletion. We can configure this behavior using the [pghistory.DeleteEvent][] tracker:

```python
@pghistory.track(pghistory.DeleteEvent())
class TrackedModel(models.Model):
    ...
```

!!! remember

    We've overridden the default trackers by doing this. Only deletions will be tracked. One can add back in the default behavior of tracking inserts and updates as follows:

    ```python
    @pghistory.track(
        pghistory.InsertEvent(), pghistory.UpdateEvent(), pghistory.DeleteEvent()
    )
    class TrackedModel(models.Model):
        ...
    ```

The [pghistory.InsertEvent][], [pghistory.UpdateEvent][], and [pghistory.DeleteEvent][] trackers all inherit [pghistory.RowEvent][] and specify some defaults, such as:

- The `pgh_label` that will be generated. [pghistory.DeleteEvent][], for example, will use "delete" as the label of the event. Customize this by providing the label as the first argument, i.e. `pghistory.DeleteEvent("my_custom_label")`.
- The row and trigger conditions. [pghistory.UpdateEvent][], for example, has its condition configured to only fire if any tracked fields change. It also stores the `NEW` row of the update. If one desires to store the row as it was *before* the update, do `pghistory.UpdateEvent(row=pghistory.Old)`.

<a id="conditional_tracking"></a>
## Conditional Tracking

By default, [pghistory.track][] stores events for all changes to the `fields` specified (or every field if no `fields` are specified). Supply conditional trackers to specify when events are created. We show examples of this below.

!!! tip

    All examples here mostly pass through to [django-pgtrigger's conditional interface](https://django-pgtrigger.readthedocs.io/en/stable/conditional/). Check out those docs for more examples.

### Basic Example

Here we create a conditional tracker that only fires whenever the `email` is updated:

```python
import pghistory

@pghistory.track(
    pghistory.UpdateEvent(
        "email_changed",
        row=pghistory.Old,
        condition=pghistory.AnyChange("email")
    ),
    model_name="UserEmailHistory"
)
class MyUser(models.Model):
    username = models.CharField(max_length=128)
    email = models.EmailField()
    address = models.TextField()
```

There are two key things going on here:

1. The [pghistory.UpdateEvent][] tracker runs on updates of `MyUser`, storing what the row looked like right before the update (i.e. the "old" row).
2. We use [pghistory.AnyChange][] to specify that the event should fire on any change to `email`.
3. We've named our event model `UserEmailHistory`. It stores every field of the `MyUser` model.

Let's see what this looks like when we change the `email` field:

```python
from myapp.models import MyUser, UserEmailHistory

u = MyUser.objects.create(username="hello", email="hello@hello.com")

# Events are only tracked on updates, so nothing has been stored yet
assert not UserEmailHistory.objects.exists()

# Change the email. An event should be stored
u.email = "world@world.com"
u.save()
print(UserEmailHistory.objects.filter(pgh_obj=u).values_list("email", flat=True))

> ["hello@hello.com"]
```

### Condition Utilities

`django-pghistory` provides the following utilities for creating change conditions, all of which are from the [django-pgtrigger library](https://django-pgtrigger.readthedocs.io):

- [pghistory.AnyChange][]: For storing an event on any changes to the provided fields. If no fields are provided, the default behavior is to fire on any change being tracked.
- Similar to [pghistory.AnyChange][], [pghistory.AnyDontChange][] fires when any of the provided fields don't change. [pghistory.AllChange][] and [pghistory.AllDontChange][] also fire when all provided fields change or all of them don't change. As mentioned before, if no fields are provided, the conditions fire based on the fields being tracked.

Here are some brief examples of these conditions:

- `pghistory.AnyChange("field_one", "field_two")`: Fire when `field_one` or `field_two` change.
- `pghistory.AnyChange(exclude=["my_field"])`: Fire when any field except for `my_field` changes.
- `pghistory.AnyChange(exclude_auto=True)`: Fire when any field except for fields with `auto_now` or `auto_now_add` attributes are set (e.g. `DateField` and `DateTimeField`).
- `pghistory.AllChange("field_three", "field_four")`. Fire only when both `field_three` and `field_four` change in the same update.

!!! remember

    The conditions above are only for [pghistory.UpdateEvent][] trackers. They cannot be used on [pghistory.InsertEvent][] or [pghistory.DeleteEvent][] since rows aren't being changed.

### Q and F Conditions

We can create even more specific conditions with the [pghistory.Q][] and [pghistory.F][] constructs, which are also from the [django-pgtrigger library](https://django-pgtrigger.readthedocs.io). For example, let's make an event when the cash in a bank account drops below one hundred dollars:

```python
@pghistory.track(
    pghistory.UpdateEvent(
        "money_below_one_hundred",
        condition=pghistory.Q(old__dollars__gte=100, new__dollars__lt=100)
    ),
)
class Cash(models.Model):
    dollars = models.DecimalField()
```

We can make another event log for when the money goes down or up:

```python
@pghistory.track(
    pghistory.UpdateEvent(
        "money_below_one_hundred",
        condition=pghistory.Q(old__dollars__gte=100, new__dollars__lt=100)
    ),
    pghistory.UpdateEvent(
        "money_down",
        condition=pghistory.Q(old__dollars__gt=pghistory.F("new__dollars"))
    ),
    pghistory.UpdateEvent(
        "money_up",
        condition=pghistory.Q(old__dollars__lt=pghistory.F("new__dollars"))
    )
)
class Cash(models.Model):
    dollars = models.DecimalField()
```

See the [django-pgtrigger docs](https://django-pgtrigger.readthedocs.io) to learn more about trigger conditions and how the `Q` and `F` objects can be used.

## Multiple Trackers

Use multiple invocations of [pghistory.track][] to track events with different schemas:

```python
@pghistory.track(
    pghistory.UpdateEvent(
        "email_changed",
        row=pghistory.Old,
        condition=pghistory.AnyChange("email")
    ),
    fields=["email"],
    model_name="UserEmailHistory"
)
@pghistory.track(
    pghistory.UpdateEvent(
        "username_changed",
        row=pghistory.Old,
        condition=pghistory.AnyChange("username")
    ),
    fields=["username"],
    model_name="UserUsernameHistory"
)
class TrackedModel(models.Model):
    ...
```

## Manual Tracking

Sometimes it is not possible to express an event based on a series of changes to a model. Some use cases, such as backfilling data, also require that events are manually created.

[pghistory.create_event][] can be used to manually create events. Events can be created for existing trackers, or the bare [pghistory.ManualEvent][] can be used for registering events that can only be manually created.

Here we register a bare [pghistory.ManualEvent][] tracker and create an event with the label of "user.create":

```python
@pghistory.track(
    pghistory.ManualEvent("user_create"),
    fields=['username']
)
class MyUser(models.Model):
    username = models.CharField(max_length=64)
    password = models.PasswordField()

# Create a user and manually create a "user.create" event
user = MyUser.objects.create(...)
pghistory.create_event(user, label="user_create")
```

!!! note

    Manually-created events will still be linked with context if context tracking has started. More on context tracking in the [Collecting Context](context.md) section.

<a id="third_party_models"></a>
## Third-Party Models

`django-pghistory` can track changes to third-party models like Django's `User` model by using a proxy model. Below we show how to track the default Django `User` model:

```python
from django.contrib.auth.models import User
import pghistory

# Track the user model, excluding the password field
@pghistory.track(exclude=["password"])
class UserProxy(User):
    class Meta:
        proxy = True
```

!!! important

    Although it's possible to track the models directly with `pghistory.track(...)(model_name)`, doing so would create migrations in a third-party app. Using proxy models ensures that the migration files are created inside your project.


## Many-To-Many Fields

Events in many-to-many fields, such as user groups or permissions, can be configured by tracking the "through" model of the many-to-many relationship. Here we show an example of how to track group "add" and "remove" events for Django's user model:

```python
from django.contrib.auth.models import User
import pghistory

@pghistory.track(
    pghistory.AfterInsert("group.add"),
    pghistory.BeforeDelete("group.remove"),
    obj_field=None,
)
class UserGroups(User.groups.through):
    class Meta:
        proxy = True
```

There are a few things to keep in mind:

1. We made a proxy model since it's a third-party model. Models in your project can directly call `pghistory.track(arguments)(model)`.
2. Django does not allow foreign keys to auto-generated "through" models. We set `obj_field=None` to ignore creating a reference in the event model. See the [Configuring Event Models](event_models.md) section for more information.

After migrating, events will be tracked as shown:

```python
# Note: this is pseudo-code
> user = User.objects.create_user("username")
> group = Group.objects.create(name="group")
> user.groups.add(group)
> user.groups.remove(group)
> print(my_app_models.UserGroupsEvent.objects.values("pgh_label", "user", "group"))

[
    {"user": user.id, "group": group.id, "pgh_label": "group.add"},
    {"user": user.id, "group": group.id, "pgh_label": "group.remove"},
]
```
