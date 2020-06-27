from django import urls
from django.contrib.auth.models import User
import pytest

import pghistory.middleware
import pghistory.tests.models as test_models
import pghistory.tracking


@pytest.mark.django_db
def test_post(client):
    """Tests a post to a test URL with the middleware enabled

    The user created and set as the request user in the view.
    It should still be tracked in the history context
    """
    assert not User.objects.exists()
    client.post(urls.reverse('test_view'))

    assert User.objects.count() == 1
    assert test_models.SnapshotModel.objects.count() == 1
    assert test_models.SnapshotModelSnapshot.objects.count() == 1

    user = User.objects.get()
    assert (
        test_models.SnapshotModelSnapshot.objects.get().pgh_context.metadata[
            'user'
        ]
        == user.id
    )


def test_middleware(rf, mocker):
    """
    Verifies pghistory context is tracked during certain requests
    with middleware in pghistory.middleware
    """

    def get_response(request):
        return getattr(pghistory.tracking._tracker, 'value', None)

    resp = pghistory.middleware.HistoryMiddleware(get_response)(
        rf.get('/get/url/')
    )
    # No tracking should be happening since this is a GET request
    assert resp is None

    # A POST request will initiate the tracker
    resp = pghistory.middleware.HistoryMiddleware(get_response)(
        rf.post('/post/url/')
    )
    assert resp.metadata == {'url': '/post/url/', 'user': None}

    # Authenticated users will be tracked
    request = rf.post('/post/url2/')
    request.user = mocker.Mock(id=3)
    resp = pghistory.middleware.HistoryMiddleware(get_response)(request)
    assert resp.metadata == {'url': '/post/url2/', 'user': 3}
