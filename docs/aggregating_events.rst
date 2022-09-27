.. _aggregating_events:

Aggregating Events and Diffs
============================

Tracking events across models results in multiple event
tables, creating challenges to query the the history for
a single object or other objects that reference it. Similarly,
obtaining diffs to see what actually changed can be
cumbersome. The `pghistory.models.Events` proxy model
makes both of these use cases easy.

Using the ``Events`` model
--------------------------

The `pghistory.models.Events`
proxy model treats all event tables as a unified view that
can be queried as a normal Django model. It comes
with the following fields:

    * **pgh_slug**: The unique identifier across all event tables.
    * **pgh_model**: The event model label formatted as "app_label.ModelName".
    * **pgh_id**: The primary key of the event.
    * **pgh_created_at**: When the event was created.
    * **pgh_label**: The event label.
    * **pgh_data**: The raw data of the event.
    * **pgh_diff**: The diff against the previous event of the same label.
    * **pgh_context_id**: The context UUID.
    * **pgh_context**: The context JSON associated with the event.
    * **pgh_obj_model**: The object model.
    * **pgh_obj_id**: The primary key of the object.

Let's create a snapshot tracker for a ``User``
model and query the associated events:

.. code-block:: python

    @pghistory.track(pghistory.Snapshot("user.change"))
    class User(models.Model):
        username = models.CharField()
        name = models.CharField()

We create a user, modify the username, and view the data and diffs
using `pghistory.models.Events`.

.. code-block:: python

    import pghistory.models

    user = User.objects.create(username="hello", name="world")
    user.username = "hi"
    user.save()

    print(pghistory.models.Events.objects.order_by("pgh_created_at").values())

The events look like::

    [{
        "pgh_slug": "app.UserEvent:<event_id>"
        "pgh_model": "app.UserEvent",
        "pgh_id": "<event_id>",
        "pgh_created_at": datetime(2020, 6, 17, 12, 20, 10),
        "pgh_label": "user.change",
        "pgh_data": {
            "username": "hello",
            "name": "world",
            "id": "<user_id>"
        },
        "pgh_diff": None,
        "pgh_context_id": None
        "pgh_context": None,
        "pgh_obj_model": "app.User",
        "pgh_obj_id": "<user_id>"
    },
    {
        "pgh_slug": "app.UserEvent:<event_id>",
        "pgh_model": "app.UserEvent",
        "pgh_id": "<event_id>",
        "pgh_created_at": datetime(2020, 6, 17, 12, 20, 20),
        "pgh_label": "user.change",
        "pgh_data": {
            "username": "hi",
            "name": "world",
            "id": "<user_id>"
        },
        "pgh_diff": {
            "username": ["hello", "hi"]
        }
        "pgh_context_id": None
        "pgh_context": None,
        "pgh_obj_model": "app.User",
        "pgh_obj_id": "<user_id>"
    }]

Above we see that ``pgh_data`` shows the raw data and ``pgh_diff`` shows
the changes. The first diff is empty because there is no previous event
of the same object and label.

How does it work?
-----------------

Underneath the hood, `pghistory.models.Events` is a
`common table expression (CTE) <https://www.postgresql.org/docs/current/queries-with.html>`__
that does a ``UNION ALL`` across event tables. It uses
`window functions <https://www.postgresql.org/docs/current/tutorial-window.html>`__
to compute the diff.

When filtering the events directly using ``Events.objects.filter()``, keep in mind
that the aggregate CTE is filtered. In versions of Postgres before 12, CTEs are materialized
before being queried, which can lead to poor performance when working with many large
event tables. Postgres 12
`changed how it treats CTEs <https://www.postgresql.org/docs/12/release-12.html>`__
and can optimize how CTEs are filtered.

Regardless of what version of Postgres you're using, we recommend using
the ``across()``, ``tracks()`` and ``references()`` methods on the
queryset for basic filtering. We cover these in the next sections.

Filtering event models using ``objects.across()``
-------------------------------------------------

Use ``Event.objects.across("app.Model")`` to filter events by their associated event model.
``Event.objects.across()`` can be supplied
with multiple model classes or model import strings. It is a much more efficient
query than running ``Event.objects.filter(pgh_model="my.Model")``.

Filtering by tracked objects using ``objects.tracks()``
-------------------------------------------------------

Filter aggregate events by object using ``Events.objects.tracks()``. This method takes one or multiple objects and
limits the search space by the tracked object. Event models without a ``pgh_obj`` field will be ignored.

Filtering by referenced objects using ``objects.references()``
--------------------------------------------------------------

The aforementioned ``objects.tracks()`` method only filters by the ``pgh_obj`` field. ``objects.references()``
will filter events that have *any* foreign key to the associate object(s). This allows one to query events
related to a particular object, such as group or permission events for a particular user.
Simply supply the primary object(s) to ``Events.objects.references()``, and all
referencing events will be returned.

Note that only events up to one level deep will be returned. Indirect relationships
through multiple foreign keys are not returned.

For example, say that we have two models like so:

.. code-block:: python

    class Company(models.Model):
        name = models.TextField()

    class Product(models.Model):
        company = models.ForeignKey(Company, on_delete=models.CASCADE)


If we make changes to the company or products, doing
``Events.objects.references(company_object)`` will return all events for the company
and any products that reference it.

Note that like other methods, ``Events.objects.references`` takes a variable amount
of arguments.

.. _events_proxy:

Querying Context as Structured Fields
-------------------------------------

Similar to individual event models, `pghistory.models.Events` can also have child
classes that make use of the `pghistory.ProxyField` utilty.

For example, let's say that we track the ``url`` attribute in our context metadata.
Here we create a subclass that proxies this field:

.. code-block::

    class EventsProxy(pghistory.models.Events):
        url = pghistory.ProxyField("pgh_context__url", models.TextField())

        class Meta:
            proxy = True

The ``EventsProxy`` model from above now has access to the ``url`` field from
the context as a normal field. For example, one can now do:

.. code-block:: python

    EventsProxy.objects.tracks(object).filter(url="https://some_url.com")

Unlike individual event models, only the ``pgh_context`` field can be proxied
on the `pghistory.models.Events` model.

.. note::

    If the corresponding attribute doesn't exist in the JSON, ``None`` will
    be returned.

Using the ``MiddlewareEvents`` model
------------------------------------

If you use :ref:`the middleware <middleware>` to attach context on requests, you
can make use of `pghistory.models.MiddlewareEvents`, which attaches
a ``user`` and ``url`` field that correspond to the attributes captured by
the middleware.
