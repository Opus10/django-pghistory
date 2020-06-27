import django.apps


class PGHistoryTestsConfig(django.apps.AppConfig):
    name = 'pghistory.tests'

    def ready(self):
        import pghistory.models

        User = django.apps.apps.get_model('auth', 'User')
        # Track events to user group relationships
        pghistory.track(
            pghistory.AfterInsert('group.add'),
            pghistory.BeforeDelete('group.remove'),
            obj_fk=None,
            app_label='tests',
        )(User.groups.through)
