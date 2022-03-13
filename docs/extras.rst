.. _extras:

Extras
======

Aggregating Events with ``AggregateEvent``
------------------------------------------

Tracking events across models can result in many different event
tables, making it cumbersome to piece together the history for
a single object.

Similarly, it can also be cumbersome to pull in changes related to
a particular model even when history tracking has not been directly
configured for that model itself (e.g. showing the ``Group`` events related
to a particular ``User``).

``django-pghistory`` comes with the `pghistory.models.AggregateEvent`
proxy model to facilitate event aggregation for objects. The model has
the following fields:

1. ``pgh_id``: The ID of the event row
2. ``pgh_table``: The database table of the event model.
3. ``pgh_created_at``: The creation time of the event.
4. ``pgh_label``: The label of the event.
5. ``pgh_data``: JSON data of all of the columns in the event row.
6. ``pgh_diff``: JSON data that shows the differences between this event
   and the previous event on the same object with the same
   label.
7. ``pgh_context``: The context foreign key of the event, if any was tracked.

Let's assume we've set up a snapshot to happen on changes to a ``User``
model:

.. code-block:: python

    @pghistory.track(pghistory.Snapshot('user.change'))
    class User(models.Model):
        username = models.CharField()
        name = models.CharField()


We can now create a user, modify the username, and see what the aggregate
event stream looks like:

.. code-block:: python

    import pghistory.models

    user = User.objects.create(username='hello', name='world')
    user.username = 'hi'
    user.save()

    print(pghistory.models.AggregateEvent.objects.target(user).order_by('pgh_created_at').values())


We use the special ``target`` method to target a single object;
a queryset or list of objects in the same class can also be provided.
The aggregate events for this code would look something like this::

    [{
        'pgh_id': <original event ID>,
        'pgh_table': 'users_userevent',
        'pgh_created_at': datetime(2020, 6, 17, 12, 20, 10),
        'pgh_data': {
            'username': 'hello',
            'name': 'world',
            'id': <user ID>
        },
        'pgh_label': 'user.change',
        'pgh_diff': None,
        'pgh_context_id': None
    },
    {
        'pgh_id': <original event ID>,
        'pgh_table': 'users_userevent',
        'pgh_created_at': datetime(2020, 6, 17, 12, 20, 20),
        'pgh_data': {
            'username': 'hi',
            'name': 'world',
            'id': <user ID>
        },
        'pgh_diff': {
            'username': ['hello', 'hi']
        }
        'pgh_label': 'user.change',
        'pgh_context_id': None
    }]

In the above, we see that ``pgh_data`` shows the data for the tracked model
during a snapshot event. In the first row, there is no ``pgh_diff`` because
we don't have a previous event for the same object with the ``snapshot`` label.
In the second row, however, the ``pgh_diff`` shows that the ``username`` field
was changed from ``hello`` to ``hi``.

By default, the ``AggregateEvent`` proxy will explore *all* event models
that reference the target object(s). For example, let's make a completely
separate model that has a foreign key to ``User`` and track that model.

.. code-block:: python

    @pghistory.track(pghistory.Snapshot('other_model.change'))
    class OtherModel(models.Model):
        user = models.ForeignKey(User)


Creating another model that points to the original user we created
(i.e. ``OtherModel.objects.create(user=user)``) will result in an
``AggregateEvent`` list that has an additional entry at the end::

    [{
        'pgh_id': <original event ID>,
        'pgh_table': 'users_userevent',
        'pgh_created_at': datetime(2020, 6, 17, 12, 20, 10),
        'pgh_data': {
            'username': 'hello',
            'name': 'world',
            'id': <user ID>
        },
        'pgh_label': 'user.change',
        'pgh_diff': None,
        'pgh_context_id': None
    },
    {
        'pgh_id': <original event ID>,
        'pgh_table': 'users_userevent',
        'pgh_created_at': datetime(2020, 6, 17, 12, 20, 20),
        'pgh_data': {
            'username': 'hi',
            'name': 'world',
            'id': <user ID>
        },
        'pgh_diff': {
            'username': ['hello', 'hi']
        }
        'pgh_label': 'user.change',
        'pgh_context_id': None
    }, {
        'pgh_id': <original event ID>,
        'pgh_table': 'otherapp_othermodelevent',
        'pgh_created_at': datetime(2020, 6, 17, 12, 21, 20),
        'pgh_data': {
            'user_id': <user ID>
            'id': <other model ID>
        },
        'pgh_diff': None,
        'pgh_label': 'other_model.change',
        'pgh_context_id': None
    }]

.. note::

    ``pgh_diff`` for the last row is ``None``. This is because there
    is no previous ``other_model.change`` event for the object. All
    diffs are relative to last event of the same label and object being
    tracked.

To recap, the ``AggregateEvent`` proxy is a utility that allows one to
aggregate all events related to an object. By default, any event model
that has any foreign key to the target object will be aggregated into
a single queryset. The queryset is like any other Django queryset and
allows one to filter on event labels, join in context, and order by
the fields.

If one wishes to only aggregate specific event models, use
``AggregateEvent.objects.across(EventModel1, EventModel2)`` for the target
object in question.


Retrieving and Joining ``AggregateEvent`` Metadata
--------------------------------------------------

Metadata that's stored in the ``pgh_context`` foreign key of an
aggregate event can be difficult to access or join since it is a JSON
field. For example, Django apps like
`django-tables <https://django-tables2.readthedocs.io/en/latest/>`__ and
`django-filter <https://django-filter.readthedocs.io/en/stable/>`__
can integrate more easily with fields that are defined on the model.

In order to bring important metadata into top-level fields of
an `pghistory.models.AggregateEvent`, one can create their own
aggregate event model by extending `pghistory.models.BaseAggregateEvent`.

For example, if one is using `pghistory.middleware.HistoryMiddleware` to
attach a ``user`` and ``url`` key to context metadata, these values
can be made into top-level attributes of an aggregate event model
with code like the following:

.. code-block:: python

    class CustomAggregateEvent(pghistory.models.BaseAggregateEvent):
        user = models.ForeignKey(
            'auth.User', on_delete=models.DO_NOTHING, null=True
        )
        url = models.TextField(null=True)

        class Meta:
            managed = False

When extending `pghistory.models.BaseAggregateEvent`, any additional
field declared will be pulled from the metadata of the context (if it
exists). It is up to the user to create fields that represent the appropriate
types stored in the JSON. For example, we can assume the ``user`` key
is a foreign key to the ``User`` model and the ``url`` key is a text field.
Also, be sure to declare the model as unmanaged, otherwise Django will
try to create a migration for it.

.. note::

    Not every event will track the same context keys, so it is good practice
    to make any extended field null-able. Foreign key relationships may
    also not reference actual rows in the foreign table, which can create
    some issues of unexpected ``ObjectDoesNotExist`` errors. It is up the
    user to keep these potential issues in mind when rendering aggregate
    event data.

With the following model, we can now access metadata from context in events
as though it was not a column in a JSON field. For example,

.. code-block:: python

    # Get all aggregate events and annotate emails of the user that
    # performed the event
    CustomAggregateEvent.objects.annotate(email=F('user__email'))


Showing Event History in the Django Admin
-----------------------------------------

Although ``django-pghistory`` does not come with a direct integration
into the Django Admin, one can override the default Django history templates
in the following way. First, make a template that will be used in place
of Django's default admin history. The following is a sample that
creates a table of historical events and collapses context, data, and
diffs:

.. code-block:: jinja

    {% extends "admin/object_history.html" %}

    {% block content %}
      <style>
      .pgh-hidden {
        display: none;
      }
      </style>

      <table id="change-history">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Event</th>
            <th scope="col"></th>
          </tr>
        </thead>
        <tbody>
          {% for item in object_history %}
            <tr>
              <th scope="row">{{ item.pgh_created_at|date:"DATETIME_FORMAT" }}</th>
              <td>{{ item.pgh_label }}</td>
              <td align="right">
                {% if item.pgh_context %}
                  <button style="align:right" onclick='$("#history-context-{{ forloop.counter0 }}").toggleClass("pgh-hidden")'>Context</button>
                {% endif %}

                {% if item.pgh_data %}
                  <button style="align:right" onclick='$("#history-data-{{ forloop.counter0 }}").toggleClass("pgh-hidden")'>Data</button>
                {% endif %}

                {% if item.pgh_diff %}
                  <button style="align:right" onclick='$("#history-diff-{{ forloop.counter0 }}").toggleClass("pgh-hidden")'>Changes</button>
                {% endif %}

                {% if item.pgh_context %}
                  <div class="pgh-hidden" id="history-context-{{ forloop.counter0 }}" style="text-align:left">
                    <h5>Context</h5>
                    <table style="width:100%">
                      <thead>
                        <tr>
                          <th scole="col">Key</th>
                          <th scope="col">Value</th>
                        </tr>
                      </thead>
                    {% for key, value in item.pgh_context.metadata.items %}
                      <tr>
                        <th>{{ key }}</th>
                        <td>{{ value }}</td>
                      </tr>
                    {% endfor %}
                    </table>
                  </div>
                {% endif %}

                {% if item.pgh_data %}
                  <div class="pgh-hidden" id="history-data-{{ forloop.counter0 }}" style="text-align:left">
                    <h5>Data</h5>
                    <table style="width:100%">
                      <thead>
                        <tr>
                          <th scole="col">Key</th>
                          <th scope="col">Value</th>
                        </tr>
                      </thead>
                    {% for key, value in item.pgh_data.items %}
                      <tr>
                        <th>{{ key }}</th>
                        <td>{{ value }}</td>
                      </tr>
                    {% endfor %}
                    </table>
                  </div>
                {% endif %}

                {% if item.pgh_diff %}
                  <div class="pgh-hidden" id="history-diff-{{ forloop.counter0 }}" style="text-align:left">
                    <h5>Changes</h5>
                    <table style="width:100%">
                      <thead>
                        <tr>
                          <th scole="col">Field</th>
                          <th scope="col">Before</th>
                          <th scope="col">After</th>
                        </tr>
                      </thead>
                    {% for key, value in item.pgh_diff.items %}
                      <tr>
                        <th>{{ key }}</th>
                        <td>{{ value.0 }}</td>
                        <td>{{ value.1 }}</td>
                      </tr>
                    {% endfor %}
                    </table>
                  </div>
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endblock %}

One can then override the ``object_history_template``
variable on their model admin to point to this template. Then override
the ``history_view`` method on the model admin like so:

.. code-block:: python

    object_history_template = 'my_app/my_history_template.html'

    def history_view(self, request, object_id, extra_context=None):
        """
        Adds additional context for the custom history template.
        """
        extra_context = extra_context or {}
        extra_context['object_history'] = (
            pghistory.models.AggregateEvent.objects
            .target(self.model(pk=object_id))
            .order_by('pgh_created_at')
            .select_related('pgh_context', 'user')
        )
        return super().history_view(
            request, object_id, extra_context=extra_context
        )

.. note::

    One can also override the global "admin/object_history.html" template
    to show the custom history view for every admin page, however, the
    template will need to be modified to use a template tag to obtain
    the ``AggregateEvent`` query (instead of overriding ``history_view``
    as shown in the example).
