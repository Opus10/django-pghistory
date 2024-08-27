# django-pghistory

`django-pghistory` tracks changes to your Django models using [Postgres triggers](https://www.postgresql.org/docs/current/sql-createtrigger.html), providing:

* Reliable history tracking everywhere with no changes to your application code.
* Structured history models that mirror the fields of your models.
* Grouping of history with additional context attached, such as the logged-in user.

`django-pghistory` has a number of ways in which you can configure history tracking for your application's needs and for performance and scale. An admin integration and middleware is included out of the box too.

<a id="quick_start"></a>
## Quick Start

Decorate your model with `pghistory.track`. For example:

```python
import pghistory

@pghistory.track()
class TrackedModel(models.Model):
    int_field = models.IntegerField()
    text_field = models.TextField()
```

Above we've tracked `TrackedModel`. Copies of the model will be stored in a dynamically-created event model on every insert and update.

Run `python manage.py makemigrations` followed by `migrate` and *voila*, every change to `TrackedModel` is now stored. This includes bulk methods and even changes that happen in raw SQL. For example:

```python
from myapp.models import TrackedModel

m = TrackedModel.objects.create(int_field=1, text_field="hello")
m.int_field = 2
m.save()

print(m.events.values("pgh_obj", "int_field"))

> [{'pgh_obj': 1, 'int_field': 1}, {'pgh_obj': 1, 'int_field': 2}]
```

Above we printed the history of `int_field`. We also printed `pgh_obj`, which references the tracked object. We'll cover how these fields and additional metadata fields are tracked later.

`django-pghistory` can track a subset of fields and conditionally store events based on specific field transitions. Users can also store free-form context from the application in event metadata, all with no additional database queries. See the next steps below on how to dive deeper and configure it for your use case.

## Compatibility

`django-pghistory` is compatible with Python 3.8 - 3.12, Django 4.2 - 5.1, Psycopg 2 - 3, and Postgres 13 - 16.

## Documentation

[View the django-pghistory docs here](https://django-pghistory.readthedocs.io/) to learn more about:

* The basics and terminology.
* Tracking historical events on models.
* Attaching dynamic application context to events.
* Configuring event models.
* Aggregating events across event models.
* The Django admin integration.
* Reverting models to previous versions.
* A guide on performance and scale.

There's also additional help, FAQ, and troubleshooting guides.

## Installation

Install `django-pghistory` with:

    pip3 install django-pghistory

After this, add `pghistory` and `pgtrigger` to the `INSTALLED_APPS` setting of your Django project.

## Other Material

There's a [DjangoCon 2023 talk](https://youtu.be/LFIAqFt9z2s?si=GQBchy9bVAk-b9ok) that walks through how the library works and provides an overview of problems that can be solved through history-tracking in Django, discussing context-tracking, event reversions, and soft-deletes.

## Contributing Guide

For information on setting up django-pghistory for development and contributing changes, view [CONTRIBUTING.md](CONTRIBUTING.md).

## Creator

- [Wes Kendall](https://github.com/wesleykendall)

## Other Contributors

- @max-muoto
- @shivananda-sahu
- @asucrews
- @Azurency
- @dracos
- @adamchainz
- @eeriksp
- @pfouque
- @tobiasmcnulty
- @lokhman
- @SupImDos
- @pmdevita
- @pablogadhi
- @xaitec
- @foobarna
