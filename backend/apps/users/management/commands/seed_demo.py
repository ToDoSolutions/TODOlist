"""Seed the database with realistic demo data.

Usage:
    python manage.py seed_demo          # Create demo data
    python manage.py seed_demo --clean  # Delete demo data first, then recreate
"""

import random
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ai_assistant.models import AiSuggestion
from apps.automations.models import AutomationLog, AutomationRule, SlaPolicy
from apps.collaboration.models import (
    AuditLog,
    Invitation,
    Meeting,
    Mention,
    Organization,
    OrganizationMembership,
    ProjectMember,
    Team,
    TeamMembership,
    Whiteboard,
)
from apps.dashboards.models import Dashboard, ShareLink
from apps.encryption.models import (
    EncryptedKeyShare,
    EncryptedTask,
    UserPublicKey,
)
from apps.feature_flags.models import FeatureFlag
from apps.intake.models import IntakeForm
from apps.integrations.models import (
    GitHubCheckRun,
    GitHubCommit,
    GitHubInstallation,
    GitHubIssueLink,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
    WebhookDelivery,
)
from apps.integrations_chat.models import ChatIntegration, ChatMessageLog
from apps.notifications.models import Notification
from apps.offline_sync.models import SyncDevice, SyncOperation
from apps.okrs.models import KeyResult, KeyResultUpdate, Objective
from apps.projects.models import Portfolio, Project, ProjectRisk
from apps.tags.models import Tag
from apps.tasks.models import (
    Comment,
    CustomField,
    CustomFieldValue,
    Epic,
    OutgoingWebhook,
    RecurrenceRule,
    SavedSearch,
    Sprint,
    Subtask,
    Task,
    TaskActivity,
    TaskRelation,
    TaskTemplate,
    TimeEntry,
)
from apps.users.models import APIKey

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
        extra_users = self._create_extra_users()
        projects = self._create_projects(user)
        tags = self._create_tags(user)
        epics = self._create_epics(user, projects)
        sprints = self._create_sprints(user, projects)
        tasks = self._create_tasks(user, projects, sprints, epics, tags)
        self._create_subtasks(tasks)
        comments = self._create_comments(user, tasks)
        self._create_time_entries(user, tasks)
        self._create_task_relations(tasks)
        self._create_teams(user, extra_users)
        self._create_project_members(user, projects, extra_users)
        self._create_templates(user, projects)
        custom_fields = self._create_custom_fields(projects)
        self._create_custom_field_values(tasks, custom_fields)
        automations = self._create_automations(user)
        self._create_okrs(user)
        # New: fill all previously empty tables
        self._create_feature_flags(user)
        self._create_outgoing_webhooks(user)
        self._create_webhook_deliveries()
        self._create_notifications(user, tasks, sprints)
        self._create_invitations(user, projects)
        self._create_mentions(user, tasks, comments, extra_users)
        self._create_audit_logs(user, tasks, projects)
        self._create_automation_logs(automations)
        self._create_key_result_updates(user)
        self._create_chat_integrations(user)
        self._create_sync_devices(user)
        self._create_encryption_data(user, tasks)
        self._create_recurrence_rules(user)
        self._create_saved_searches(user)
        self._create_task_activities(user, tasks)
        self._create_api_keys(user)
        self._create_ai_suggestions(user, tasks)
        self._create_risks(user, projects)
        self._create_dashboards(user)
        self._create_organization(user, projects, extra_users)
        self._create_sla_policies(user)
        self._create_meetings(user, projects, tasks, extra_users)
        self._create_share_links(user, projects)
        self._create_intake_forms(user, projects)
        self._create_whiteboards(user, projects)
        self._create_workflow_transitions(projects)
        self._create_portfolios(user, projects)
        self._create_external_calendars(user)
        self._create_wiki_pages(user, projects)
        self._create_github_data(user, tasks)

        self.stdout.write(self.style.SUCCESS("\n=== Datos demo creados ==="))
        self.stdout.write(f"  Usuario: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        self.stdout.write(f"  Proyectos: {len(projects)}")
        self.stdout.write(f"  Épicas: {len(epics)}")
        self.stdout.write(f"  Sprints: {len(sprints)}")
        self.stdout.write(f"  Tareas: {len(tasks)}")
        self.stdout.write(f"  Etiquetas: {len(tags)}")

    def _clean(self):
        self.stdout.write("Limpiando datos demo...")
        # Delete in dependency order (children first)
        EncryptedKeyShare.objects.all().delete()
        EncryptedTask.objects.all().delete()
        UserPublicKey.objects.all().delete()
        SyncOperation.objects.all().delete()
        SyncDevice.objects.all().delete()
        ChatMessageLog.objects.all().delete()
        ChatIntegration.objects.all().delete()
        WebhookDelivery.objects.all().delete()
        GitHubCheckRun.objects.all().delete()
        GitHubRelease.objects.all().delete()
        GitHubCommit.objects.all().delete()
        GitHubPullRequest.objects.all().delete()
        GitHubIssueLink.objects.all().delete()
        GitHubRepo.objects.all().delete()
        GitHubInstallation.objects.all().delete()
        AiSuggestion.objects.all().delete()
        APIKey.objects.all().delete()
        KeyResultUpdate.objects.all().delete()
        AutomationLog.objects.all().delete()
        AuditLog.objects.all().delete()
        Mention.objects.all().delete()
        Invitation.objects.all().delete()
        ProjectMember.objects.all().delete()
        Notification.objects.all().delete()
        FeatureFlag.objects.all().delete()
        OutgoingWebhook.objects.all().delete()
        SavedSearch.objects.all().delete()
        RecurrenceRule.objects.all().delete()
        CustomFieldValue.objects.all().delete()
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
        Dashboard.objects.all().delete()
        ProjectRisk.objects.all().delete()
        OrganizationMembership.objects.all().delete()
        Organization.objects.all().delete()
        Whiteboard.objects.all().delete()
        IntakeForm.objects.all().delete()
        ShareLink.objects.all().delete()
        Meeting.objects.all().delete()
        SlaPolicy.objects.all().delete()
        from apps.projects.models import WorkflowTransition
        WorkflowTransition.objects.all().delete()
        Portfolio.objects.all().delete()
        from apps.collaboration.models import ExternalCalendar
        ExternalCalendar.objects.all().delete()
        from apps.wiki.models import WikiPage
        WikiPage.objects.all().delete()
        Project.objects.all().delete()
        User.objects.filter(email__in=[DEMO_EMAIL, "ana@todolist.com", "carlos@todolist.com",
                                       "elena@todolist.com", "javier@todolist.com"]).delete()
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
            ("Sprint 15 - Offline Sync", "Implementar sync offline básico", projects[0], "active", today - timedelta(days=14), today + timedelta(days=1)),
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
            # Archivadas: pueblan /app/archive para que la vista no salga vacía
            ("Prototipo de onboarding v1", "Primer intento de flujo de onboarding descartado", projects[2], None, None, "archived", 3, "task", 2, 3, [], now - timedelta(days=30)),
            ("Spike: web sockets vs polling", "Investigación de tiempo real descartada", projects[1], None, None, "archived", 4, "task", 1, 4, [], now - timedelta(days=45)),
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
            if t.completed_at:
                # auto_now_add fuerza created_at=now: hay que retrodatarlo
                # con update() para que lead time (created→completed) > 0
                backdate = t.completed_at - timedelta(
                    days=random.randint(1, 10),
                    hours=random.randint(0, 23),
                )
                Task.objects.filter(pk=t.pk).update(created_at=backdate)
                t.created_at = backdate
            if task_tags:
                t.tags.set(task_tags)
            tasks.append(t)
        # Algunas favoritas para que la vista /app/favorites no quede vacía
        for idx in (0, 2, 7):
            if idx < len(tasks):
                tasks[idx].favorited_by.add(user)
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
        comments = []
        for task_idx, body in comments_data:
            if task_idx < len(tasks):
                c = Comment.objects.create(task=tasks[task_idx], author=user, body=body)
                comments.append(c)
        self.stdout.write(f"  Comentarios: {len(comments)}")
        return comments

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

    def _create_teams(self, user, extra_users=None):
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
            # Add extra users to teams
            if extra_users:
                roles = ["member", "member", "admin"]
                for i, eu in enumerate(extra_users[:3]):
                    TeamMembership.objects.get_or_create(
                        team=t, user=eu,
                        defaults={"role": roles[i % len(roles)]},
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
        fields = []
        for project, name, ftype, options in cf_data:
            cf, _ = CustomField.objects.get_or_create(
                project=project, name=name,
                defaults={"field_type": ftype, "options": options, "is_required": False},
            )
            fields.append(cf)
        self.stdout.write(f"  Campos personalizados: {len(fields)}")
        return fields

    def _create_automations(self, user):
        rules = [
            ("Auto P0 en bloqueo", "Cuando una tarea pasa a blocked, asignar prioridad P0", "task_blocked", "set_priority", {"priority": 0}),
            ("Notificar tareas vencidas", "Cuando una tarea vence, crear notificación", "task_overdue", "create_notification", {"message": "Tarea vencida"}),
            ("Subtareas a En progreso", "Cuando una tarea se completa, mover subtareas a En progreso", "task_completed", "subtasks_in_progress", {}),
        ]
        created = []
        for name, desc, trigger, action, params in rules:
            rule, _ = AutomationRule.objects.get_or_create(
                name=name, owner=user,
                defaults={"description": desc, "trigger": trigger, "action": action, "action_params": params, "enabled": True},
            )
            created.append(rule)
        self.stdout.write(f"  Automatizaciones: {len(created)}")
        return created

    def _create_okrs(self, user):
        today = timezone.now().date()
        year = today.year
        quarter = f"Q{(today.month - 1) // 3 + 1}"

        objectives_data = [
            ("Mejorar calidad del código", "Reducir bugs en producción y mejorar cobertura de tests", [
                ("Reducir bugs en producción a < 5/mes", 10, 3, "bugs", "decrease"),
                ("Aumentar cobertura de tests a 80%", 80, 45, "%", "increase"),
                ("Reducir tiempo de CI a < 10 min", 30, 18, "min", "decrease"),
            ]),
            ("Acelerar delivery", "Reducir time-to-market de nuevas features", [
                ("Deploy 2 features/semana", 8, 5, "features", "increase"),
                ("Reducir lead time a < 3 días", 7, 5, "días", "decrease"),
                ("Sprint completion rate > 90%", 90, 75, "%", "increase"),
            ]),
            ("Mejorar experiencia móvil", "App más rápida y estable", [
                ("Reducir crash rate a < 0.5%", 1, 2, "%", "decrease"),
                ("App startup < 2 segundos", 2, 3, "s", "decrease"),
                ("Rating App Store > 4.5", 5, 4, "puntos", "increase"),
            ]),
        ]

        count = 0
        for title, desc, krs in objectives_data:
            obj, _ = Objective.objects.get_or_create(
                title=title, owner=user, quarter=quarter, year=year,
                defaults={"description": desc, "status": "in_progress", "progress": 50},
            )
            for kr_title, target, current, unit, direction in krs:
                KeyResult.objects.get_or_create(
                    objective=obj, title=kr_title, owner=user,
                    defaults={
                        "target_value": target, "current_value": current,
                        "unit": unit, "direction": direction,
                    },
                )
                count += 1
        self.stdout.write(f"  OKRs: {len(objectives_data)} objetivos, {count} key results")

    # ──────────────────────────────────────────────────────────────
    #  NEW: Extra users for collaboration, mentions, project members
    # ──────────────────────────────────────────────────────────────

    def _create_extra_users(self):
        users_data = [
            ("ana@todolist.com", "Ana García", "Frontend Developer"),
            ("carlos@todolist.com", "Carlos López", "Backend Developer"),
            ("elena@todolist.com", "Elena Ruiz", "DevOps Engineer"),
            ("javier@todolist.com", "Javier Moreno", "QA Engineer"),
        ]
        users = []
        for email, name, role in users_data:
            u, created = User.objects.get_or_create(
                email=email,
                defaults={"username": name.lower().replace(" ", "_"), "is_active": True},
            )
            if created:
                u.set_password("demo12345")
                u.save()
            users.append(u)
        self.stdout.write(f"  Usuarios extra: {len(users)}")
        return users

    # ──────────────────────────────────────────────────────────────
    #  Feature Flags — realistic kill switches, canary, dark launches
    # ──────────────────────────────────────────────────────────────

    def _create_feature_flags(self, user):
        flags = [
            ("checkout_v2", "Checkout v2 Rediseñado",
             "Nuevo checkout en un solo paso. Rollout gradual 25%.",
             True, 25),
            ("recommendation_engine", "Motor de Recomendaciones AI",
             "Dark launch del motor de recomendaciones. Corre en background sin mostrar al usuario.",
             True, 0),
            ("kill_switch_payments", "Kill Switch - Pagos",
             "Desactivar pasarela de pago nueva y volver a la legacy si hay incidentes.",
             False, 0),
            ("beta_offline_sync", "Sync Offline Beta",
             "Acceso temprano a sincronización offline para usuarios beta.",
             True, 10),
            ("new_onboarding_flow", "Nuevo Onboarding",
             "Onboarding guiado con tooltips animados. Canary al 5%.",
             False, 5),
            ("graphql_api", "API GraphQL",
             "Endpoint GraphQL experimental junto a REST. Solo interno.",
             True, 0),
        ]
        count = 0
        for key, name, desc, enabled, pct in flags:
            FeatureFlag.objects.get_or_create(
                key=key,
                defaults={"name": name, "description": desc, "is_enabled": enabled, "enabled_percentage": pct},
            )
            count += 1
        self.stdout.write(f"  Feature Flags: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Outgoing Webhooks — Slack, Discord, custom endpoint
    # ──────────────────────────────────────────────────────────────

    def _create_outgoing_webhooks(self, user):
        webhooks = [
            ("https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
             ["task.created", "task.completed", "sprint.started"]),
            ("https://discord.com/api/webhooks/000000000000000000/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
             ["task.blocked", "task.overdue"]),
            ("https://api.zapier.com/hooks/catch/0000000/0000000/",
             ["task.created", "comment.created", "timeentry.created"]),
        ]
        count = 0
        for url, events in webhooks:
            OutgoingWebhook.objects.get_or_create(
                url=url, owner=user,
                defaults={"events": events, "is_active": True, "secret": "whsec_" + uuid.uuid4().hex[:16]},
            )
            count += 1
        self.stdout.write(f"  Webhooks salientes: {count}")

    def _create_webhook_deliveries(self):
        now = timezone.now()
        deliveries = [
            ("wh_del_001", "task.created", "created", "processed", "", "todosolutions/todolist-api", now - timedelta(hours=2)),
            ("wh_del_002", "task.completed", "completed", "processed", "", "todosolutions/todolist-api", now - timedelta(hours=5)),
            ("wh_del_003", "task.blocked", "blocked", "processed", "", "todosolutions/todolist-api", now - timedelta(hours=8)),
            ("wh_del_004", "task.created", "created", "failed", "Connection timeout", "todosolutions/todolist-web", now - timedelta(hours=12)),
            ("wh_del_005", "sprint.started", "started", "processed", "", "todosolutions/todolist-api", now - timedelta(days=1)),
            ("wh_del_006", "task.overdue", "overdue", "retrying", "HTTP 503", "todosolutions/todolist-mobile", now - timedelta(days=2)),
            ("wh_del_007", "comment.created", "created", "processed", "", "todosolutions/todolist-api", now - timedelta(days=3)),
        ]
        count = 0
        for did, event, action, status, error, repo, created in deliveries:
            WebhookDelivery.objects.get_or_create(
                delivery_id=did,
                defaults={
                    "event_type": event, "action": action, "status": status,
                    "error_message": error, "repo_full_name": repo,
                    "payload": {"event": event, "timestamp": created.isoformat()},
                    "processed_at": created + timedelta(seconds=2) if status == "processed" else None,
                },
            )
            count += 1
        self.stdout.write(f"  Webhook deliveries: {count}")

    # ──────────────────────────────────────────────────────────────
    #  GitHub integration — installations, repos, PRs, commits, releases
    # ──────────────────────────────────────────────────────────────

    def _create_github_data(self, user, tasks):
        now = timezone.now()

        # Installation
        inst, _ = GitHubInstallation.objects.get_or_create(
            installation_id=12345678,
            defaults={
                "user": user, "account_login": "todosolutions",
                "account_type": "Organization",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345678?v=4",
                "github_username": "todosolutions",
            },
        )

        # Repos
        repos_data = [
            (1001, "todosolutions/todolist-api", "todolist-api", "todosolutions", False, "main"),
            (1002, "todosolutions/todolist-mobile", "todolist-mobile", "todosolutions", False, "main"),
            (1003, "todosolutions/todolist-web", "todolist-web", "todosolutions", False, "develop"),
        ]
        repos = []
        for rid, full, name, owner, is_priv, branch in repos_data:
            r, _ = GitHubRepo.objects.get_or_create(
                installation=inst, repo_id=rid,
                defaults={"full_name": full, "name": name, "owner": owner, "is_private": is_priv, "default_branch": branch},
            )
            repos.append(r)

        # Issue links — link some tasks to GitHub issues
        issue_links = [
            (tasks[0], repos[0], 42, 100001, "https://github.com/todosolutions/todolist-api/issues/42", "closed"),
            (tasks[7], repos[1], 15, 100002, "https://github.com/todosolutions/todolist-mobile/issues/15", "open"),
            (tasks[10], repos[0], 78, 100003, "https://github.com/todosolutions/todolist-api/issues/78", "open"),
            (tasks[17], repos[0], 91, 100004, "https://github.com/todosolutions/todolist-api/issues/91", "open"),
            (tasks[20], repos[2], 23, 100005, "https://github.com/todosolutions/todolist-web/issues/23", "closed"),
        ]
        for task, repo, num, iid, url, state in issue_links:
            GitHubIssueLink.objects.get_or_create(
                task=task,
                defaults={"repo": repo, "issue_number": num, "issue_id": iid, "issue_url": url, "issue_state": state,
                          "last_synced_at": now - timedelta(hours=2)},
            )

        # Pull Requests
        prs_data = [
            (repos[0], 101, 200001, "feat: implement OAuth2 Google login", "closed", True, "https://github.com/todosolutions/todolist-api/pull/101",
             "feat/auth-google", "main", "ana-garcia", now - timedelta(days=20), now - timedelta(days=19), "success", 3, 2),
            (repos[0], 102, 200002, "fix: memory leak in user service pool", "open", False, "https://github.com/todosolutions/todolist-api/pull/102",
             "fix/user-pool", "main", "carlos-lopez", now - timedelta(days=2), None, "pending", 1, 0),
            (repos[1], 45, 200003, "feat: offline cache with AsyncStorage", "open", False, "https://github.com/todosolutions/todolist-mobile/pull/45",
             "feat/offline-cache", "main", "ana-garcia", now - timedelta(days=5), None, "pending", 0, 0),
            (repos[2], 12, 200004, "feat: new landing page with Lottie animations", "closed", True, "https://github.com/todosolutions/todolist-web/pull/12",
             "feat/new-landing", "main", "elena-ruiz", now - timedelta(days=35), now - timedelta(days=33), "success", 5, 3),
            (repos[0], 103, 200005, "chore: upgrade PostgreSQL 16", "draft", False, "https://github.com/todosolutions/todolist-api/pull/103",
             "chore/pg16", "main", "carlos-lopez", now - timedelta(days=1), None, "", 0, 0),
        ]
        prs = []
        for repo, num, pid, title, state, merged, url, head, base, author, created, merged_at, ci, comments, approvals in prs_data:
            pr, _ = GitHubPullRequest.objects.get_or_create(
                repo=repo, pr_number=num,
                defaults={"pr_id": pid, "title": title, "state": state, "is_merged": merged,
                          "html_url": url, "head_branch": head, "base_branch": base, "author": author,
                          "created_at_gh": created, "merged_at": merged_at,
                          "review_comments_count": comments, "approvals_count": approvals,
                          "ci_status": ci},
            )
            prs.append(pr)

        # Link PRs to tasks
        if len(tasks) > 0 and len(prs) > 0:
            prs[0].tasks.add(tasks[0])
            prs[1].tasks.add(tasks[17])
            prs[2].tasks.add(tasks[4])
            prs[3].tasks.add(tasks[20])

        # Commits
        commits_data = [
            (repos[0], "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2", "feat(auth): Google Sign-In integration with PKCE", "ana-garcia", now - timedelta(days=20)),
            (repos[0], "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3", "feat(auth): Apple Sign-In with nonce validation", "ana-garcia", now - timedelta(days=18)),
            (repos[0], "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4", "fix(auth): handle 401 in logout interceptor (#7)", "carlos-lopez", now - timedelta(days=2)),
            (repos[0], "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5", "feat(gateway): Kong setup with JWT plugin", "carlos-lopez", now - timedelta(days=6)),
            (repos[0], "e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6", "feat(gateway): rate limiting with Redis sliding window", "carlos-lopez", now - timedelta(days=2)),
            (repos[1], "f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1", "feat(mobile): AsyncStorage wrapper for offline cache", "ana-garcia", now - timedelta(days=5)),
            (repos[1], "1a2b3c4d5e6f1a2b3c4d5e6f1a2b3c4d5e6f1a2b", "fix(mobile): crash on logout with expired token", "ana-garcia", now - timedelta(days=3)),
            (repos[2], "2b3c4d5e6f1a2b3c4d5e6f1a2b3c4d5e6f1a2b3c", "feat(web): new hero section with Lottie animations", "elena-ruiz", now - timedelta(days=33)),
            (repos[2], "3c4d5e6f1a2b3c4d5e6f1a2b3c4d5e6f1a2b3c4d", "feat(web): single-page checkout with Stripe", "elena-ruiz", now - timedelta(days=30)),
            (repos[0], "4d5e6f1a2b3c4d5e6f1a2b3c4d5e6f1a2b3c4d5e", "chore(deps): upgrade Django to 5.0.6", "javier-moreno", now - timedelta(days=1)),
        ]
        for repo, sha, msg, author, date in commits_data:
            GitHubCommit.objects.get_or_create(
                sha=sha,
                defaults={"repo": repo, "message": msg, "author": author, "author_date": date,
                          "html_url": f"https://github.com/{repo.full_name}/commit/{sha}"},
            )

        # Releases
        releases_data = [
            (repos[0], 500001, "v2.1.0", "v2.1.0 - Auth & Gateway",
             "## Cambios\n- OAuth2 Google login\n- Apple Sign-In\n- Kong API Gateway\n- Rate limiting con Redis\n- JWT middleware",
             "https://github.com/todosolutions/todolist-api/releases/tag/v2.1.0", "published", False, "carlos-lopez", now - timedelta(days=18)),
            (repos[2], 500002, "v3.0.0", "v3.0.0 - Rediseño E-commerce",
             "## Cambios\n- Nueva landing page\n- Checkout en un solo paso\n- Stripe Payment Intent\n- Lazy loading imágenes\n- Búsqueda Elasticsearch",
             "https://github.com/todosolutions/todolist-web/releases/tag/v3.0.0", "published", False, "elena-ruiz", now - timedelta(days=28)),
            (repos[0], 500003, "v2.2.0-beta.1", "v2.2.0-beta.1 - Service Mesh Preview",
             "Beta release con Istio service mesh. No usar en producción.",
             "https://github.com/todosolutions/todolist-api/releases/tag/v2.2.0-beta.1", "published", True, "carlos-lopez", now - timedelta(days=1)),
        ]
        for repo, rid, tag, name, body, url, state, pre, author, pub in releases_data:
            GitHubRelease.objects.get_or_create(
                release_id=rid,
                defaults={"repo": repo, "tag_name": tag, "name": name, "body": body, "html_url": url,
                          "state": state, "is_prerelease": pre, "author": author, "published_at": pub},
            )

        # Check Runs (CI)
        checks_data = [
            (repos[0], 900001, "CI / test", "completed", "success", prs[0] if prs else None, now - timedelta(days=20), now - timedelta(days=20, minutes=-8)),
            (repos[0], 900002, "CI / lint", "completed", "success", prs[0] if prs else None, now - timedelta(days=20), now - timedelta(days=20, minutes=-2)),
            (repos[0], 900003, "CI / test", "completed", "failure", prs[1] if len(prs) > 1 else None, now - timedelta(days=2), now - timedelta(days=2, minutes=-5)),
            (repos[0], 900004, "CI / security-scan", "in_progress", "", prs[1] if len(prs) > 1 else None, now - timedelta(hours=1), None),
            (repos[2], 900005, "CI / build-and-deploy", "completed", "success", prs[3] if len(prs) > 3 else None, now - timedelta(days=33), now - timedelta(days=33, minutes=-12)),
        ]
        for repo, cid, name, status, conclusion, pr, started, completed in checks_data:
            GitHubCheckRun.objects.get_or_create(
                check_id=cid,
                defaults={"repo": repo, "name": name, "status": status, "conclusion": conclusion,
                          "pull_request": pr, "started_at": started, "completed_at": completed},
            )

        self.stdout.write(f"  GitHub: 1 installation, {len(repos)} repos, {len(issue_links)} issue links, {len(prs_data)} PRs, {len(commits_data)} commits, {len(releases_data)} releases, {len(checks_data)} check runs")
        return repos

    # ──────────────────────────────────────────────────────────────
    #  Notifications
    # ──────────────────────────────────────────────────────────────

    def _create_notifications(self, user, tasks, sprints):
        now = timezone.now()
        notifs = [
            ("task_assigned", "Nueva tarea asignada", f"Se te ha asignado: {tasks[2].title}", tasks[2], None, "/app"),
            ("mention", "Mención en comentario", "Ana te mencionó en una tarea", tasks[0], None, "/app"),
            ("sprint_started", f"Sprint iniciado: {sprints[2].name}", sprints[2].goal, None, sprints[2], "/app/sprints"),
            ("task_overdue", "Tarea vencida", f"La tarea '{tasks[7].title}' ha pasado su fecha límite", tasks[7], None, "/app"),
            ("task_completed", "Tarea completada", f"'{tasks[0].title}' marcada como completada", tasks[0], None, "/app"),
            ("task_commented", "Nuevo comentario", "Carlos comentó en 'Memory leak en user service'", tasks[17], None, "/app"),
            ("task_blocked", "Tarea bloqueada", f"'{tasks[7].title}' ha sido bloqueada", tasks[7], None, "/app"),
            ("custom", "Bienvenido a TODOlist", "Tu cuenta está lista. ¡Empieza a crear tareas!", None, None, "/app"),
            ("task_assigned", "Nueva tarea asignada", f"Se te ha asignado: {tasks[10].title}", tasks[10], None, "/app"),
            ("sprint_closed", f"Sprint completado: {sprints[1].name}", "El sprint ha finalizado. Revisa el burndown.", None, sprints[1], "/app/burndown"),
        ]
        count = 0
        for i, (ntype, title, body, task, sprint, url) in enumerate(notifs):
            if task and task.id:
                Notification.objects.get_or_create(
                    recipient=user, title=title, type=ntype,
                    defaults={
                        "body": body, "task": task, "sprint": sprint, "action_url": url,
                        "read": i > 5,  # first 6 unread, rest read
                        "read_at": now - timedelta(hours=i) if i > 5 else None,
                    },
                )
            else:
                Notification.objects.get_or_create(
                    recipient=user, title=title, type=ntype,
                    defaults={
                        "body": body, "sprint": sprint, "action_url": url,
                        "read": i > 5,
                        "read_at": now - timedelta(hours=i) if i > 5 else None,
                    },
                )
            count += 1
        self.stdout.write(f"  Notificaciones: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Project Members
    # ──────────────────────────────────────────────────────────────

    def _create_project_members(self, user, projects, extra_users):
        if not extra_users:
            return
        members = [
            (projects[0], extra_users[0], "admin"),     # Ana - Frontend → App Móvil
            (projects[0], extra_users[3], "member"),     # Javier - QA → App Móvil
            (projects[1], extra_users[1], "admin"),      # Carlos - Backend → Microservicios
            (projects[1], extra_users[2], "member"),     # Elena - DevOps → Microservicios
            (projects[2], extra_users[0], "member"),     # Ana - Frontend → E-commerce
            (projects[2], extra_users[3], "viewer"),     # Javier - QA → E-commerce
        ]
        count = 0
        for project, member_user, role in members:
            ProjectMember.objects.get_or_create(
                project=project, user=member_user,
                defaults={"role": role, "invited_by": user},
            )
            count += 1
        self.stdout.write(f"  Miembros de proyecto: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Invitations
    # ──────────────────────────────────────────────────────────────

    def _create_invitations(self, user, projects):
        invites = [
            ("project", projects[0].id, "newdev1@example.com", "member"),
            ("project", projects[1].id, "newdev2@example.com", "admin"),
            ("team", 1, "newpm@example.com", "member"),
        ]
        count = 0
        for target_type, target_id, email, role in invites:
            Invitation.objects.get_or_create(
                email=email, target_type=target_type, target_id=target_id,
                defaults={
                    "role": role, "invited_by": user,
                    "token": uuid.uuid4().hex,
                    "status": "pending",
                },
            )
            count += 1
        self.stdout.write(f"  Invitaciones: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Mentions
    # ──────────────────────────────────────────────────────────────

    def _create_mentions(self, user, tasks, comments, extra_users):
        if not extra_users or not comments:
            return
        mentions = [
            (comments[0], tasks[7], extra_users[0], user),    # Ana mentioned in crash bug
            (comments[2], tasks[17], extra_users[1], user),   # Carlos mentioned in memory leak
            (comments[5], tasks[24], extra_users[3], user),   # Javier mentioned in cart bug
        ]
        count = 0
        for comment, task, mentioned, mentioned_by in mentions:
            Mention.objects.get_or_create(
                comment=comment, task=task, mentioned_user=mentioned,
                defaults={"mentioned_by": mentioned_by},
            )
            count += 1
        self.stdout.write(f"  Menciones: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Audit Logs
    # ──────────────────────────────────────────────────────────────

    def _create_audit_logs(self, user, tasks, projects):
        now = timezone.now()
        logs = [
            ("create", "project", projects[0].id, projects[0].name, {}, {"name": projects[0].name}, now - timedelta(days=60)),
            ("update", "task", tasks[0].id, tasks[0].title, {"state": "in_progress"}, {"state": "completed"}, now - timedelta(days=20)),
            ("create", "task", tasks[10].id, tasks[10].title, {}, {"title": tasks[10].title}, now - timedelta(days=6)),
            ("delete", "task", 9999, "Tarea obsoleta", {"id": 9999}, {}, now - timedelta(days=10)),
            ("update", "project", projects[1].id, projects[1].name, {"description": "Migrar monolito"}, {"description": projects[1].description}, now - timedelta(days=30)),
            ("create", "sprint", 1, "Sprint 14", {}, {"name": "Sprint 14"}, now - timedelta(days=28)),
            ("update", "task", tasks[17].id, tasks[17].title, {"state": "in_progress"}, {"state": "blocked"}, now - timedelta(days=1)),
            ("create", "task", tasks[20].id, tasks[20].title, {}, {"title": tasks[20].title}, now - timedelta(days=35)),
            ("update", "task", tasks[7].id, tasks[7].title, {"state": "in_progress"}, {"state": "blocked"}, now - timedelta(days=2)),
            ("create", "epic", 1, "Autenticación OAuth 2.0", {}, {"title": "Autenticación OAuth 2.0"}, now - timedelta(days=60)),
        ]
        count = 0
        for action, rtype, rid, rname, old, new, created in logs:
            AuditLog.objects.get_or_create(
                action=action, resource_type=rtype, resource_id=rid, created_at=created,
                defaults={
                    "actor": user, "resource_name": rname,
                    "old_values": old, "new_values": new,
                },
            )
            count += 1
        self.stdout.write(f"  Audit logs: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Automation Logs
    # ──────────────────────────────────────────────────────────────

    def _create_automation_logs(self, automations):
        if not automations:
            return
        logs = [
            (automations[0], "success", {"task_id": 8, "state": "blocked"}, {"priority": 0}, ""),
            (automations[1], "success", {"task_id": 7, "due_date": "overdue"}, {"notification": "sent"}, ""),
            (automations[2], "success", {"task_id": 0, "state": "completed"}, {"subtasks": "moved_to_in_progress"}, ""),
            (automations[0], "success", {"task_id": 17, "state": "blocked"}, {"priority": 0}, ""),
            (automations[1], "failed", {"task_id": 99}, {}, "Tarea no encontrada"),
        ]
        count = 0
        for rule, status, trigger, result, error in logs:
            AutomationLog.objects.create(
                rule=rule, status=status, trigger_data=trigger, action_result=result, error_message=error,
            )
            count += 1
        self.stdout.write(f"  Automation logs: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Key Result Updates — progress over time
    # ──────────────────────────────────────────────────────────────

    def _create_key_result_updates(self, user):
        now = timezone.now()
        krs = list(KeyResult.objects.all()[:6])
        updates = [
            (krs[0], 10, 7, "3 bugs críticos arreglados este sprint", now - timedelta(days=14)),
            (krs[0], 7, 3, "Solo quedan 3 bugs tras los hotfixes", now - timedelta(days=2)),
            (krs[1], 45, 60, "Tests añadidos para el módulo de auth", now - timedelta(days=10)),
            (krs[1], 60, 65, "Más tests para el gateway", now - timedelta(days=3)),
            (krs[2], 18, 15, "Suites de tests paralelizadas", now - timedelta(days=7)),
            (krs[3], 5, 6, "2 features entregadas esta semana", now - timedelta(days=5)),
        ]
        count = 0
        for kr, old, new, note, created in updates:
            if kr:
                KeyResultUpdate.objects.create(
                    key_result=kr, user=user, old_value=old, new_value=new, note=note,
                )
                # Update KR current value
                kr.current_value = new
                kr.save()
                count += 1
        self.stdout.write(f"  Key Result updates: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Chat Integrations — Slack + Discord
    # ──────────────────────────────────────────────────────────────

    def _create_chat_integrations(self, user):
        integrations = [
            ("slack", "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
             "#engineering", ["task.created", "task.blocked", "sprint.started"]),
            ("discord", "https://discord.com/api/webhooks/000000000000000000/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
             "dev-alerts", ["task.overdue", "task.blocked"]),
        ]
        count = 0
        for provider, url, channel, events in integrations:
            ci, _ = ChatIntegration.objects.get_or_create(
                owner=user, provider=provider,
                defaults={"webhook_url": url, "channel": channel, "events": events, "is_active": True},
            )
            # Add some message logs
            for i in range(3):
                ChatMessageLog.objects.create(
                    integration=ci,
                    event=events[i % len(events)],
                    payload={"text": f"Test message {i+1} from {provider}"},
                    status_code=200 if i < 2 else 500,
                    success=i < 2,
                    error="" if i < 2 else "Internal Server Error",
                )
            count += 1
        self.stdout.write(f"  Chat integrations: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Sync Devices & Operations
    # ──────────────────────────────────────────────────────────────

    def _create_sync_devices(self, user):
        now = timezone.now()
        devices = [
            ("device-iphone-12-abc123", "iPhone 12 - Ana", now - timedelta(hours=2)),
            ("device-macbook-pro-xyz789", "MacBook Pro - Ana", now - timedelta(hours=5)),
            ("device-android-pixel7-def456", "Pixel 7 - Demo", now - timedelta(days=1)),
        ]
        devs = []
        for did, name, last_sync in devices:
            d, _ = SyncDevice.objects.get_or_create(
                user=user, device_id=did,
                defaults={"device_name": name, "last_sync_at": last_sync},
            )
            devs.append(d)

        # Sync operations
        ops = [
            (devs[0], "create", "task", "client-uuid-001", 1, now - timedelta(hours=2)),
            (devs[0], "update", "task", "client-uuid-002", 2, now - timedelta(hours=2, minutes=-5)),
            (devs[1], "create", "subtask", "client-uuid-003", 1, now - timedelta(hours=5)),
            (devs[1], "delete", "task", "client-uuid-004", None, now - timedelta(hours=5, minutes=-2)),
            (devs[2], "update", "task", "client-uuid-005", 5, now - timedelta(days=1)),
        ]
        count = 0
        for dev, op_type, entity, eid, server_id, ts in ops:
            SyncOperation.objects.create(
                device=dev, user=user, op_type=op_type, entity_type=entity,
                entity_id=eid, server_entity_id=server_id,
                payload={"title": f"Sync {op_type} {entity}"},
                client_timestamp=ts, server_timestamp=ts + timedelta(seconds=1),
                status="applied", applied_at=ts + timedelta(seconds=1),
            )
            count += 1
        self.stdout.write(f"  Sync devices: {len(devs)}, operations: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Encryption — public keys, encrypted tasks, key shares
    # ──────────────────────────────────────────────────────────────

    def _create_encryption_data(self, user, tasks):
        # Generate a dummy RSA public key (for demo only, NOT real crypto)
        dummy_pubkey = (
            "-----BEGIN PUBLIC KEY-----\n"
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xfn/2gNE\n"
            "dummy_key_for_demo_purposes_only_not_real_crypto_key_data_here\n"
            "-----END PUBLIC KEY-----"
        )
        pubkey, _ = UserPublicKey.objects.get_or_create(
            user=user, key_id="key-2024-001",
            defaults={"public_key": dummy_pubkey, "algorithm": "RSA-OAEP-256", "is_active": True},
        )

        # Encrypted tasks
        enc_tasks = []
        for i in range(2):
            et = EncryptedTask.objects.create(
                owner=user,
                encrypted_data=f"encrypted_blob_{i}_{uuid.uuid4().hex}",
                encryption_key_id="key-2024-001",
                iv=uuid.uuid4().hex[:32],
                auth_tag=uuid.uuid4().hex[:32],
                algorithm="AES-256-GCM",
            )
            enc_tasks.append(et)

        # Key shares
        for et in enc_tasks:
            EncryptedKeyShare.objects.create(
                encrypted_task=et, user=user,
                encrypted_key=f"shared_key_{uuid.uuid4().hex}",
                user_public_key=pubkey,
            )
        self.stdout.write(f"  Encryption: 1 pubkey, {len(enc_tasks)} encrypted tasks, {len(enc_tasks)} key shares")

    # ──────────────────────────────────────────────────────────────
    #  Recurrence Rules
    # ──────────────────────────────────────────────────────────────

    def _create_recurrence_rules(self, user):
        rules = [
            ("daily", 1, None, None),       # Daily standup
            ("weekly", 1, None, 52),         # Weekly sprint planning
            ("monthly", 1, None, 12),        # Monthly retrospective
        ]
        count = 0
        for freq, interval, until, cnt in rules:
            RecurrenceRule.objects.create(
                frequency=freq, interval=interval, until=until, count=cnt,
                owner=user,
            )
            count += 1
        self.stdout.write(f"  Reglas de recurrencia: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Saved Searches
    # ──────────────────────────────────────────────────────────────

    def _create_saved_searches(self, user):
        searches = [
            ("Mis bugs abiertos", {"state": "blocked", "task_type": "bug"}, False),
            ("Tareas urgentes", {"priority": "0"}, True),
            ("Sprint actual", {"sprint": "active"}, True),
            ("Documentación pendiente", {"task_type": "docs", "state": "pending"}, False),
            ("Sin proyecto", {"project": "null"}, False),
        ]
        count = 0
        for name, filters, shared in searches:
            SavedSearch.objects.get_or_create(
                name=name, owner=user,
                defaults={"filters": filters, "is_shared": shared},
            )
            count += 1
        self.stdout.write(f"  Búsquedas guardadas: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Task Activities
    # ──────────────────────────────────────────────────────────────

    def _create_task_activities(self, user, tasks):
        now = timezone.now()
        activities = [
            (tasks[0], "created", "", "", now - timedelta(days=20)),
            (tasks[0], "state_changed", "in_progress", "completed", now - timedelta(days=19)),
            (tasks[0], "comment_added", "", "Login con Google funcionando", now - timedelta(days=18)),
            (tasks[7], "created", "", "", now - timedelta(days=5)),
            (tasks[7], "state_changed", "in_progress", "blocked", now - timedelta(days=2)),
            (tasks[7], "priority_changed", "2", "0", now - timedelta(days=2)),
            (tasks[10], "created", "", "", now - timedelta(days=6)),
            (tasks[10], "state_changed", "pending", "in_progress", now - timedelta(days=4)),
            (tasks[17], "created", "", "", now - timedelta(days=10)),
            (tasks[17], "state_changed", "in_progress", "blocked", now - timedelta(days=1)),
            (tasks[20], "created", "", "", now - timedelta(days=35)),
            (tasks[20], "state_changed", "in_progress", "completed", now - timedelta(days=30)),
        ]
        count = 0
        for task, action, old, new, created in activities:
            TaskActivity.objects.create(
                task=task, actor=user, action=action,
                field=action.replace("_changed", "").replace("_added", "") if "_" in action else "",
                old_value=old, new_value=new,
            )
            count += 1
        self.stdout.write(f"  Actividades de tarea: {count}")

    # ──────────────────────────────────────────────────────────────
    #  API Keys
    # ──────────────────────────────────────────────────────────────

    def _create_api_keys(self, user):
        now = timezone.now()
        keys = [
            ("Producción - CI/CD", ["read", "write"], True, now + timedelta(days=365)),
            ("Desarrollo - Local", ["read"], True, now + timedelta(days=90)),
            ("Webhook listener", ["read"], False, now - timedelta(days=1)),
        ]
        count = 0
        for name, scopes, active, expires in keys:
            raw_key = f"tl_{uuid.uuid4().hex}"
            APIKey.objects.create(
                user=user, name=name,
                key_prefix=raw_key[:12],
                hashed_key=make_password(raw_key),
                scopes=scopes, is_active=active, expires_at=expires,
            )
            count += 1
        self.stdout.write(f"  API Keys: {count}")

    # ──────────────────────────────────────────────────────────────
    #  AI Suggestions (rule-based assistant)
    # ──────────────────────────────────────────────────────────────

    def _create_ai_suggestions(self, user, tasks):
        # Los tipos deben ser los de AiSuggestion.SuggestionType — antes se
        # usaban nombres inventados que el frontend no puede traducir.
        suggestions = [
            (tasks[7], "priority_estimate", {"state": "blocked", "age_days": 5},
             {"suggested_priority": 0, "reason": "Tarea bloqueada por más de 3 días"}, 0.92),
            (tasks[17], "priority_estimate", {"state": "blocked", "age_days": 1},
             {"suggested_priority": 0, "reason": "Bug en producción bloqueado"}, 0.88),
            (tasks[2], "blocker_detection", {"state": "in_progress", "sprint_progress": 60},
             {"suggested_action": "move_to_next_sprint", "reason": "Sprint casi finalizado y tarea sin completar"}, 0.75),
            (tasks[10], "description_improvement", {"tags": ["devops", "api"]},
             {"improved_description": "Tarea de DevOps — documentar pasos de despliegue", "suggestions": ["Añadir checklist de despliegue"]}, 0.81),
            (tasks[4], "story_point_estimate", {"story_points": 8, "subtasks": 0},
             {"suggested_points": 5, "reason": "Tarea grande sin subtareas. Considerar dividir."}, 0.70),
        ]
        count = 0
        for task, stype, inp, out, conf in suggestions:
            AiSuggestion.objects.create(
                user=user, task=task, suggestion_type=stype,
                input_data=inp, output_data=out, confidence=conf,
            )
            count += 1
        self.stdout.write(f"  AI Suggestions: {count}")

    # ──────────────────────────────────────────────────────────────
    #  Custom Field Values
    # ──────────────────────────────────────────────────────────────

    def _create_custom_field_values(self, tasks, custom_fields):
        if not custom_fields:
            return
        # Map: task index -> [(field_index, value)]
        values = [
            (0, 0, "Cliente A"),    # tasks[0] → Cliente = Cliente A
            (0, 1, "Alta"),          # tasks[0] → Severidad = Alta
            (7, 1, "Crítica"),       # tasks[7] → Severidad = Crítica
            (10, 2, "API Gateway"),  # tasks[10] → Componente = API Gateway
            (10, 3, "v2.1.0"),       # tasks[10] → Versión = v2.1.0
            (17, 2, "User Service"), # tasks[17] → Componente = User Service
            (20, 4, "Visual"),       # tasks[20] → Tipo de bug = Visual
            (24, 4, "Funcional"),    # tasks[24] → Tipo de bug = Funcional
            (24, 5, "https://shop.example.com/cart"),  # tasks[24] → URL afectada
        ]
        count = 0
        for task_idx, field_idx, value in values:
            if task_idx < len(tasks) and field_idx < len(custom_fields):
                CustomFieldValue.objects.get_or_create(
                    task=tasks[task_idx], field=custom_fields[field_idx],
                    defaults={"value": value},
                )
                count += 1
        self.stdout.write(f"  Custom field values: {count}")

    # --------------------------------------------------------------
    #  Riesgos de proyecto
    # --------------------------------------------------------------

    def _create_risks(self, user, projects):
        risks = [
            (projects[0], "Dependencia de una sola persona en auth", "Concentración de conocimiento en el módulo de autenticación.", "high", "high", "open", "Formar a una segunda persona y documentar el flujo."),
            (projects[0], "Scope creep en el rediseño", "Peticiones extra de marketing durante el sprint.", "medium", "medium", "mitigated", "Congelar el scope al inicio del sprint y registrar cambios como tareas nuevas."),
            (projects[1], "Deuda técnica en el monolito", "El ritmo de migración puede resentirse por acoplamientos ocultos.", "high", "medium", "open", "Reservar 20% de capacidad por sprint para refactorización."),
            (projects[2], "Integración de pagos puede retrasarse", "La pasarela de pago aún no ha confirmado la fecha de sandbox.", "medium", "high", "open", "Abstraer el conector de pagos detrás de una interfaz."),
        ]
        count = 0
        for proj, title, desc, prob, impact, status, mit in risks:
            ProjectRisk.objects.get_or_create(
                project=proj, title=title,
                defaults={
                    "description": desc, "probability": prob,
                    "impact": impact, "status": status, "mitigation": mit,
                    "owner": user,
                },
            )
            count += 1
        self.stdout.write(f"  Riesgos: {count}")

    # --------------------------------------------------------------
    #  Dashboards personalizados
    # --------------------------------------------------------------

    def _create_dashboards(self, user):
        dashboard, created = Dashboard.objects.get_or_create(
            owner=user, name="Resumen del workspace",
            defaults={
                "is_default": True,
                "widgets": [
                    {"id": "w1", "type": "kpis", "size": "full"},
                    {"id": "w2", "type": "my_tasks", "size": "half"},
                    {"id": "w3", "type": "blocked", "size": "half"},
                    {"id": "w4", "type": "velocity", "size": "half"},
                    {"id": "w5", "type": "recent_activity", "size": "half"},
                ],
            },
        )
        self.stdout.write(f"  Dashboards: {'creado' if created else 'ya existía'}")

    # --------------------------------------------------------------
    #  Organización demo
    # --------------------------------------------------------------

    def _create_organization(self, user, projects, extra_users):
        org, _ = Organization.objects.get_or_create(
            slug="acme-demo",
            defaults={
                "name": "Acme Demo",
                "description": "Organización de demostración que agrupa los proyectos.",
                "owner": user,
            },
        )
        OrganizationMembership.objects.get_or_create(
            organization=org, user=user, defaults={"role": "owner"},
        )
        for u in extra_users[:2]:
            OrganizationMembership.objects.get_or_create(
                organization=org, user=u, defaults={"role": "member"},
            )
        # Vincula el primer proyecto a la organización
        if projects and not projects[0].organization_id:
            projects[0].organization = org
            projects[0].save(update_fields=["organization"])
        self.stdout.write("  Organización: Acme Demo")

    # --------------------------------------------------------------
    #  Políticas SLA
    # --------------------------------------------------------------

    def _create_sla_policies(self, user):
        policies = [
            ("Críticas — respuesta 4h", 0, 4, 24, True, True, True),
            ("Altas — respuesta 8h", 1, 8, 48, True, True, False),
            ("Medias — respuesta 24h", 2, 24, 120, True, False, False),
        ]
        count = 0
        for name, prio, resp, res, bump, no, na in policies:
            SlaPolicy.objects.get_or_create(
                owner=user, name=name,
                defaults={
                    "priority": prio,
                    "response_hours": resp,
                    "resolution_hours": res,
                    "bump_priority": bump,
                    "notify_owner": no,
                    "notify_assignee": na,
                },
            )
            count += 1
        self.stdout.write(f"  Políticas SLA: {count}")

    # --------------------------------------------------------------
    #  Reuniones con decisiones
    # --------------------------------------------------------------

    def _create_meetings(self, user, projects, tasks, extra_users):
        from datetime import timedelta
        meetings = [
            (
                projects[0], "Sprint planning — Offline Sync",
                timezone.now() - timedelta(days=3), 60,
                "Revisión del scope del sprint y capacidad del equipo.",
                "Decidido: la sync offline usa cola persistente con merge por campo; el conflicto se resuelve en cliente.\nDecidido: se pospone el delta-sync a la v2.",
            ),
            (
                projects[1], "Revisión de arquitectura",
                timezone.now() - timedelta(days=1), 45,
                "Estado de la migración del monolito a servicios.",
                "Decidido: se extrae primero el módulo de auth; el gateway queda para el final.\nDecidido: contratos OpenAPI obligatorios por servicio.",
            ),
            (
                projects[0], "Daily — bloqueos del sprint",
                timezone.now() + timedelta(days=1), 15,
                "Revisión diaria: rate limiting bloqueado, asignar segundo backend.",
                "",
            ),
            (
                projects[2], "Demo con stakeholders",
                timezone.now() + timedelta(days=4), 30,
                "Demo del nuevo checkout y propuesta de iteración.",
                "",
            ),
        ]
        count = 0
        for proj, title, when, mins, notes, decisions in meetings:
            m, created = Meeting.objects.get_or_create(
                title=title, owner=user,
                defaults={
                    "project": proj, "scheduled_at": when,
                    "duration_minutes": mins, "notes": notes,
                    "decisions": decisions,
                },
            )
            if created and extra_users:
                m.attendees.add(user, *extra_users[:2])
            count += 1
        self.stdout.write(f"  Reuniones: {count}")

    # --------------------------------------------------------------
    #  Enlaces de compartición públicos
    # --------------------------------------------------------------

    def _create_share_links(self, user, projects):
        for i, proj in enumerate(projects[:2]):
            ShareLink.objects.get_or_create(
                project=proj, created_by=user,
            )
        self.stdout.write(f"  Share links: {ShareLink.objects.filter(created_by=user).count()}")

    # --------------------------------------------------------------
    #  Formularios de intake
    # --------------------------------------------------------------

    def _create_intake_forms(self, user, projects):
        forms = [
            (
                projects[0], "Reporte de bug",
                "Formulario público para reportar errores de la app.",
                [
                    {"name": "title", "label": "Resumen del bug", "type": "text", "required": True},
                    {"name": "description", "label": "Pasos para reproducir", "type": "textarea", "required": True},
                    {"name": "priority", "label": "Severidad percibida", "type": "select", "required": False,
                     "options": ["0", "1", "2", "3"]},
                    {"name": "device", "label": "Dispositivo", "type": "select", "required": False,
                     "options": ["Android", "iOS"]},
                ],
                {"state": "backlog", "task_type": "bug"},
            ),
            (
                projects[2], "Petición de cambio web",
                "Solicitudes de cambios para el e-commerce.",
                [
                    {"name": "title", "label": "Qué quieres cambiar", "type": "text", "required": True},
                    {"name": "description", "label": "Motivo y detalles", "type": "textarea", "required": True},
                    {"name": "url", "label": "Página afectada", "type": "text", "required": False},
                ],
                {"state": "backlog"},
            ),
        ]
        count = 0
        for proj, name, desc, schema, defaults in forms:
            IntakeForm.objects.get_or_create(
                owner=user, project=proj, name=name,
                defaults={
                    "description": desc, "schema": schema,
                    "task_defaults": defaults,
                },
            )
            count += 1
        self.stdout.write(f"  Intake forms: {count}")

    # --------------------------------------------------------------
    #  Pizarras
    # --------------------------------------------------------------

    def _create_whiteboards(self, user, projects):
        wb, _ = Whiteboard.objects.get_or_create(
            project=projects[0], owner=user, name="Mapa de arquitectura",
            defaults={
                "content": {
                    "nodes": [
                        {"id": "n1", "x": 80, "y": 80, "text": "App móvil", "color": "#1976d2", "w": 160, "h": 64},
                        {"id": "n2", "x": 320, "y": 80, "text": "API Gateway", "color": "#7b1fa2", "w": 160, "h": 64},
                        {"id": "n3", "x": 560, "y": 80, "text": "Backend Django", "color": "#388e3c", "w": 160, "h": 64},
                        {"id": "n4", "x": 320, "y": 220, "text": "Cache local", "color": "#f57c00", "w": 160, "h": 64},
                    ],
                    "edges": [
                        {"from": "n1", "to": "n2"},
                        {"from": "n2", "to": "n3"},
                        {"from": "n1", "to": "n4"},
                    ],
                },
            },
        )
        self.stdout.write("  Pizarras: 1")

    # --------------------------------------------------------------
    #  Transiciones de workflow
    # --------------------------------------------------------------

    def _create_workflow_transitions(self, projects):
        from apps.projects.models import WorkflowTransition
        edges = [
            ("backlog", "pending"),
            ("pending", "in_progress"),
            ("in_progress", "review"),
            ("review", "completed"),
            ("pending", "blocked"),
            ("in_progress", "blocked"),
            ("blocked", "pending"),
            ("completed", "archived"),
            ("pending", "cancelled"),
        ]
        for a, b in edges:
            WorkflowTransition.objects.get_or_create(
                project=projects[0], from_state=a, to_state=b,
            )
        self.stdout.write(
            f"  Transiciones de workflow: "
            f"{WorkflowTransition.objects.filter(project=projects[0]).count()}"
        )

    # --------------------------------------------------------------
    #  Portafolios
    # --------------------------------------------------------------

    def _create_portfolios(self, user, projects):
        p, created = Portfolio.objects.get_or_create(
            owner=user, name="Producto 2026",
            defaults={"color": "#7b1fa2"},
        )
        if created or p.projects.count() == 0:
            p.projects.set(projects[:2])
        self.stdout.write(
            f"  Portafolios: {Portfolio.objects.filter(owner=user).count()}"
        )

    # --------------------------------------------------------------
    #  Calendarios externos (iCal inbound)
    # --------------------------------------------------------------

    def _create_external_calendars(self, user):
        from apps.collaboration.models import ExternalCalendar
        cal, _ = ExternalCalendar.objects.get_or_create(
            user=user, name="Calendario equipo (Google)",
            defaults={
                "url": "https://calendar.google.com/calendar/ical/demo/basic.ics",
                "color": "#4caf50",
                "last_synced_at": timezone.now(),
            },
        )
        self.stdout.write(
            f"  Calendarios externos: "
            f"{ExternalCalendar.objects.filter(user=user).count()}"
        )

    # --------------------------------------------------------------
    #  Wiki
    # --------------------------------------------------------------

    def _create_wiki_pages(self, user, projects):
        from apps.wiki.models import WikiPage
        pages = [
            (projects[2], None, "Guía de onboarding",
             "# Onboarding\n\nBienvenido al equipo. Pasos iniciales:\n\n- Clona el repo y ejecuta `docker compose up`\n- Lee la guía de estilo\n- Pide acceso a los entornos de staging\n"),
            (projects[2], None, "Convenciones de código",
             "# Convenciones\n\n- Python: black + isort, líneas de 100\n- TypeScript: prettier + eslint strict\n- Commits: conventional commits en inglés\n"),
            (projects[1], None, "Runbook de despliegue",
             "# Runbook\n\n1. Mergear a main\n2. CI ejecuta tests y build\n3. Deploy a staging automático\n4. Promoción manual a producción\n"),
        ]
        for proj, parent, title, content in pages:
            WikiPage.objects.get_or_create(
                title=title, owner=user,
                defaults={"project": proj, "parent": parent,
                          "content": content, "updated_by": user},
            )
        self.stdout.write(
            f"  Páginas wiki: {WikiPage.objects.filter(owner=user).count()}"
        )
