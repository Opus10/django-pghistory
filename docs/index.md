# django-pghistory

`django-pghistory` tracks changes to your Django models using [Postgres triggers](https://www.postgresql.org/docs/current/sql-createtrigger.html). It offers several advantages over other apps:

* No base models or managers to inherit, no signal handlers, and no custom save methods. All changes are reliably tracked, including bulk methods, with miniscule code.
* Snapshot all changes to your models, create conditional event trackers, or only track the fields you care about.
* Changes are stored in structured event tables that mirror your models. No JSON, and you can easily query events in your application.
* Changes can be grouped together with additional context attached, such as the logged-in user. The middleware can do this automatically.

`django-pghistory` has a number of ways in which you can configure tracking models for your application's needs and for performance and scale. An admin integration is included out of the box too.

<a id="quick_start"></a>
## Quick Start

Decorate your model with [pghistory.track][]. For example:

```python
import pghistory

@pghistory.track(pghistory.Snapshot())
class TrackedModel(models.Model):
    int_field = models.IntegerField()
    text_field = models.TextField()
```

Above we've registered a [pghistory.Snapshot][] event tracker to `TrackedModel`. This event tracker stores every change in a dynamically-created model that mirrors fields in `TrackedModel`.

Run `python manage.py makemigrations` followed by `migrate` and *voila*, every change to `TrackedModel` is now stored. This includes bulk methods and even changes that happen in raw SQL. For example:

```python
from myapp.models import TrackedModel

# Even though we didn't declare TrackedModelEvent, django-pghistory
# creates it for us in our app
from myapp.models import TrackedModelEvent

m = TrackedModel.objects.create(int_field=1, text_field="hello")
m.int_field = 2
m.save()

print(TrackedModelEvent.objects.values("pgh_obj", "int_field"))

> [{'pgh_obj': 1, 'int_field': 1}, {'pgh_obj': 1, 'int_field': 2}]
```

Above we printed the `pgh_obj` field, which is a special foreign key to the tracked object. There are a few other special `pgh_` fields that we'll discuss later.

`django-pghistory` can track a subset of fields and conditionally store events based on specific field transitions. Users can also store free-form context from the application that's referenced by the event model, all with no additional database queries. See the next steps below on how to dive deeper and configure it for your use case.

## Compatibility

`django-pghistory` is compatible with Python 3.8 - 3.12, Django 3.2 - 4.2, Psycopg 2 - 3, and Postgres 12 - 16.

## Next Steps

We recommend everyone first read:

* [Installation](installation.md) for how to install the library.
* [Basics](basics.md) for an overview and terminology guide.

After this, there are several usage guides:

* [Event Tracking](event_tracking.md) for tracking historical events on models.
* [Collecting Context](context.md) for attaching dynamic application context to events.
* [Configuring Event Models](event_models.md) for configuring event models.
* [Aggregating Events and Diffs](aggregating_events.md) for aggregating events across event models.
* [Admin Integration](admin.md) for an overview of the Django admin integration.
* [Reverting Objects](reversion.md) for reverting models to previous versions.

There's additional help in these sections:

* [Frequently Asked Questions](faq.md) for common questions.
* [Troubleshooting](troubleshooting.md) for advice on known issues.
* [Performance and Scaling](performance.md) for tips on performance and scaling.
* [Upgrading](upgrading.md) for upgrading to new versions.

Finally, core API information exists in these sections:

* [Settings](settings.md) for all available Django settings.
* [Module](module.md) for documentation of the `pghistory` module.
* [Release Notes](release_notes.md) for information about every release.
* [Contributing Guide](contributing.md) for details on contributing to the codebase.
