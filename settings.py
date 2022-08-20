import dj_database_url


SECRET_KEY = "django-pghistory"
# Install the tests as an app so that we can make test models
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "pghistory",
    "pghistory.tests",
    "pgtrigger",
    "django_extensions",
]
# Database url comes from the DATABASE_URL env var
DATABASES = {"default": dj_database_url.config()}
# Force postgres timezones to be UTC for tests
USE_TZ = True
TIMEZONE = "UTC"
# For testing middleware
ROOT_URLCONF = "pghistory.tests.urls"
MIDDLEWARE = ["pghistory.middleware.HistoryMiddleware"]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
