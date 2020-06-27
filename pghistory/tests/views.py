from django import http
from django import views
from django.contrib.auth.models import User
from django.utils import timezone

import pghistory.tests.models as test_models


class MyPostView(views.View):
    def post(self, request, *args, **kwargs):
        user = User.objects.create(username='username')
        request.user = user
        test_models.SnapshotModel.objects.create(
            dt_field=timezone.now(), int_field=1, fk_field=user
        )
        return http.HttpResponse()
