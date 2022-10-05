.. _settings:

Settings
========

Below are all settings for ``django-pghistory``.

PGHISTORY_MIDDLEWARE_METHODS
----------------------------

Set the HTTP methods tracked by the middleware.

**Default** ``("GET", "POST", "PUT", "PATCH", "DELETE")``

PGHISTORY_JSON_ENCODER
----------------------

The JSON encoder class or class path to use when serializing
context.

**Default** ``"django.core.serializers.json.DjangoJSONEncoder"``

PGHISTORY_BASE_MODEL
--------------------

The base model to use for event models.

**Default** ``pghistory.models.Event``

PGHISTORY_FIELD
---------------

The default configuration for fields in event models.

**Default** ``pghistory.Field()``

PGHISTORY_RELATED_FIELD
-----------------------

The default configuration for related fields in event models.

**Default** ``pghistory.RelatedField()``

PGHISTORY_FOREIGN_KEY_FIELD
---------------------------

The default configuration for foreign keys in event models.

**Default** ``pghistory.ForeignKey()``

PGHISTORY_CONTEXT_FIELD
-----------------------

The default configuration for the ``pgh_context`` field.

**Default** ``pghistory.ContextForeignKey()``

PGHISTORY_CONTEXT_ID_FIELD
--------------------------

The default configuration for the ``pgh_context_id`` field
when ``pghistory.ContextJSONField`` is used for the ``pgh_context``
field.

**Default** ``pghistory.ContextUUIDField()``

PGHISTORY_OBJ_FIELD
-------------------

The default configuration for the ``pgh_obj`` field.

**Default** ``pghistory.ObjForeignKey()``

PGHISTORY_ADMIN_ORDERING
------------------------

The default ordering for the ``Events`` admin.

**Default** ``"-pgh_created_at"``

PGHISTORY_ADMIN_MODEL
---------------------

The default model or model label for the ``Events`` admin.

**Default** ``"pghistory.Events"``

PGHISTORY_ADMIN_QUERYSET
------------------------

The default queryset for the ``Events`` admin. If set,
``PGHISTORY_ADMIN_MODEL`` will be ignored.

**Default** Uses ``PGHISTORY_ADMIN_MODEL`` ordered by ``PGHISTORY_ADMIN_ORDERING``.

PGHISTORY_ADMIN_CLASS
---------------------

The admin class to use. Must subclass `pghistory.admin.EventsAdmin`.

**Default** ``"pghistory.admin.EventsAdmin"``

PGHISTORY_ADMIN_ALL_EVENTS
--------------------------

``True`` if all events should be able to be displayed in the default
Django ``Events`` admin page without filtering.

**Default** ``True``

.. note::

    This setting only works in Django 3.1 and above.

PGHISTORY_ADMIN_LIST_DISPLAY
----------------------------

The default fields shown in the ``Events`` admin.

**Default** ``["pgh_created_at", "pgh_obj_model", "pgh_obj_id", "pgh_diff"]``. If
``pghistory.MiddlewareEvents`` is the event model, the "user" and "url" fields will
be added.

