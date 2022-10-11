.. _faq:

Frequently Asked Questions
==========================

How does ``django-pghistory`` track everything?
-----------------------------------------------

By using `Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__.
In other words, historical event records are created in the database alongside the database operation,
providing a reliable way to track events regardless of where it happens in your code.

Are triggers supported by Django?
---------------------------------

Triggers are not supported by Django directly, but ``django-pghistory`` uses
`django-pgtrigger <github.com/Opus10/django-pgtrigger>`__ to seamlessly integrate
them with your Django models.

How do I know triggers are working?
-----------------------------------

For those that are new to triggers and want additional confidence in their behavior,
try the following:

* Always write tests. Perform updates on your tracked models in
  automated tests and verify that the event models are created.
* Run ``python manage.py pgtrigger ls`` to verify that all triggers are installed.
* Run ``python manage.py check`` to ensure that there are no missing migrations for
  triggers.

What are the performance impacts?
---------------------------------

Although triggers will be issuing additional SQL statements to write events, keep in mind
that this happens within the database instance itself. In other words, writing events
does not incur additional expensive round-trip database calls. This results in a reduced
performance impact when compared to other history tracking methods implemented in software.

See the :ref:`performance` section for tips and tricks on large history tables.

How do I revert models?
-----------------------

Check out the :ref:`reversion` section.

How do I only track a subset of models?
---------------------------------------

Add a condition to your tracker. See the :ref:`conditional_tracking` subsection.

How do I track models with concrete inheritance?
------------------------------------------------

Currently concrete inheritance isn't well supported since ``django-pghistory``
simply snapshots the fields on the underlying table. Since concrete inheritance
uses foreign keys to other tables, you'll need to set up trackers on all tables.

We plan to add a guide on this in the future.

Can my event models be cascade deleted?
---------------------------------------

By default, event models use unconstrained foreign keys and instruct Django
to do nothing when tracked models are deleted. This applies not only
to the ``pgh_obj`` field that maintains a reference to the tracked model, but
every foreign key that's tracked.

You can configure the ``pgh_obj`` key globally by setting the
``settings.PGHISTORY_OBJ_FIELD`` with the proper configuration or by
setting it on a per-event-model basis with the ``obj_field`` option
to `pghistory.track`.

See the :ref:`event_models` section for details on how to set
configuration options for event models.

Can I use event models in my application?
-----------------------------------------

Yes, one of the strengths of ``django-pghistory`` is that it uses
structured event models that can be tailored to fit your application use case.

How can I keep the values of fields that have been removed?
-----------------------------------------------------------

The short answer is that you can't. ``django-pghistory`` is designed to create
event models that mirror the models they track, meaning the removal of a field
in a tracked model will also be removed in the event model.

If you need data for fields that have been dropped, we recommend two approaches:

1. Make the field nullable instead of removing it.
2. Use `django-pgtrigger <https://github.com/Opus10/django-pgtrigger>`__
   to create a custom trigger that dumps a JSON record of the row at that point
   in time.

How can I contact the author?
-----------------------------

The primary author, Wes Kendall, loves to talk to users. Message him at `wesleykendall@protonmail.com <mailto:wesleykendall@protonmail.com>`__ for any feedback. Any questions, feature requests, or bugs should
be reported as `issues here <https://github.com/Opus10/django-pghistory/issues>`__.

Wes and other `Opus 10 engineers <https://opus10.dev>`__ do contracting work, so keep them in mind if your company
uses Django.
