from django import urls

from pghistory.tests import views

urlpatterns = [
    urls.path('test-view', views.MyPostView.as_view(), name='test_view')
]
