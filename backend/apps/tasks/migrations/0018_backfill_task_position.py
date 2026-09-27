from django.db import migrations


def backfill_task_position(apps, schema_editor):
    """Asigna ``position`` a las tareas anteriores al campo (todas a 0).

    Enumeración global por ``(created_at, id)``: la ordenación manual de
    la vista lista parte de un orden cronológico coherente. Las tareas
    con position != 0 (creadas por API entre deploy y migración) se
    dejan como están.
    """
    Task = apps.get_model("tasks", "Task")
    pending = Task.objects.filter(position=0).order_by("created_at", "id")
    for pos, task in enumerate(pending, start=1):
        Task.objects.filter(pk=task.pk).update(position=pos)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0017_backfill_task_seq"),
    ]

    operations = [
        migrations.RunPython(
            backfill_task_position, reverse_code=migrations.RunPython.noop
        ),
    ]
