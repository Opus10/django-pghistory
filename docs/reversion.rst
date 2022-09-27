.. _reversion:

Reverting Objects
=================

Objects can be reverted using the ``revert`` method on the event model.
This only works for event models that track every field. Trying to
revert an event model that doesn't track every field will result
in a ``RuntimeError``.

For example, say that we have a model with a `pghistory.Snapshot` tracker:

.. code-block:: python

    @pghistory.track(
        pghistory.Snapshot("snapshot"),
        obj_field=pghistory.ObjForeignKey(related_name="events"),
    )
    class MyModel(models.Model):
        # Fields go here ...

        def rewind(self):
            """Rewind to the previous version"""
            try:
                return self.events.order_by("-pgh_id")[1].revert()
            except IndexError:
                return self

Above we've set up a tracker to track snapshots. The object field on the
snapshot model has a related name of "events", allowing us to make
a ``rewind`` method on ``MyModel`` to revert it back to the previous
version.

Note that we use the second-to-last snapshot in ``rewind`` above. This
is because the latest snapshot always contains the current version
of the model.

.. note::

    We are open to adding more functionality and a possible
    admin integration for reversion if there's demand. Please consider
    `opening an issue here <https://github.com/opus10/django-pghistory/issues>`__
    if there's a use case you're trying to solve.
