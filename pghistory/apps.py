import django.apps
from django.db.models.signals import class_prepared


def pgh_setup(sender, **kwargs):
    if hasattr(sender, "pghistory_setup"):
        sender.pghistory_setup()


class PGHistoryConfig(django.apps.AppConfig):
    name = "pghistory"

    def __init__(self, *args, **kwargs):
        """
        Install pgtriggers for Change detection models whenever
        the change detection model class is ready. We have to do this
        in __init__ instead of ready() here since the class_prepared
        signal is emitted before models are ready
        """
        class_prepared.connect(pgh_setup)
        super().__init__(*args, **kwargs)

    def ready(self):
        # Register custom checks
        from pghistory import checks  # noqa
