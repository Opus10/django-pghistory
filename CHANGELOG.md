# Changelog
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

