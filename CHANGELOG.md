# Changelog
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

