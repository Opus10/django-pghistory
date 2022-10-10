.. _troubleshooting:

Troubleshooting
===============

If you have issues with the triggers that are installed by ``django-pghistory``,
we recommend reading
`django-pgtrigger's troubleshooting guide <https://django-pgtrigger.readthedocs.io/en/latest/troubleshooting.html>`__.
It goes over most of the core issues that might happen when creating or migrating triggers.

A tracked field cannot be created
---------------------------------

Special fields, such as Django's ``ImageField`` cannot be supplied some of the core field parameter overrides
supplied, such as the ``primary_key`` attribute.

If a custom field errors because of invalid arguments, use ``settings.PGHISTORY_EXCLUDE_FIELD_KWARGS``.
See the :ref:`settings section here <exclude_field_kwargs>` for an example.