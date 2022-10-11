import pgtrigger
import pytest


@pytest.mark.django_db
def test_trigger_install():
    """Do a full uninstall/install of triggers to fully exercise the function rendering code"""
    pgtrigger.uninstall()
    pgtrigger.install()
