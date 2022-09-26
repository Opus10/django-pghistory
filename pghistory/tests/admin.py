from django.contrib import admin

from pghistory.admin import EventModelAdmin
import pghistory.tests.models as test_models


class UntrackedModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.UntrackedModel, UntrackedModelAdmin)


class DenormContextAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.DenormContext, DenormContextAdmin)


class CustomModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.CustomModel, CustomModelAdmin)


class CustomModelSnapshotAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.CustomModelSnapshot, CustomModelSnapshotAdmin)


class UniqueConstraintModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.UniqueConstraintModel, UniqueConstraintModelAdmin)


class SnapshotModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.SnapshotModel, SnapshotModelAdmin)


class SnapshotModelSnapshotAdmin(EventModelAdmin):
    pass


admin.site.register(test_models.SnapshotModelSnapshot, SnapshotModelSnapshotAdmin)


class CustomSnapshotModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.CustomSnapshotModel, CustomSnapshotModelAdmin)


class EventModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.EventModel, EventModelAdmin)


class CustomEventModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(test_models.CustomEventModel, CustomEventModelAdmin)


class CustomEventProxyAdmin(admin.ModelAdmin):
    list_display = ["id", "url", "auth_user"]


admin.site.register(test_models.CustomEventProxy, CustomEventProxyAdmin)
