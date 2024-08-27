from django.contrib.auth.models import User
from django.db import models

import pghistory


@pghistory.track()
class SnapshotImageField(models.Model):
    img_field = models.ImageField()


class UntrackedModel(models.Model):
    untracked = models.CharField(max_length=64)


@pghistory.track()
class BigAutoFieldModel(models.Model):
    id = models.BigAutoField(primary_key=True)


@pghistory.track(context_field=pghistory.ContextJSONField())
@pghistory.track(
    pghistory.InsertEvent("snapshot_no_id_insert"),
    pghistory.UpdateEvent("snapshot_no_id_update"),
    obj_field=pghistory.ObjForeignKey(related_name="event_no_id"),
    context_field=pghistory.ContextJSONField(),
    context_id_field=None,
    model_name="DenormContextEventNoId",
)
class DenormContext(models.Model):
    """
    For testing denormalized context
    """

    int_field = models.IntegerField()
    fk_field = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True)


@pghistory.track(
    model_name="CustomModelSnapshot", obj_field=pghistory.ObjForeignKey(related_name="snapshot")
)
@pghistory.track(
    pghistory.UpdateEvent(
        "int_field_updated",
        condition=pghistory.AnyChange("int_field"),
    )
)
class CustomModel(models.Model):
    """
    For testing history tracking with a custom primary key
    and custom column name
    """

    my_pk = models.UUIDField(primary_key=True)
    int_field = models.IntegerField(db_column="integer_field")


@pghistory.track(obj_field=pghistory.ObjForeignKey(related_name="snapshot"), append_only=True)
class UniqueConstraintModel(models.Model):
    """For testing tracking models with unique constraints"""

    my_one_to_one = models.OneToOneField(CustomModel, on_delete=models.PROTECT)
    my_char_field = models.CharField(unique=True, max_length=32)
    my_int_field1 = models.IntegerField(db_index=True)
    my_int_field2 = models.IntegerField()

    class Meta:
        unique_together = [("my_int_field1", "my_int_field2")]


@pghistory.track(
    pghistory.InsertEvent("dt_field_snapshot_insert"),
    pghistory.UpdateEvent("dt_field_snapshot_update"),
    fields=["dt_field"],
    obj_field=pghistory.ObjForeignKey(related_name="dt_field_snapshot"),
)
@pghistory.track(
    pghistory.InsertEvent("dt_field_int_field_snapshot_insert"),
    pghistory.UpdateEvent("dt_field_int_field_snapshot_update"),
    fields=["dt_field", "int_field"],
    obj_field=pghistory.ObjForeignKey(related_name="dt_field_int_field_snapshot"),
)
@pghistory.track(
    pghistory.InsertEvent("snapshot_insert"),
    pghistory.UpdateEvent("snapshot_update"),
    model_name="SnapshotModelSnapshot",
    obj_field=pghistory.ObjForeignKey(related_name="snapshot"),
)
@pghistory.track(
    pghistory.InsertEvent("no_pgh_obj_snapshot_insert"),
    pghistory.UpdateEvent("no_pgh_obj_snapshot_update"),
    model_name="NoPghObjSnapshot",
    obj_field=None,
)
class SnapshotModel(models.Model):
    """
    For testing snapshots of a model or fields
    """

    dt_field = models.DateTimeField()
    int_field = models.IntegerField()
    fk_field = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True)


class CustomSnapshotModel(
    pghistory.create_event_model(
        SnapshotModel,
        pghistory.InsertEvent("custom_snapshot_insert"),
        pghistory.UpdateEvent("custom_snapshot_update"),
        exclude=["dt_field"],
        obj_field=pghistory.ObjForeignKey(
            related_name="custom_related_name",
            null=True,
            on_delete=models.SET_NULL,
        ),
        context_field=None,
    )
):
    fk_field = models.ForeignKey("auth.User", on_delete=models.CASCADE, null=True)
    # Add an extra field that's not on the original model to try to throw
    # tests off
    fk_field2 = models.ForeignKey(
        "auth.User",
        db_constraint=False,
        null=True,
        on_delete=models.DO_NOTHING,
        related_name="+",
        related_query_name="+",
    )


@pghistory.track(
    pghistory.ManualEvent("manual_event"),
    pghistory.InsertEvent("model.create"),
    pghistory.UpdateEvent("before_update", row=pghistory.Old),
    pghistory.DeleteEvent("before_delete", row=pghistory.Old),
    pghistory.UpdateEvent("after_update", condition=pghistory.AnyChange("dt_field")),
)
@pghistory.track(
    pghistory.Tracker("no_pgh_obj_manual_event"),
    obj_field=None,
    model_name="NoPghObjEvent",
)
class EventModel(models.Model):
    """
    For testing model events
    """

    dt_field = models.DateTimeField()
    int_field = models.IntegerField()


class CustomEventModel(
    pghistory.create_event_model(
        EventModel,
        pghistory.InsertEvent("model.custom_create"),
        fields=["dt_field"],
        context_field=None,
        obj_field=pghistory.ObjForeignKey(
            related_name="custom_related_name",
            null=True,
            on_delete=models.SET_NULL,
        ),
    )
):
    pass


CustomEventWithContext = pghistory.create_event_model(
    EventModel,
    pghistory.InsertEvent("model.custom_create_with_context"),
    abstract=False,
    model_name="CustomEventWithContext",
    obj_field=pghistory.ObjForeignKey(related_name="+"),
)


class CustomEventProxy(EventModel.pgh_event_models["model.create"]):
    url = pghistory.ProxyField("pgh_context__metadata__url", models.TextField(null=True))
    auth_user = pghistory.ProxyField(
        "pgh_context__metadata__user",
        models.ForeignKey("auth.User", on_delete=models.DO_NOTHING, null=True),
    )

    class Meta:
        proxy = True


class CustomEvents(pghistory.models.Events):
    user = models.ForeignKey("auth.User", on_delete=models.DO_NOTHING, null=True)
    url = pghistory.ProxyField("pgh_context__url", models.TextField(null=True))

    class Meta:
        proxy = True


@pghistory.track(
    pghistory.InsertEvent("group.add"),
    pghistory.DeleteEvent("group.remove"),
    obj_field=None,
)
class UserGroups(User.groups.through):
    class Meta:
        proxy = True


@pghistory.track(
    pghistory.UpdateEvent(row=pghistory.Old, condition=pghistory.AnyChange(exclude_auto=True)),
    pghistory.DeleteEvent(),
    obj_field=pghistory.ObjForeignKey(related_name="no_auto_fields_event"),
)
class IgnoreAutoFieldsSnapshotModel(models.Model):
    """For testing the IgnoreAutoFieldsSnapshot tracker"""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    my_char_field = models.CharField(max_length=32)
    my_int_field = models.IntegerField()
