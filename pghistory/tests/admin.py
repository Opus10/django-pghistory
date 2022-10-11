from django.contrib import admin

from pghistory.admin import EventModelAdmin
import pghistory.tests.models as test_models


admin.site.register(test_models.UntrackedModel)

admin.site.register(test_models.DenormContext)

admin.site.register(test_models.CustomModel)

admin.site.register(test_models.CustomModelSnapshot)

admin.site.register(test_models.UniqueConstraintModel)

admin.site.register(test_models.SnapshotModel)

admin.site.register(test_models.CustomSnapshotModel)

admin.site.register(test_models.EventModel)


class SnapshotModelSnapshotAdmin(EventModelAdmin):
    pass


admin.site.register(test_models.SnapshotModelSnapshot, SnapshotModelSnapshotAdmin)


class EventModelEventAdmin(EventModelAdmin):
    pass


admin.site.register(test_models.EventModelEvent, EventModelEventAdmin)


class CustomEventModelAdmin(EventModelAdmin):
    pass


admin.site.register(test_models.CustomEventModel, CustomEventModelAdmin)


class CustomEventProxyAdmin(EventModelAdmin):
    list_display = ["id", "url", "auth_user"]


admin.site.register(test_models.CustomEventProxy, CustomEventProxyAdmin)
