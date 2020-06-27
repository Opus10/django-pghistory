from django.db import models
import pgtrigger

import pghistory


class UntrackedModel(models.Model):
    untracked = models.CharField(max_length=64)


@pghistory.track(
    pghistory.Snapshot('snapshot'),
    model_name='CustomModelSnapshot',
    related_name='snapshot',
)
@pghistory.track(
    pghistory.AfterUpdate(
        'int_field_updated',
        condition=pgtrigger.Q(
            old__int_field__df=pgtrigger.F('new__int_field')
        ),
    )
)
class CustomModel(models.Model):
    """
    For testing history tracking with a custom primary key
    and custom column name
    """

    my_pk = models.UUIDField(primary_key=True)
    int_field = models.IntegerField(db_column='integer_field')


@pghistory.track(pghistory.Snapshot('snapshot'), related_name='snapshot')
class UniqueConstraintModel(models.Model):
    """For testing tracking models with unique constraints"""

    my_one_to_one = models.OneToOneField(CustomModel, on_delete=models.PROTECT)
    my_char_field = models.CharField(unique=True, max_length=32)
    my_int_field1 = models.IntegerField(db_index=True)
    my_int_field2 = models.IntegerField()

    class Meta:
        unique_together = [('my_int_field1', 'my_int_field2')]


@pghistory.track(
    pghistory.Snapshot('dt_field_snapshot'),
    fields=['dt_field'],
    related_name='dt_field_snapshot',
)
@pghistory.track(
    pghistory.Snapshot('dt_field_int_field_snapshot'),
    fields=['dt_field', 'int_field'],
    related_name='dt_field_int_field_snapshot',
)
@pghistory.track(
    pghistory.Snapshot('snapshot'),
    related_name='snapshot',
    model_name='SnapshotModelSnapshot',
)
@pghistory.track(
    pghistory.Snapshot('no_pgh_obj_snapshot'),
    obj_fk=None,
    related_name='no_pgh_obj_snapshot',
    model_name='NoPghObjSnapshot',
)
class SnapshotModel(models.Model):
    """
    For testing snapshots of a model or fields
    """

    dt_field = models.DateTimeField()
    int_field = models.IntegerField()
    fk_field = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True
    )


class CustomSnapshotModel(
    pghistory.get_event_model(
        SnapshotModel,
        pghistory.Snapshot('custom_snapshot'),
        exclude=['dt_field'],
        obj_fk=models.ForeignKey(
            SnapshotModel,
            related_name='custom_related_name',
            null=True,
            on_delete=models.SET_NULL,
        ),
        context_fk=None,
    )
):
    fk_field = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, null=True
    )
    # Add an extra field that's not on the original model to try to throw
    # tests off
    fk_field2 = models.ForeignKey(
        'auth.User',
        db_constraint=False,
        null=True,
        on_delete=models.DO_NOTHING,
        related_name='+',
        related_query_name='+',
    )


@pghistory.track(
    pghistory.Event('manual_event'),
    pghistory.AfterInsert('model.create'),
    pghistory.BeforeUpdate('before_update'),
    pghistory.AfterUpdate(
        'after_update',
        condition=pgtrigger.Q(old__dt_field__df=pgtrigger.F('new__dt_field')),
    ),
)
@pghistory.track(
    pghistory.Event('no_pgh_obj_manual_event'),
    obj_fk=None,
    model_name='NoPghObjEvent',
    related_name='no_pgh_obj_event',
)
class EventModel(models.Model):
    """
    For testing model events
    """

    dt_field = models.DateTimeField()
    int_field = models.IntegerField()


class CustomEventModel(
    pghistory.get_event_model(
        EventModel,
        pghistory.AfterInsert('model.custom_create'),
        fields=['dt_field'],
        context_fk=None,
        obj_fk=models.ForeignKey(
            EventModel,
            related_name='custom_related_name',
            null=True,
            on_delete=models.SET_NULL,
        ),
    )
):
    pass


class CustomAggregateEvent(pghistory.models.BaseAggregateEvent):
    user = models.ForeignKey(
        'auth.User', on_delete=models.DO_NOTHING, null=True
    )
    url = models.TextField(null=True)

    class Meta:
        managed = False
