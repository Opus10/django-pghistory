django-pghistory
=================

``django-pghistory`` provides automated and customizable history
tracking for Django models using
`Postgres triggers <https://www.postgresql.org/docs/12/sql-createtrigger.html>`__.
Users can configure a number of event trackers to snapshot every model
change or to fire specific events when certain changes occur in the database.

In contrast with other Django auditing and history tracking apps
(seen `here <https://djangopackages.org/grids/g/model-audit/>`__),
``django-pghistory`` has the following advantages:

1. No instrumentation of model and queryset methods in order to properly
   track history. After configuring your model, events will be tracked
   automatically with no other changes to code. In contrast with
   apps like
   `django-reversion <https://django-reversion.readthedocs.io/en/stable/>`__,
   it is impossible for code to accidentally bypass history tracking, and users
   do not have to use a specific model/queryset interface to ensure history
   is correctly tracked.
2. Bulk updates and all other modifications to the database that do not fire
   Django signals will still be properly tracked.
3. Historical event modeling is completely controlled by the user and kept
   in sync with models being tracked. There are no cumbersome generic foreign
   keys and little dependence on unstructured JSON fields for tracking changes,
   making it easier to use the historical events in your application (and
   in a performant manner).
4. Changes to multiple objects in a request (or any level of granularity)
   can be grouped together under the same context. Although history tracking
   happens in Postgres triggers, application code can still attach metadata
   to historical events, such as the URL of the request, leading to a more
   clear and useful audit trail.

As mentioned, ``django-pghistory`` is built on top of
`Postgres triggers <https://www.postgresql.org/docs/12/sql-createtrigger.html>`__,
meaning that historical event tracking happens at the database level.
Because of this, history tracking data is 100% reliable and not susceptible
to race conditions.

Along with this, ``django-pghistory`` provides the ability for users to
make modeling decisions about how history is tracked that best suit their
application needs. For example,
`pghistory.track` allows one to track events to single fields, a combination
of fields, or entire model updates only when relevant fields are updated
or when conditions in the database hold true.

Although ``django-pghistory`` provides default history modeling out
of the box for various scenarios, users have the ability to extend and
customize models to suit their needs.

To get started, go to the :ref:`tutorial`. The tutorial covers how to
set up and configure automated event tracking in your application.

Also be sure to check out
:ref:`extras` for information about extra utilities in ``django-pghistory``.
This section covers some of the additional ways that one can access
and aggregate event history. It also shows examples of how one can integrate
history into the Django admin in place of it's default history pages.
