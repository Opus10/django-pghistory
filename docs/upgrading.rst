.. _upgrading:

Upgrading
=========

Version 2
---------

To upgrade to version 2, the majority of people can simply run
``python manage.py makemigrations`` to make the migrations for the triggers.
If, however, you are tracking third-party models, you will need to register trackers on proxy models.
Otherwise trigger migrations will be created outside of your project.

**Important** - Please be sure you have ``django-pgtrigger>=4.5`` installed, otherwise
``django-pghistory`` might be susceptible to some migration-related bugs

For example, this is how you can track changes to Django's user model:

.. code-block:: python

    # Track the user model, excluding the password field
    @pghistory.track(
        pghistory.Snapshot('user.snapshot'),
        exclude=['password'],
    )
    class UserProxy(User):
        class Meta:
            proxy = True

The same syntax is also used for default many-to-many "through" models. For example, this is how one
tracks changes to group add/remove events on the user model:

.. code-block:: python

  from django.contrib.auth.models import User
  import pghistory

  # Track add and remove events to user groups
  @pghistory.track(
      pghistory.AfterInsert('group.add'),
      pghistory.BeforeDelete('group.remove'),
      obj_fk=None,
  )
  class UserGroups(User.groups.through):
      class Meta:
          proxy = True

Maintaining legacy behavior
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to disable ``django-pgtrigger`` integration with migrations entirely,
set ``settings.PGTRIGGER_MIGRATIONS`` to ``False``.
Setting this along with ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True``
will preserve the legacy behavior of how triggers were installed. It is not recommend to do this
since migrations fix legacy trigger installation bugs.

Version 2.5
-----------

Although version 2.5 remains backwards compatible, it deprecates arguments
and functionality in preparation for removal in version 3.
Below are the deprecated changes.

``pghistory.track``
~~~~~~~~~~~~~~~~~~~

* The ``obj_fk`` argument is deprecated in favor of ``obj_field``. The new
  argument must be supplied a `pghistory.ObjForeignKey` instance.
  See :ref:`event_models` for more information on the new configuration
  methods.
* The ``context_fk`` argument is deprecated in favor of ``context_field``.
  The new argument must be a `pghistory.ContextForeignKey`. If you're
  denormalizing context, it must be a `pghistory.ContextJSONField` argument.
  See :ref:`event_models` for more information on the new configuration
  methods and context denormalization.
* The ``related_name`` argument is deprecated. Supply the ``related_name``
  argument to the instance of the ``obj_field`` argument. For example,
  ``obj_field=pghistory.ObjForeignKey(related_name="events")``.

``pghistory.get_event_model``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Deprecated and renamed to `pghistory.create_event_model`.
* Along with the changed arguments from `pghistory.track`, the ``name``
  argument has been deprecated in favor of ``model_name``.

``pghistory.models.AggregateEvent``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Deprecated in favor of `pghistory.models.Events`. The core fields from the original
  model are there with other additions and renamed fields. See
  :ref:`aggregating_events` for more information.
* ``objects.target`` is deprecated and renamed to ``objects.references``
* Additional fields on proxy models must use `pghistory.ProxyField` to declare the field.
  See :ref:`events_proxy` for more information.

``pghistory.Event``
~~~~~~~~~~~~~~~~~~~

* Deprecated and renamed to `pghistory.Tracker`.

``pghistory.DatabaseEvent``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Deprecated and renamed to `pghistory.DatabaseTracker`.