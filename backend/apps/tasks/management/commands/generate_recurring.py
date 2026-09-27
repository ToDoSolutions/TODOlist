"""Management command para generar tareas recurrentes pendientes.

Uso:
    python manage.py generate_recurring

Equivalente a la tarea de Celery ``apps.tasks.tasks.generate_recurring_tasks``,
útil para ejecución manual o vía cron externo.
"""
from django.core.management.base import BaseCommand

from apps.tasks.tasks import _generate_recurring_tasks


class Command(BaseCommand):
    help = (
        "Genera las ocurrencias pendientes de todas las reglas de "
        "recurrencia activas (hasta/count no superados)."
    )

    def handle(self, *args, **options):
        summary = _generate_recurring_tasks()

        self.stdout.write(
            self.style.SUCCESS(
                "Reglas procesadas: {rules_processed} | "
                "Tareas creadas: {tasks_created} | "
                "Errores: {errors}".format(
                    rules_processed=summary["rules_processed"],
                    tasks_created=summary["tasks_created"],
                    errors=len(summary["errors"]),
                )
            )
        )

        for err in summary["errors"]:
            self.stderr.write(
                self.style.ERROR(
                    "Regla {rule_id}: {error}".format(**err)
                )
            )
