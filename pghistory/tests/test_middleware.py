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
    assert test_models.SnapshotModelSnapshot.objects.get().pgh_context.metadata['user'] == user.id


def test_middleware(rf, mocker):
    """
    Verifies pghistory context is tracked during certain requests
    with middleware in pghistory.middleware
    """

    def get_response(request):
        return getattr(pghistory.tracking._tracker, 'value', None)

    resp = pghistory.middleware.HistoryMiddleware(get_response)(rf.get('/get/url/'))
    # No tracking should be happening since this is a GET request
    assert resp is None

    # A POST request will initiate the tracker
    resp = pghistory.middleware.HistoryMiddleware(get_response)(rf.post('/post/url/'))
    assert resp.metadata == {'url': '/post/url/', 'user': None}

    # Authenticated users will be tracked
    mock_user_id = 3
    mock_user = mocker.Mock(id=mock_user_id)
    request = rf.post('/post/url2/')
    request.user = mock_user
    resp = pghistory.middleware.HistoryMiddleware(get_response)(request)
    assert resp.metadata == {'url': '/post/url2/', 'user': mock_user_id}

    # PATCH requests initiate the tracker
    patch_url = '/patch/url/'
    request = rf.patch(patch_url)
    request.user = mock_user
    resp = pghistory.middleware.HistoryMiddleware(get_response)(request)
    assert resp.metadata == {'url': patch_url, 'user': mock_user_id}

    # PUT requests initiate the tracker
    put_url = '/put/url/'
    request = rf.put(put_url)
    request.user = mock_user
    resp = pghistory.middleware.HistoryMiddleware(get_response)(request)
    assert resp.metadata == {'url': put_url, 'user': mock_user_id}

    # DELETE requests initiate the tracker
    delete_url = '/delete/url/'
    request = rf.delete(delete_url)
    request.user = mock_user
    resp = pghistory.middleware.HistoryMiddleware(get_response)(request)
    assert resp.metadata == {'url': delete_url, 'user': mock_user_id}
