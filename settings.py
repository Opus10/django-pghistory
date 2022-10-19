import os

import dj_database_url


SECRET_KEY = "django-pghistory"
# Install the tests as an app so that we can make test models
INSTALLED_APPS = [
    "pghistory",
    "pghistory.admin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "pghistory.middleware.HistoryMiddleware",
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Options for testing the admin locally and in tests
ALLOWED_HOSTS = []
DEBUG = True
ROOT_URLCONF = "pghistory.tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pghistory.tests.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"
