from django.core.management import call_command
from django.core.management.base import SystemCheckError
import pytest


@pytest.mark.django_db
def test_checks(settings):
    call_command("check")

    # Note: We can't call .remove(), otherwise it leaks into other tests
    settings.INSTALLED_APPS = [
        app for app in settings.INSTALLED_APPS if app not in ("pgtrigger", "pghistory.admin")
    ]

    # Try a management command. This checks that our check is properly registered
    # and fails
    with pytest.raises(SystemCheckError, match='Add "pgtrigger" to settings.INSTALLED_APPS'):
        call_command("check")
