import django.apps
from django.db.models.signals import class_prepared
from django.db.models.signals import post_migrate


def install_pgh_attach_context_func(**kwargs):
    """
    Installs a special stored procedure used by pghistory that makes
    it easier to manually and automatically construct context for
    history
    """
    Context = django.apps.apps.get_model("pghistory", "Context")
    Context.install_pgh_attach_context_func()


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
        post_migrate.connect(install_pgh_attach_context_func, sender=self)
