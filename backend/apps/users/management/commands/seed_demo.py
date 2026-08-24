"""Seed the database with realistic demo data.

Usage:
    python manage.py seed_demo          # Create demo data
    python manage.py seed_demo --clean  # Delete demo data first, then recreate
"""

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import (
    Task, Subtask, Comment, Sprint, Epic, TimeEntry,
    TaskTemplate, CustomField, TaskRelation, TaskActivity,
)
from apps.collaboration.models import Team, TeamMembership
from apps.automations.models import AutomationRule
from apps.okrs.models import Objective, KeyResult

User = get_user_model()

DEMO_EMAIL = "demo@todolist.com"
DEMO_PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Crea datos de demo realistas para probar la aplicación."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Eliminar datos demo existentes antes de crear nuevos.",
        )

    def handle(self, *args, **options):
        if options["clean"]:
            self._clean()

        self.stdout.write(self.style.SUCCESS("=== Creando datos demo ==="))

        user = self._create_user()
        projects = self._create_projects(user)
        tags = self._create_tags(user)
        epics = self._create_epics(user, projects)
        sprints = self._create_sprints(user, projects)
        tasks = self._create_tasks(user, projects, sprints, epics, tags)
        self._create_subtasks(tasks)
        self._create_comments(user, tasks)
        self._create_time_entries(user, tasks)
        self._create_task_relations(tasks)
        self._create_teams(user)
        self._create_templates(user, projects)
        self._create_custom_fields(projects)
        self._create_automations(user)
        self._create_okrs(user)

        self.stdout.write(self.style.SUCCESS("\n=== Datos demo creados ==="))
        self.stdout.write(f"  Usuario: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        self.stdout.write(f"  Proyectos: {len(projects)}")
        self.stdout.write(f"  Épicas: {len(epics)}")
        self.stdout.write(f"  Sprints: {len(sprints)}")
        self.stdout.write(f"  Tareas: {len(tasks)}")
        self.stdout.write(f"  Etiquetas: {len(tags)}")

    def _clean(self):
        self.stdout.write("Limpiando datos demo...")
        TaskRelation.objects.all().delete()
        TimeEntry.objects.all().delete()
        Subtask.objects.all().delete()
        Comment.objects.all().delete()
        TaskActivity.objects.all().delete()
        Task.objects.all().delete()
        TaskTemplate.objects.all().delete()
        CustomField.objects.all().delete()
        Sprint.objects.all().delete()
        Epic.objects.all().delete()
        AutomationRule.objects.all().delete()
        KeyResult.objects.all().delete()
        Objective.objects.all().delete()
        TeamMembership.objects.all().delete()
        Team.objects.all().delete()
        Tag.objects.all().delete()
        Project.objects.all().delete()
        User.objects.filter(email=DEMO_EMAIL).delete()
        self.stdout.write(self.style.WARNING("Datos limpiados."))

    def _create_user(self):
        user, created = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={"username": "demo_user", "is_active": True},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.stdout.write(f"  Usuario creado: {user.email}")
        else:
            self.stdout.write(f"  Usuario existente: {user.email}")
        return user

    def _create_projects(self, user):
        data = [
            ("App Móvil React Native", "Desarrollo de app móvil para iOS y Android con React Native, incluyendo auth, push notifications y offline sync.", "#1976d2"),
            ("Migración a Microservicios", "Migrar monolito a arquitectura de microservicios con Docker y Kubernetes.", "#7b1fa2"),
            ("Rediseño Web E-commerce", "Rediseño completo del e-commerce: nueva UI, checkout optimizado, pasarela de pago.", "#388e3c"),
        ]
        projects = []
        for name, desc, color in data:
            p, _ = Project.objects.get_or_create(
                name=name, owner=user,
                defaults={"description": desc, "color": color},
            )
            projects.append(p)
        self.stdout.write(f"  Proyectos: {len(projects)}")
        return projects

    def _create_tags(self, user):
        tag_data = [
            ("bug", "#f44336"), ("feature", "#4caf50"), ("urgent", "#ff9800"),
            ("frontend", "#2196f3"), ("backend", "#9c27b0"), ("devops", "#607d8b"),
            ("design", "#e91e63"), ("api", "#00bcd4"), ("database", "#795548"),
            ("security", "#f44336"), ("performance", "#ff5722"), ("refactor", "#9e9e9e"),
            ("documentation", "#3f51b5"), ("testing", "#8bc34a"), ("mobile", "#009688"),
        ]
        tags = []
        for name, color in tag_data:
            t, _ = Tag.objects.get_or_create(name=name, owner=user, defaults={"color": color})
            tags.append(t)
        self.stdout.write(f"  Etiquetas: {len(tags)}")
        return tags

    def _create_epics(self, user, projects):
        epics_data = [
            ("Autenticación OAuth 2.0", "Implementar login con Google, Apple y Facebook", projects[0], "#1976d2", "in_progress"),
            ("Sincronización Offline", "Cache local y sync cuando haya conexión", projects[0], "#1976d2", "planned"),
            ("API Gateway", "Implementar gateway con rate limiting y auth", projects[1], "#7b1fa2", "in_progress"),
            ("Service Mesh", "Configurar Istio para comunicación entre servicios", projects[1], "#7b1fa2", "planned"),
            ("Nueva Homepage", "Rediseñar landing page con nuevo branding", projects[2], "#388e3c", "completed"),
        ]
        epics = []
        today = timezone.now().date()
        for title, desc, project, color, state in epics_data:
            e, _ = Epic.objects.get_or_create(
                title=title, owner=user, project=project,
                defaults={
                    "description": desc, "color": color, "state": state,
                    "start_date": today - timedelta(days=60),
                    "end_date": today + timedelta(days=30),
                },
            )
            epics.append(e)
        self.stdout.write(f"  Épicas: {len(epics)}")
        return epics

    def _create_sprints(self, user, projects):
        today = timezone.now().date()
        sprints_data = [
            ("Sprint 14 - Auth & Landing", "Completar auth OAuth y landing page", projects[0], "closed", today - timedelta(days=28), today - timedelta(days=15)),
            ("Sprint 15 - Offline Sync", "Implementar sync offline básico", projects[0], "closed", today - timedelta(days=14), today - timedelta(days=1)),
            ("Sprint 16 - API Gateway", "Gateway con rate limiting y JWT", projects[1], "active", today, today + timedelta(days=13)),
            ("Sprint 17 - Service Mesh", "Configurar Istio y observabilidad", projects[1], "planned", today + timedelta(days=14), today + timedelta(days=27)),
            ("Sprint 12 - Checkout", "Optimizar checkout y pasarela", projects[2], "closed", today - timedelta(days=42), today - timedelta(days=29)),
        ]
        sprints = []
        for name, goal, project, state, start, end in sprints_data:
            s, _ = Sprint.objects.get_or_create(
                name=name, owner=user, project=project,
                defaults={"goal": goal, "state": state, "start_date": start, "end_date": end},
            )
            sprints.append(s)
        self.stdout.write(f"  Sprints: {len(sprints)}")
        return sprints

    def _create_tasks(self, user, projects, sprints, epics, tags):
        now = timezone.now()
        tasks_data = [
            # Project 0: App Móvil
            ("Implementar login con Google", "Integrar Google Sign-In SDK en la app móvil", projects[0], sprints[0], epics[0], "completed", 1, "feature", 5, 8, [tags[1], tags[3], tags[14]], now - timedelta(days=20)),
            ("Implementar login con Apple", "Integrar Sign in with Apple", projects[0], sprints[0], epics[0], "completed", 1, "feature", 5, 5, [tags[1], tags[3], tags[14]], now - timedelta(days=18)),
            ("Pantalla de registro", "Crear formulario de registro con validación", projects[0], sprints[1], epics[0], "in_progress", 2, "feature", 3, 3, [tags[3], tags[6]], now + timedelta(days=3)),
            ("Refresh token flow", "Implementar renovación automática de tokens", projects[0], sprints[1], epics[0], "in_progress", 1, "feature", 3, 5, [tags[4], tags[9]], now + timedelta(days=5)),
            ("Cache local con AsyncStorage", "Implementar cache offline para tareas", projects[0], sprints[1], epics[1], "pending", 3, "feature", 8, 13, [tags[3], tags[4]], now + timedelta(days=10)),
            ("Conflict resolution strategy", "Definir estrategia para conflictos de sync", projects[0], None, epics[1], "backlog", 3, "research", 5, None, [tags[4]], None),
            ("Push notifications APNS", "Configurar push notifications para iOS", projects[0], None, None, "backlog", 4, "feature", 3, None, [tags[3], tags[14]], None),
            ("Bug: crash al cerrar sesión", "La app crashea al cerrar sesión con token expirado", projects[0], sprints[1], None, "blocked", 0, "bug", 1, 2, [tags[0], tags[2], tags[14]], now - timedelta(days=2)),
            ("Tests E2E auth flow", "Tests end-to-end del flujo de autenticación", projects[0], sprints[1], epics[0], "review", 2, "task", 3, 5, [tags[13]], now + timedelta(days=1)),
            ("Documentar API auth", "Documentar endpoints de auth con OpenAPI", projects[0], None, epics[0], "pending", 4, "docs", 2, 3, [tags[12], tags[7]], now + timedelta(days=7)),

            # Project 1: Microservicios
            ("Configurar API Gateway con Kong", "Instalar y configurar Kong como gateway", projects[1], sprints[2], epics[2], "in_progress", 1, "task", 8, 13, [tags[5], tags[7]], now + timedelta(days=6)),
            ("Rate limiting por usuario", "Implementar rate limiting con Redis", projects[1], sprints[2], epics[2], "pending", 2, "feature", 5, 8, [tags[4], tags[5], tags[10]], now + timedelta(days=8)),
            ("JWT auth middleware", "Middleware para validar JWT en todos los servicios", projects[1], sprints[2], epics[2], "in_progress", 1, "feature", 3, 5, [tags[4], tags[9]], now + timedelta(days=4)),
            ("Dockerizar servicio de usuarios", "Crear Dockerfile y docker-compose para users service", projects[1], sprints[2], None, "completed", 3, "task", 2, 3, [tags[5]], now - timedelta(days=5)),
            ("CI/CD pipeline con GitHub Actions", "Pipeline de deploy automático", projects[1], sprints[2], None, "review", 2, "task", 5, 8, [tags[5]], now + timedelta(days=2)),
            ("Istio service mesh setup", "Configurar Istio en Kubernetes", projects[1], None, epics[3], "backlog", 3, "task", 13, None, [tags[5]], None),
            ("Observabilidad con Jaeger", "Distributed tracing con Jaeger", projects[1], None, epics[3], "backlog", 4, "task", 8, None, [tags[5], tags[10]], None),
            ("Bug: memory leak en user service", "Memory leak detectado en producción", projects[1], sprints[2], None, "blocked", 0, "bug", 3, 5, [tags[0], tags[2], tags[10]], now - timedelta(days=1)),
            ("Refactorizar conexión pool DB", "Mejorar pool de conexiones a PostgreSQL", projects[1], None, None, "pending", 3, "tech_debt", 5, 8, [tags[11], tags[8]], now + timedelta(days=14)),
            ("Migrar schema a PostgreSQL 16", "Upgrade de PostgreSQL 14 a 16", projects[1], None, None, "backlog", 4, "task", 3, None, [tags[8], tags[5]], None),

            # Project 2: E-commerce
            ("Nueva landing page", "Rediseñar homepage con nuevo branding", projects[2], sprints[4], epics[4], "completed", 2, "feature", 8, 13, [tags[3], tags[6]], now - timedelta(days=35)),
            ("Componente hero animado", "Hero section con animaciones Lottie", projects[2], sprints[4], epics[4], "completed", 3, "feature", 3, 5, [tags[3], tags[6]], now - timedelta(days=33)),
            ("Checkout en un solo paso", "Simplificar checkout a una sola página", projects[2], sprints[4], None, "completed", 1, "feature", 8, 8, [tags[3], tags[4]], now - timedelta(days=30)),
            ("Integrar Stripe Payment Intent", "Pasarela de pago con Stripe", projects[2], sprints[4], None, "completed", 1, "feature", 5, 8, [tags[4], tags[9]], now - timedelta(days=32)),
            ("Bug: carrito pierde items al recargar", "Items del carrito se pierden en refresh", projects[2], None, None, "in_progress", 0, "bug", 2, 3, [tags[0], tags[3]], now + timedelta(days=1)),
            ("Optimizar imágenes producto", "Lazy loading y WebP para imágenes", projects[2], None, None, "pending", 3, "improvement", 3, 5, [tags[3], tags[10]], now + timedelta(days=5)),
            ("Búsqueda con Elasticsearch", "Implementar búsqueda full-text con ES", projects[2], None, None, "backlog", 2, "feature", 13, None, [tags[4], tags[8]], None),
            ("Filtros por categoría y precio", "Sistema de filtros en catálogo", projects[2], None, None, "pending", 3, "feature", 5, 8, [tags[3], tags[4]], now + timedelta(days=9)),
            ("Documentar API e-commerce", "Documentar endpoints REST del e-commerce", projects[2], None, None, "backlog", 4, "docs", 3, None, [tags[12], tags[7]], None),
            ("Tests de carga checkout", "Tests de carga con k6 para checkout", projects[2], None, None, "review", 2, "task", 3, 5, [tags[13], tags[10]], now + timedelta(days=3)),

            # Tareas generales (sin proyecto)
            ("Revisar PRs pendientes", "Revisar pull requests acumulados", None, None, None, "pending", 2, "task", 1, 1, [tags[13]], now + timedelta(days=1)),
            ("Actualizar dependencias npm", "Actualizar paquetes npm obsoletos", None, None, None, "backlog", 4, "tech_debt", 2, None, [tags[11]], None),
            ("Configurar Sentry", "Integrar Sentry para error tracking", None, None, None, "completed", 3, "task", 1, 2, [tags[5]], now - timedelta(days=10)),
        ]

        tasks = []
        for (title, desc, project, sprint, epic, state, priority,
             ttype, sp, est, task_tags, due) in tasks_data:
            t = Task.objects.create(
                title=title,
                description=desc,
                state=state,
                priority=priority,
                task_type=ttype,
                story_points=sp,
                estimate_hours=est,
                owner=user,
                project=project,
                sprint=sprint,
                epic=epic,
                due_date=due,
                completed_at=now - timedelta(days=random.randint(1, 20)) if state == "completed" else None,
            )
            if task_tags:
                t.tags.set(task_tags)
            tasks.append(t)
        self.stdout.write(f"  Tareas: {len(tasks)}")
        return tasks

    def _create_subtasks(self, tasks):
        subtask_data = {
            2: ["Validar email", "Validar contraseña fuerte", "Confirmar contraseña", "Aceptar términos"],
            3: ["Implementar refresh endpoint", "Manejar expiración", "Tests unitarios", "Tests de integración"],
            4: ["Diseñar schema de cache", "Implementar AsyncStorage wrapper", "Sync queue", "Conflict resolver"],
            10: ["Instalar Kong", "Configurar rutas", "Setup plugins", "Documentar configuración"],
            11: ["Diseñar algoritmo", "Implementar con Redis", "Tests de carga", "Documentar"],
            22: ["Diseñar UI", "Implementar componente", "Tests E2E", "Deploy a staging"],
            23: ["Crear cuenta Stripe", "Integrar Payment Intent API", "Webhook handling", "Tests"],
        }
        count = 0
        for task_idx, items in subtask_data.items():
            if task_idx < len(tasks):
                for i, title in enumerate(items):
                    Subtask.objects.create(
                        task=tasks[task_idx],
                        title=title,
                        is_done=tasks[task_idx].state == "completed",
                        order=i,
                    )
                    count += 1
        self.stdout.write(f"  Subtareas: {count}")

    def _create_comments(self, user, tasks):
        comments_data = [
            (7, "He podido reproducir el crash. Parece que ocurre cuando el token ya expiró y se intenta hacer logout."),
            (7, "El problema está en el interceptor de Axios. No maneja bien el 401 en el logout."),
            (17, "El memory leak viene del pool de conexiones. No se cierran las conexiones correctamente."),
            (17, "He profileado con clinic.js y confirma que el leak está en pg-pool. Hay que configurar max y idleTimeout."),
            (24, "No consigo reproducirlo. ¿Pasaba con un usuario concreto o con cualquier sesión?"),
            (24, "Parece que solo pasa cuando se añaden items sin estar logueado. El localStorage se sobreescribe."),
            (0, "¡Login con Google funcionando en iOS! 🎉"),
            (10, "Kong instalado y configurado. Falta añadir los plugins de rate limiting y JWT."),
        ]
        count = 0
        for task_idx, body in comments_data:
            if task_idx < len(tasks):
                Comment.objects.create(task=tasks[task_idx], author=user, body=body)
                count += 1
        self.stdout.write(f"  Comentarios: {count}")

    def _create_time_entries(self, user, tasks):
        now = timezone.now()
        entries = [
            (0, 7200, "Implementación completa del login con Google", now - timedelta(days=20, hours=3)),
            (1, 5400, "Integración Sign in with Apple", now - timedelta(days=18, hours=2)),
            (2, 3600, "Diseño de la pantalla de registro", now - timedelta(days=5, hours=4)),
            (2, 5400, "Implementación de validaciones", now - timedelta(days=4, hours=2)),
            (3, 4800, "Endpoint de refresh token", now - timedelta(days=3, hours=5)),
            (10, 9000, "Configuración inicial de Kong", now - timedelta(days=6, hours=8)),
            (11, 3600, "Investigación de rate limiting con Redis", now - timedelta(days=2, hours=3)),
            (12, 7200, "JWT middleware implementado", now - timedelta(days=1, hours=4)),
            (13, 1800, "Dockerfile del user service", now - timedelta(days=7, hours=2)),
            (20, 14400, "Landing page completa", now - timedelta(days=35, hours=6)),
            (22, 10800, "Checkout en un solo paso", now - timedelta(days=30, hours=10)),
            (23, 7200, "Integración Stripe Payment Intent", now - timedelta(days=32, hours=5)),
            (24, 2700, "Debug del bug del carrito", now - timedelta(days=1, hours=3)),
        ]
        count = 0
        for task_idx, duration, desc, started in entries:
            if task_idx < len(tasks):
                TimeEntry.objects.create(
                    task=tasks[task_idx],
                    user=user,
                    duration_seconds=duration,
                    description=desc,
                    started_at=started,
                    ended_at=started + timedelta(seconds=duration),
                )
                count += 1
        self.stdout.write(f"  Registros de tiempo: {count}")

    def _create_task_relations(self, tasks):
        relations = [
            (3, 4, "blocks"),      # Refresh token blocks cache
            (4, 5, "blocks"),      # Cache blocks conflict resolution
            (10, 11, "blocks"),    # Gateway blocks rate limiting
            (10, 12, "related"),   # Gateway related to JWT middleware
            (12, 13, "related"),   # JWT related to Docker users
            (20, 21, "related"),   # Landing related to hero
            (22, 23, "depends_on"),# Checkout depends on Stripe
            (0, 8, "related"),     # Google login related to E2E tests
        ]
        count = 0
        for src_idx, tgt_idx, rel_type in relations:
            if src_idx < len(tasks) and tgt_idx < len(tasks):
                TaskRelation.objects.get_or_create(
                    source=tasks[src_idx],
                    target=tasks[tgt_idx],
                    defaults={"relation_type": rel_type},
                )
                count += 1
        self.stdout.write(f"  Relaciones: {count}")

    def _create_teams(self, user):
        teams_data = [
            ("Equipo Frontend", "Desarrolladores frontend: React, React Native, CSS"),
            ("Equipo Backend", "Desarrolladores backend: Django, PostgreSQL, Docker"),
            ("Equipo DevOps", "Infraestructura, CI/CD, Kubernetes, monitoring"),
        ]
        count = 0
        for name, desc in teams_data:
            t, _ = Team.objects.get_or_create(
                name=name, owner=user,
                defaults={"slug": name.lower().replace(" ", "-"), "description": desc},
            )
            TeamMembership.objects.get_or_create(
                team=t, user=user,
                defaults={"role": "owner"},
            )
            count += 1
        self.stdout.write(f"  Equipos: {count}")

    def _create_templates(self, user, projects):
        templates = [
            ("Bug Report", "Plantilla para reportar bugs", projects[0], {
                "title": "[Bug] ", "description": "## Descripción\n\n## Pasos para reproducir\n1.\n2.\n3.\n\n## Comportamiento esperado\n\n## Comportamiento actual\n\n## Entorno\n- OS:\n- Versión app:",
                "priority": 0, "state": "pending", "task_type": "bug",
            }),
            ("Feature Request", "Plantilla para solicitar nuevas funcionalidades", projects[0], {
                "title": "[Feature] ", "description": "## Motivación\n\n## Propuesta\n\n## Alternativas consideradas\n\n## Criterios de aceptación\n- [ ] \n- [ ] ",
                "priority": 3, "state": "backlog", "task_type": "feature",
            }),
            ("Documentación", "Plantilla para tareas de documentación", None, {
                "title": "[Docs] ", "description": "## Qué documentar\n\n## Audiencia\n\n## Outline\n1. Introducción\n2. \n3. ",
                "priority": 4, "state": "pending", "task_type": "docs",
            }),
        ]
        count = 0
        for name, desc, project, data in templates:
            TaskTemplate.objects.get_or_create(
                name=name, owner=user,
                defaults={"description": desc, "project": project, "template_data": data},
            )
            count += 1
        self.stdout.write(f"  Plantillas: {count}")

    def _create_custom_fields(self, projects):
        cf_data = [
            (projects[0], "Cliente", "select", ["Interno", "Cliente A", "Cliente B", "Cliente C"]),
            (projects[0], "Severidad", "select", ["Crítica", "Alta", "Media", "Baja"]),
            (projects[1], "Componente", "select", ["API Gateway", "Auth Service", "User Service", "DB"]),
            (projects[1], "Versión", "text", []),
            (projects[2], "Tipo de bug", "select", ["Visual", "Funcional", "Performance", "Seguridad"]),
            (projects[2], "URL afectada", "url", []),
        ]
        count = 0
        for project, name, ftype, options in cf_data:
            CustomField.objects.get_or_create(
                project=project, name=name,
                defaults={"field_type": ftype, "options": options, "is_required": False},
            )
            count += 1
        self.stdout.write(f"  Campos personalizados: {count}")

    def _create_automations(self, user):
        rules = [
            ("Auto P0 en bloqueo", "Cuando una tarea pasa a blocked, asignar prioridad P0", "task_blocked", "set_priority", {"priority": 0}),
            ("Notificar tareas vencidas", "Cuando una tarea vence, crear notificación", "task_overdue", "create_notification", {"message": "Tarea vencida"}),
            ("Subtareas a in_progress", "Cuando una tarea se completa, mover subtareas a in_progress", "task_completed", "subtasks_in_progress", {}),
        ]
        count = 0
        for name, desc, trigger, action, params in rules:
            AutomationRule.objects.get_or_create(
                name=name, owner=user,
                defaults={"description": desc, "trigger": trigger, "action": action, "action_params": params, "enabled": True},
            )
            count += 1
        self.stdout.write(f"  Automatizaciones: {count}")

    def _create_okrs(self, user):
        today = timezone.now().date()
        year = today.year
        quarter = f"Q{(today.month - 1) // 3 + 1}"

        objectives_data = [
            ("Mejorar calidad del código", "Reducir bugs en producción y mejorar cobertura de tests", [
                ("Reducir bugs en producción a < 5/mes", 10, 3, "count"),
                ("Aumentar cobertura de tests a 80%", 80, 45, "percentage"),
                ("Reducir tiempo de CI a < 10 min", 30, 18, "minutes"),
            ]),
            ("Acelerar delivery", "Reducir time-to-market de nuevas features", [
                ("Deploy 2 features/semana", 8, 5, "count"),
                ("Reducir lead time a < 3 días", 7, 5, "days"),
                ("Sprint completion rate > 90%", 90, 75, "percentage"),
            ]),
            ("Mejorar experiencia móvil", "App más rápida y estable", [
                ("Reducir crash rate a < 0.5%", 1, 2, "percentage"),
                ("App startup < 2 segundos", 2, 3, "seconds"),
                ("Rating App Store > 4.5", 5, 4, "count"),
            ]),
        ]

        count = 0
        for title, desc, krs in objectives_data:
            obj, _ = Objective.objects.get_or_create(
                title=title, owner=user, quarter=quarter, year=year,
                defaults={"description": desc, "status": "in_progress", "progress": 50},
            )
            for kr_title, target, current, unit in krs:
                KeyResult.objects.get_or_create(
                    objective=obj, title=kr_title, owner=user,
                    defaults={"target_value": target, "current_value": current, "unit": unit},
                )
                count += 1
        self.stdout.write(f"  OKRs: {len(objectives_data)} objetivos, {count} key results")
