django-pghistory
################

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

To get started, read the `django-pghistory docs
<https://django-pghistory.readthedocs.io/>`__. The docs covers how to
set up and configure automated event tracking in your application, along
with how to aggregate events for objects and visualize them in your
admin/application.

Documentation
=============

`View the django-pghistory docs here
<https://django-pghistory.readthedocs.io/>`_.

Installation
============

Install django-pghistory with::

    pip3 install django-pghistory

After this, add ``pghistory`` and ``pgtrigger`` to the ``INSTALLED_APPS``
setting of your Django project.

Contributing Guide
==================

For information on setting up django-pghistory for development and
contributing changes, view `CONTRIBUTING.rst <CONTRIBUTING.rst>`_.

Primary Authors
===============

- @wesleykendall (Wes Kendall, wesleykendall@protonmail.com)

Other Contributors
==================

- @shivananda-sahu
- @asucrews
- @Azurency
- @dracos
- @adamchainz
- @eeriksp
