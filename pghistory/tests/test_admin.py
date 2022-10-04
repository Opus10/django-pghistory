import bs4
import ddf
from django import urls
import pytest

from pghistory import models
from pghistory.admin import core as admin
import pghistory.tests.models as test_models


@pytest.fixture
def authed_user():
    return ddf.G("auth.User", is_superuser=True, is_staff=True)


@pytest.fixture
def authed_client(client, authed_user):
    client.force_login(authed_user)
    return client


def test_get_model_doesnt_exist():
    """Tests admin._get_model when the model doesnt exist"""
    assert not admin._get_model("bad.model")


def test_get_obj_model_doesnt_exist():
    """Tests admin._get_obj when the model doesnt exist"""
    assert not admin._get_obj("bad.model:1")


@pytest.mark.django_db
def test_events_page(authed_client, settings):
    """Verify pghistory events page with different settings and filters"""
    ddf.G(test_models.CustomModel)
    ddf.G(test_models.UniqueConstraintModel)
    ddf.G(test_models.SnapshotModel)

    url = urls.reverse("admin:pghistory_events_changelist")

    resp = authed_client.get(url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Check some of the known labels that should be in filters
    assert "By label" in html
    assert "after_update" in html
    assert "snapshot_no_id" in html

    # Check some of the event models
    assert "By event model" in html
    assert "tests.CustomEventModel" in html
    assert "tests.DenormContextEvent" in html

    num_events = models.Events.objects.count()
    assert num_events > 0
    assert f"{num_events} events" in html

    # Filter by event model
    resp = authed_client.get(url + "?event_model=tests.customsnapshotmodel")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "1 event" in html

    # Filter by label
    resp = authed_client.get(url + "?label=snapshot")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    num_events = models.Events.objects.filter(pgh_label="snapshot").count()
    assert f"{num_events} event" in html

    # Don't show events on unfiltered views
    settings.PGHISTORY_ADMIN_ALL_EVENTS = False

    resp = authed_client.get(url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "0 events" in html


@pytest.mark.django_db
def test_events_links(authed_client):
    """Ensure the events aggregate page is linked in appropriate admin pages"""
    custom_model = ddf.G(test_models.CustomModel)
    ddf.G(test_models.UniqueConstraintModel)
    ddf.G(test_models.SnapshotModel)

    # Go to the changelist page, verify that the "Events" button is present,
    # click on it, and verify it filters properly
    url = urls.reverse("admin:tests_custommodel_changelist")
    resp = authed_client.get(url)
    assert resp.status_code == 200
    soup = bs4.BeautifulSoup(resp.content, features="html5lib")
    events_url = soup.find("a", href=True, class_="events-admin")["href"]
    resp = authed_client.get(events_url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    assert 'title="tests.CustomModel"' in html
    soup = bs4.BeautifulSoup(resp.content, features="html5lib")
    back_url = soup.find("a", href=True, class_="back")["href"]
    assert back_url == url

    # Go to an individual event in the change page, verify the "Events"
    # button filters by the object.
    url = urls.reverse("admin:tests_custommodel_change", kwargs={"object_id": custom_model.pk})
    resp = authed_client.get(url)
    assert resp.status_code == 200
    soup = bs4.BeautifulSoup(resp.content, features="html5lib")
    events_url = soup.find("a", href=True, class_="events-admin")["href"]
    resp = authed_client.get(events_url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert f'title="tests.CustomModel:{custom_model.pk}"' in html

    # Verify the back button works
    soup = bs4.BeautifulSoup(resp.content, features="html5lib")
    back_url = soup.find("a", href=True, class_="back")["href"]
    assert back_url == url

    # Try a different filter method
    references_url = events_url.replace("tracks", "references")
    assert "method=references" in references_url
    resp = authed_client.get(references_url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_event_links(authed_client):
    """Ensure the individual event pages are linked properly"""
    snapshot = ddf.G(test_models.SnapshotModel)

    # Go to an individual change page and verify the snapshot model admin button shows
    url = urls.reverse("admin:tests_snapshotmodel_change", kwargs={"object_id": snapshot.pk})
    resp = authed_client.get(url)
    assert resp.status_code == 200
    soup = bs4.BeautifulSoup(resp.content, features="html5lib")
    event_url = soup.find("a", href=True, class_="event-admin")["href"]
    assert "snapshotmodelsnapshot" in event_url
    resp = authed_client.get(event_url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert f'title="tests.SnapshotModel:{snapshot.pk}"' in html

    # Verify the back button works
    soup = bs4.BeautifulSoup(resp.content, features="html5lib")
    back_url = soup.find("a", href=True, class_="back")["href"]
    assert back_url == url
