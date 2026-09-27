# TODOlist

Aplicación web full-stack de gestión de tareas, proyectos y productividad.
Diseñada para crecer hacia un **LifeOS** (tareas + proyectos + Kanban +
calendario + hábitos + objetivos + IA).

> Repositorio: https://github.com/ToDoSolutions/TODOlist.git

## Stack

| Capa         | Tecnología                                                        |
|--------------|-------------------------------------------------------------------|
| Frontend     | React 18 + TypeScript + Vite + MUI + TanStack Query + Zod         |
| Backend      | Django 5 + Django REST Framework + SimpleJWT + Celery             |
| GraphQL      | graphene-django                                                   |
| Real-time    | Django Channels + WebSocket                                       |
| Base datos   | PostgreSQL (full-text search)                                     |
| Caché/Cola   | Redis (caching + Celery broker)                                   |
| PWA          | vite-plugin-pwa (service worker, offline, installable)           |
| Contenedores | Docker + Docker Compose                                           |
| CI/CD        | GitHub Actions                                                    |

## Features

### Core
- **Autenticación**: registro, login, JWT (access + refresh) en cookies httpOnly con CSRF double-submit, 2FA con TOTP
- **Proyectos**: crear, listar, archivar, compartir con roles
- **Tareas**: CRUD completo, título, descripción, estado, prioridad, fecha límite,
  story points, tipo (bug, feature, task, etc.), subtareas, comentarios, adjuntos
- **Estados**: backlog, pendiente, en progreso, bloqueada, en revisión,
  completada, cancelada, archivada
- **Prioridades**: P0 Crítica → P5 Algún día
- **Etiquetas**: personalizadas y coloreadas
- **Épicas**: agrupar tareas relacionadas
- **Filtros**: por estado, prioridad, etiqueta, fecha, tipo, assignee
- **Búsqueda full-text** sobre tareas y proyectos (PostgreSQL)

### Vistas
- **Lista**: con ordenación, filtros y edición inline
- **Kanban**: con swimlanes (prioridad, assignee, sprint), WIP limits, quick-add
- **Tabla**: con edición inline, multi-selección, export CSV
- **Calendario**: vista mensual de tareas por fecha límite
- **Dashboard**: KPIs, métricas de flujo, salud del backlog, distribuciones

### Planificación ágil
- **Sprints**: crear, activar, cerrar, capacidad, burndown
- **Sprint planning**: asignar tareas a sprints, story points
- **Métricas**: lead time, cycle time, throughput, WIP, backlog health

### Integración GitHub
- **GitHub App**: instalación OAuth, sync bidireccional
- **Issues → Tasks**: sincronización automática
- **Webhooks**: idempotencia, retries con backoff exponencial, DLQ
- **PRs**: pull requests, merges, reviews
- **Commits**: tracking de commits por tarea
- **Releases**: versiones y changelog
- **CI/CD**: check runs, estados de CI

### Colaboración
- **Equipos**: crear equipos, roles (owner/admin/member/guest)
- **Miembros de proyecto**: compartir con roles (owner/editor/viewer)
- **Invitaciones**: por email con token
- **Menciones**: @user en comentarios con notificación automática
- **Permisos**: granulares por proyecto

### Notificaciones
- **In-app**: campana con badge, popover, auto-refresh
- **Email**: configurable por tipo y preferencias
- **17 tipos**: tarea asignada, vencida, completada, comentada, bloqueada,
  sprint iniciado/cerrado, mención, PR abierto/merged, CI fallida, etc.
- **Preferencias**: por usuario y tipo (in_app, email, digest)

### Automatizaciones
- **Reglas**: 9 triggers (tarea creada, estado cambiado, vencida, etc.)
- **Condiciones**: equals, not_equals, contains, gt, lt (AND combinables)
- **Acciones**: set_priority, set_state, set_assignee, add_tag, set_due_date,
  move_to_sprint, subtasks_in_progress, create_notification, create_task
- **Logs**: historial de ejecuciones con status y errores
- **Chequeo diario**: tareas vencidas y sprints por terminar (Celery beat)

### API pública
- **API keys**: hasheadas (SHA256), scopes (read/write/admin), revocables
- **Rate limiting**: burst (60/min), authenticated (300/hour), API key (1000/hour)
- **OpenAPI docs**: Swagger UI (`/api/docs/`), ReDoc (`/api/redoc/`)
- **GraphQL**: endpoint `/graphql/` con queries y mutations

### Auditoría
- **Audit log**: 10 tipos de acción (login, create, update, delete, etc.)
- **Tracking**: actor, recurso, old/new values, IP, user agent
- **Filtros**: por acción y tipo de recurso

### Seguridad
- **2FA**: TOTP con apps autenticadoras (Google Authenticator, Authy)
- **Backup codes**: 10 códigos de un solo uso
- **API keys**: hasheadas, con expiración y revocación
- **Rate limiting**: en todos los endpoints

### PWA
- **Instalable**: manifest, icons, standalone display
- **Offline**: service worker con cache de assets y API
- **Install prompt**: snackbar con botón instalar
- **Offline indicator**: aviso cuando no hay conexión

### Real-time
- **WebSocket**: actualizaciones en vivo de tareas, notificaciones
- **Channels**: Django Channels + Redis channel layer

### Extras
- **Dark mode**: toggle de tema claro/oscuro
- **i18n**: español/inglés
- **Time tracking**: registro de tiempo por tarea
- **File attachments**: adjuntos en tareas y comentarios
- **Bulk operations**: actualizar múltiples tareas a la vez
- **Task templates**: plantillas reutilizables
- **Custom fields**: campos personalizados por proyecto
- **Outgoing webhooks**: notificar a servicios externos

## Estructura

```
TODOlist/
├── backend/               # Django + DRF + Celery
│   ├── apps/
│   │   ├── users/         # Auth, 2FA, API keys
│   │   ├── projects/      # Proyectos
│   │   ├── tasks/         # Tareas, sprints, épicas, comentarios, métricas
│   │   ├── tags/          # Etiquetas
│   │   ├── integrations/  # GitHub, webhooks
│   │   ├── notifications/ # Notificaciones
│   │   ├── automations/   # Reglas de automatización
│   │   ├── collaboration/ # Equipos, menciones, audit
│   │   └── graphql_app/   # GraphQL endpoint + WebSocket consumers
│   ├── config/            # Settings, URLs, ASGI (JWT WS auth)
│   ├── tests/             # 2220 tests (1936 + 284 contract)
│   └── Dockerfile
├── frontend/              # React + Vite + PWA
│   ├── src/
│   │   ├── pages/         # 15+ páginas
│   │   ├── components/    # Componentes reutilizables
│   │   ├── api/           # API client
│   │   └── auth/          # Auth context
│   └── Dockerfile
├── .github/workflows/     # CI/CD
├── docker-compose.yml
└── README.md
```

## Puesta en marcha (desarrollo)

Requisitos: Docker y Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/
- Swagger docs: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/
- GraphQL: http://localhost:8000/graphql/
- Admin Django: http://localhost:8000/admin/

## Variables de entorno

Ver [`.env.example`](./.env.example).

## Testing

```bash
# Backend
cd backend
python -m pytest

# Frontend
cd frontend
npx vitest run
```

## CI/CD

GitHub Actions ejecuta automáticamente:
- Tests de backend (pytest)
- Tests de frontend (vitest)
- Build de frontend
- Build de Docker images

## Licencia

MIT — ver [LICENSE](./LICENSE).
