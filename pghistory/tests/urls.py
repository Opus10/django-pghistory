from django import urls
from django.contrib import admin

from pghistory.tests import views

urlpatterns = [
    urls.path("test-view", views.MyPostView.as_view(), name="test_view"),
    urls.path("admin/", admin.site.urls),
]
