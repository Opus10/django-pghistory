Installation
============

Install django-pghistory with::

    pip3 install django-pghistory

After this, add ``pghistory`` to the ``INSTALLED_APPS``
setting of your Django project.

``pghistory`` uses ``django-pgtrigger`` and ``django-pgconnection`` as
dependencies. Although these are automatically installed, the user
needs to add ``pgtrigger`` and ``pgconnection`` to
``settings.INSTALLED_APPS``, along with properly setting up
``django-pgconnection`` in ``settings.py`` as follows::

    import pgconnection

    DATABASES = pgconnection.configure({
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'mydatabase',
        }
    })
