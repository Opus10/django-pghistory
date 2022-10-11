.. _performance:

Performance and Scaling
=======================

Here we overview some of the main things to consider regarding performance
and scale. It's useful to consider some of these recommendations before using
``django-pghistory`` because some changes can involve tricky migrations if
done after the fact.

Trigger Execution
-----------------

`Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__
are used to store events. When using a `pghistory.Snapshot` tracker, for example,
this means a snapshot of your model is saved every time it is created or updated.
In other words, an ``INSERT`` statement for the event table is ran alongside the
query that creates or updates data on the tracked model.

While this will have a performance impact when creating or updating models, keep
in mind that triggers run in the database and do not require expensive round trips
from the application. This can result in substantially better performance when
compared to traditional history tracking solutions that are implemented in the
application and do separate round trips.

When triggers execute, the following happens:

1. By default, context will be updated or inserted into the main ``Context`` model's table.
2. A new entry will be made in the event table.

The following sections discuss considerations to help the performance of both
operations in the trigger.

Ignoring Context
----------------

If you don't want to attach context to events, set ``settings.PGHISTORY_CONTEXT_FIELD`` to
``None``. All event models won't include the ``pgh_context`` field, and the associated
context operations won't happen.

.. note::

    You can still track context on a per-event-model basis with the ``context_field``
    argument to `pghistory.track`.

Denormalizing Context
---------------------

As discussed in the :ref:`denormalizing_context` section, you can avoid doing an update
or insert on the main context table and instead duplicate the context data on the event
model. This not only reduces the overhead of maintaining an index to the context table
from the event table, but it also reduces the contention on a shared context table among
multiple event triggers.

Large amounts of events should also be taken into consideration too. As the context table
grows, so will the indices and the associated time it takes to update the index.
Denormalizing context reduces the overhead at the expense of more storage. It also
makes it easier to partition your event tables.

Indices and Foreign Key Constraints
-----------------------------------

By default, all event tables use unconstrained foreign keys. Event tables also drop
all indices except for foreign keys.

If you don't plan to query or join your event models, you may not need to index the foreign
keys. You could instead set the default foreign key behavior to:

.. code-block:: python

    PGHISTORY_FOREIGN_KEY_FIELD = pghistory.ForeignKey(db_index=False)

Keep in mind that this could negatively impact the performance of the admin integration. If you want
to continue using core admin functionality, be sure to index the object field,
otherwise the foreign key settings will override it:

.. code-block:: python

   PGHISTORY_OBJ_FIELD = pghistory.ObjForeignKey(db_index=True)

If you prefer that your foreign keys have referential integrity, do:

.. code-block:: python

    PGHISTORY_FOREIGN_KEY_FIELD = pghistory.ForeignKey(
        db_constraint=True,
        on_delete=pghistory.DEFAULT
    )

Remember that there will be a performance hit for maintaining the foreign key constraint, and Django
will also have to cascade delete more models.

The ``Events`` Proxy Model
--------------------------

The `pghistory.models.Events` proxy model uses a common table expression (CTE) across event tables
to query an aggregate view of data. Postgres 12 optimizes filters on CTEs, but you may experience
performance issues if trying to directly filter ``Events`` on earlier versions of Postgres.

See :ref:`aggregating_events` for more information on how to use the special model manager
methods to more efficiently filter events.
