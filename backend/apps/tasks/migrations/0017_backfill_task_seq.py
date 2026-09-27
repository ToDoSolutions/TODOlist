from django.db import migrations


def backfill_task_seq(apps, schema_editor):
    """Asigna ``seq`` por proyecto a las tareas existentes.

    Enumeración por ``(created_at, id)`` dentro de cada proyecto. Las
    tareas que ya tengan un ``seq`` distinto de 0 (creadas entre el
    deploy del código y la migración) conservan su valor pero cuentan
    en la numeración, evitando duplicados.
    """
    Task = apps.get_model("tasks", "Task")
    project_ids = (
        Task.objects.exclude(project_id=None)
        .values_list("project_id", flat=True)
        .distinct()
    )
    for project_id in project_ids:
        tasks = Task.objects.filter(project_id=project_id).order_by(
            "created_at", "id"
        )
        for seq, task in enumerate(tasks, start=1):
            if task.seq == 0:
                Task.objects.filter(pk=task.pk).update(seq=seq)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0016_task_section_task_seq"),
    ]

    operations = [
        migrations.RunPython(
            backfill_task_seq, reverse_code=migrations.RunPython.noop
        ),
    ]
