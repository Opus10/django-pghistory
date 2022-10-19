import os

import dj_database_url


SECRET_KEY = "django-pghistory"
# Install the tests as an app so that we can make test models
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "pghistory",
    "pgtrigger",
    "django_extensions",
]

# Conditionally add the test app when we aren't building docs,
# otherwise sphinx builds won't work
if not os.environ.get("SPHINX"):
    INSTALLED_APPS += ["pghistory.tests"]

# Database url comes from the DATABASE_URL env var
DATABASES = {"default": dj_database_url.config()}
# Force postgres timezones to be UTC for tests
USE_TZ = True
TIMEZONE = "UTC"
# For testing middleware
ROOT_URLCONF = "pghistory.tests.urls"
MIDDLEWARE = ["pghistory.middleware.HistoryMiddleware"]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
