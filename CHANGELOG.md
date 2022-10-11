# Changelog
## 2.5.0 (2022-10-10)
### Bug
  - Ignore tracking non-concrete fields [Wesley Kendall, e7b0589]

    If a field isn't concrete, pghistory no longer tries to track it.
  - Require ``django-pgtrigger>=4.5`` [Wesley Kendall, a70e0d3]

    Version 4.5 of ``django-pgtrigger`` fixes several bugs related to trigger migrations,
    especially as they relate to ``django-pghistory``.

    See the migration guide to ``django-pgtrigger`` version 4 at
    https://django-pgtrigger.readthedocs.io/en/4.5.3/upgrading.html#version-4. Upgrading
    from version 3 to 4 only affects mutli-database setups.
### Feature
  - Automatically add the "pgh_event_model" attribute to tracked models. [Wesley Kendall, 917c396]

    When a model is tracked, a "pgh_event_model" attribute is added to the tracked model to
    make it easier to inherit the event model and access it.
  - The label argument for ``pghistory.track`` is optional [Wesley Kendall, b6a8c99]

    The label argument was previously required. Now it defaults to the name of the tracker.
  - Simplify conditions for snapshots of all fields [Wesley Kendall, e9dbc06]

    Previously when using ``pghistory.Snapshot``, the condition for the trigger would OR
    together each field to verify nothing changed. Now ``OLD.* IS DISTINCT FROM NEW.*``
    is used as the condition.
  - Restructure documentation and add more tests [Wesley Kendall, 3bc868e]

    The documemntation was overhauled for the new features and
    admin integration.
  - Added reversion capability [Wesley Kendall, c2d8b90]

    A ``revert`` method was added to event models for reverting changes.
    The method only runs if the event model tracks every field, otherwise
    a ``Runtime`` error is thrown.
  - Use ProxyField() for defining proxy columns over attributes. [Wesley Kendall, a267478]

    When inheriting the ``Events`` model or individual event models,
    one can use the ``pghistory.ProxyField`` utility to proxy
    relationships from JSON columns into structured fields. For
    example, making a foreign key for users that proxies through the
    ``user`` attribute of context.

    Previously this behavior only worked on the deprecated
    ``AggregateEvent`` model by adding additional fields. Any
    fields that are proxied must now use the ``pghistory.ProxyField``
    utility.
  - Integration with Django admin [Wesley Kendall, a9fea95]

    Installing ``pghistory.admin`` to ``settings.INSTALLED_APPS``
    will provide the following:

    * An "Events" admin page that other admins can use to display events
    * Dynamic buttons on tracked models that redirect to a pre-filtered
      events admin
    * The ability to make admins for specific event models and have them
      show up as buttons on their associated tracked model admin pages

    The default events admin has configuration parameters that can
    be set via settings.
  - New event model configuration and new aggregate ``Events`` model. [Wes Kendall, c1120f2]

    Event models can be configured with global settings
    and with overrides on a per-event-model basis.
    Previous arguments to ``pghistory.track``, such as
    ``obj_fk`` and ``context_fk`` have been deprecated
    in place of ``obj_field`` and ``context_field``.
    These new fields, along with their associated settings,
    use ``pghistory.Field`` configuration instances.

    Along with this, the ``AggregateEvent`` model has been deprecated
    in favor of the ``Events`` proxy model. The new
    ``Events`` model has similar fields and operates the same way, and
    it also has other methods for filtering aggregate events.
### Trivial
  - Rename "tracking" module to "runtime" module. [Wesley Kendall, 43645ea]

## 2.4.2 (2022-10-06)
### Trivial
  - Update with the latest Python template [Wesley Kendall, ef2fb6e]

## 2.4.1 (2022-09-13)
### Trivial
  - Ensure installation of pghistory context function is installed across multiple databases [Wes Kendall, d06c758]

## 2.4.0 (2022-09-07)
### Bug
  - Fix issues related to the ``dumpdata`` command [Wes Kendall, 8cb8036]

    Django's ``dumpdata`` command is now compatible with pghistory's AggregateEvent
    model.

## 2.3.0 (2022-09-06)
### Bug
  - Check that "pgtrigger" is in settings.INSTALLED_APPS [Wes Kendall, fa86205]

    A check is registered with Django's check framework to verify that
    "pgtrigger" is in settings.INSTALLED_APPS when using ``django-pghistory``.

    Docs were also updated to note the requirement of pgtrigger in INSTALLED_APPS.
  - Install context tracking function in a migration [Wes Kendall, 516dc14]

    The Postgres pghistory function is now installed in a migration, alleviating
    issues that would happen when trying to migrate pghistory triggers.

## 2.2.2 (2022-09-02)
### Trivial
  - Reference PK of user instead of ID in middleware for DRF-based flows [Wes Kendall, 2193e2b]

## 2.2.1 (2022-09-02)
### Trivial
  - Do additional safety checks in middleware [Wes Kendall, 9678d83]

## 2.2.0 (2022-09-02)
### Feature
  - Configure middleware tracked methods [Wes Kendall, e931757]

    Use ``settings.PGHISTORY_MIDDLEWARE_METHODS`` to configure which methods
    are tracked in the middleware. Defaults to ``("GET", "POST", "PUT", "PATCH", "DELETE")``.

## 2.1.1 (2022-08-31)
### Trivial
  - Format trigger SQL for better compatibility with ``django-pgtrigger``>=4.5 [Wes Kendall, fa04191]

## 2.1.0 (2022-08-27)
### Feature
  - Add setting to configure JSON encoder for context. [Zac Miller, 430225f]

    ``django-pghistory`` now uses Django's default JSON encoder
    to serialize contexts, which supports datetimes, UUIDs,
    and other fields.

    You can override the JSON encoder by setting
    ``PGHISTORY_JSON_ENCODER`` to the path of the class.
### Trivial
  - Local development enhancements [Wes Kendall, 95a5b1d]

## 2.0.3 (2022-08-26)
### Trivial
  - Test against Django 4.1 and other CI improvements [Wes Kendall, 953fe1d]

## 2.0.2 (2022-08-24)
### Trivial
  - Fix ReadTheDocs builds [Wes Kendall, afbc33e]

## 2.0.1 (2022-08-20)
### Trivial
  - Fix release note rendering and code formatting changes [Wes Kendall, 7043553]

## 2.0.0 (2022-08-08)
### Api-Break
  - Integration with Django's migration system [Wes Kendall, e0acead]

    ``django-pghistory`` upgrades ``django-pgtrigger``, which now integrates
    with the Django migration system.

    Run ``python manage.py makemigrations`` to make migrations for the triggers
    created by ``django-pghistory`` in order to upgrade.

    If you are tracking changes to third-party models, register the tracker on
    a proxy model so that migrations are created in the proper app.
### Feature
  - Remove dependency on ``django-pgconnection`` [Wes Kendall, aea6056]

    ``django-pghistory`` no longer requires that users wrap ``settings.DATABASES``
    with ``django-pgconnection``.

## 1.5.2 (2022-07-31)
### Trivial
  - Updated with latest Django template, fixing doc builds [Wes Kendall, 42cbc3c]

## 1.5.1 (2022-07-31)
### Trivial
  - Use `pk` instead of `id` to get the user's primary key [Eerik Sven Puudist, f105828]
  - Fix default_app_config warning on Django 3.2+ [Adam Johnson, 8753bc4]

## 1.5.0 (2022-05-17)
### Feature
  - Add support for GET requests in pghistory middleware [Shivananda Sahu, ae2524e]

    Currently the middleware adds a context for POST, PUT, PATCH and DELETE requests. Updating middleware to add a context for GET requests along with POST, PUT, PATCH and DELETE.

## 1.4.0 (2022-03-13)
### Feature
  - Allow target() to receive a queryset or list. [M Somerville, 0f34e91]

    This expands the target() function to accept a queryset or a list of
    objects on top of the existing one object.
  - Add support for delete requests in pghistory middleware [Shivananda Sahu, 322d17e]

    Currently the middleware adds a context for POST, PUT, and PATCH requests. This leaves out DELETE requests as the only ones that can affect a model without a context. Updating middleware to add a context for DELETE requests along with POST, PUT and PATCH.
### Trivial
  - Minor code formatting fixes [Wes Kendall, d0b7664]

## 1.3.0 (2022-03-13)
### Bug
  - Fixed bug in BeforeDelete event [Wes Kendall, aab4182]

    The BeforeDelete event was referencing the wrong trigger value (NEW).
    Code was updated to reference the proper OLD row for this event,
    and a failing test case was added.

## 1.2.2 (2022-03-13)
### Trivial
  - Updated with latest template, dropping 3.6 support and adding Django 4 support [Wes Kendall, c160973]

## 1.2.1 (2021-05-30)
### Trivial
  - Updated with latest python template [Wes Kendall, 09f6cfb]

## 1.2.0 (2020-10-23)
### Feature
  - Upgrade pgtrigger and test against Django 3.1 [Wes Kendall, 176fb13]

    Uses the latest version of django-pgtrigger. Also tests against Django 3.1
    and fixes a few bugs related to internal changes in the Django codebase.

## 1.1.0 (2020-08-04)
### Bug
  - Escape single quotes in tracked context [Wes Kendall, 40f758e]

    Invalid SQL was generated from context values with single quotes when
    using ``pghistory.context``. Single quotes are now properly escaped, and
    a failing test case was created to cover this scenario.

## 1.0.1 (2020-06-29)
### Trivial
  - Updated with the latest public django app template. [Wes Kendall, fc1f3e4]

## 1.0.0 (2020-06-27)
### Api-Break
  - Initial release of django-pghistory. [Wes Kendall, ecfcf96]

    ``django-pghistory`` provides automated and customizable history
    tracking for Django models using
    [Postgres triggers](https://www.postgresql.org/docs/12/sql-createtrigger.html).
    Users can configure a number of event trackers to snapshot every model
    change or to fire specific events when certain changes occur in the database.

    In contrast with other Django auditing and history tracking apps
    (seen [here](https://djangopackages.org/grids/g/model-audit/)),
    ``django-pghistory`` has the following advantages:

    1. No instrumentation of model and queryset methods in order to properly
       track history. After configuring your model, events will be tracked
       automatically with no other changes to code. In contrast with
       apps like
       [django-reversion](https://django-reversion.readthedocs.io/en/stable/),
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

