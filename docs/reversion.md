# Reverting Objects

Objects can be reverted using the `revert` method on the event model. This only works for event models that track every field. Trying to revert an event model that doesn't track every field will result in a `RuntimeError`.

For example, say that we have a tracked model:

```python
@pghistory.track()
class MyModel(models.Model):
    # Fields go here ...

    def rewind(self):
        """Rewind to the previous version"""
        try:
            return self.events.order_by("-pgh_id")[1].revert()
        except IndexError:
            return self
```

The `rewind` method on `MyModel` will revert it back to the previous version if it exists. Note that we use the second-to-last event in `rewind` above. This is because the latest snapshot always contains the current version of the model by default.

!!! note

    We are open to adding more functionality and a possible admin integration for reversion if there's demand. Please consider [opening an issue here](https://github.com/opus10/django-pghistory/issues) if there's a use case you're trying to solve.
