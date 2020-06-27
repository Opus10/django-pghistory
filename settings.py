import dj_database_url
import pgconnection


SECRET_KEY = 'django-pghistory'
# Install the tests as an app so that we can make test models
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'pghistory',
    'pghistory.tests',
    'pgconnection',
    'pgtrigger',
    'django_extensions',
]
# Database url comes from the DATABASE_URL env var
DATABASES = pgconnection.configure({'default': dj_database_url.config()})
# Force postgres timezones to be UTC for tests
USE_TZ = True
TIMEZONE = 'UTC'
# For testing middleware
ROOT_URLCONF = 'pghistory.tests.urls'
MIDDLEWARE = ['pghistory.middleware.HistoryMiddleware']
