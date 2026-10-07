<h1 align="center">TODOlist</h1>

<p align="center">
  <strong>Gestión de trabajo autoalojable y open source (AGPLv3)</strong><br>
  Tareas, proyectos, sprints, OKRs, wiki, automatizaciones con SLA,<br>
  sync offline con resolución de conflictos y E2EE opcional en cliente.
</p>

<p align="center">
  <a href="https://github.com/ToDoSolutions/TODOlist/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/ToDoSolutions/TODOlist/ci.yml?branch=main&label=CI" alt="CI">
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/ToDoSolutions/TODOlist" alt="Licencia AGPLv3">
  </a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/node-20%2B-blue" alt="Node 20+">
</p>

<p align="center">
  <a href="./README.en.md">English</a> ·
  <a href="#inicio-rápido">Inicio rápido</a> ·
  <a href="./docs/ARCHITECTURE.md">Arquitectura</a> ·
  <a href="./CONTRIBUTING.md">Contribuir</a> ·
  <a href="./SECURITY.md">Seguridad</a>
</p>

<p align="center">
  <img src="docs/assets/screenshots/kanban.png" alt="Tablero Kanban con columnas por estado, tarjetas con prioridad, etiquetas, puntos y fecha" width="900">
</p>
<table align="center">
<tr>
  <td><img src="docs/assets/screenshots/dashboard.png" alt="Dashboard con KPIs: abiertas, completadas, vencidas, bloqueadas, métricas de flujo y salud del backlog" width="420"></td>
  <td><img src="docs/assets/screenshots/tasks-list.png" alt="Lista de tareas con búsqueda rápida, filtros por estado y prioridad, y búsquedas guardadas" width="420"></td>
  <td><img src="docs/assets/screenshots/sprints.png" alt="Sprints con estado activo/planificado/cerrado, rango de fechas y tareas asignadas" width="420"></td>
</tr>
<tr>
  <td><img src="docs/assets/screenshots/calendar.png" alt="Calendario mensual con tareas coloreadas por estado en sus fechas de vencimiento" width="420"></td>
  <td><img src="docs/assets/screenshots/task-detail.png" alt="Editor de tarea con sub-tareas, dependencias, adjuntos, propiedades y temporizador" width="420"></td>
  <td><img src="docs/assets/screenshots/gantt.png" alt="Diagrama de Gantt con barras de tareas por estado agrupadas por proyecto y sprints" width="420"></td>
</tr>
<tr>
  <td><img src="docs/assets/screenshots/my-work.png" alt="Mi trabajo: bandeja con vencidas, para hoy, bloqueadas, en progreso y próximos 7 días" width="420"></td>
  <td><img src="docs/assets/screenshots/automations.png" alt="Reglas de automatización con trigger y acción, activables y con contador de ejecuciones" width="420"></td>
  <td><img src="docs/assets/screenshots/projects.png" alt="Proyectos en tarjetas con contadores de tareas, sprints y épicas" width="420"></td>
</tr>
</table>
<p align="center"><sub>Dashboard · Tareas · Sprints · Calendario · Detalle · Gantt · Mi trabajo · Automatizaciones · Proyectos</sub></p>

<details>
<summary>Todas las capturas — 82 pantallas agrupadas por dominio</summary>

### Inicio y bandejas

| Inicio | Bandeja de entrada |
|---|---|
| ![Inicio: KPIs del día, proyectos recientes, sprint activo y actividad reciente](docs/assets/screenshots/app-home.png) | ![Bandeja de entrada: tareas capturadas pendientes de triaje](docs/assets/screenshots/inbox.png) |

| Bandeja de atención | Enfoque |
|---|---|
| ![Bandeja de atención: invitaciones, menciones, conflictos y alertas accionables](docs/assets/screenshots/attention.png) | ![Enfoque: temporizador Pomodoro vinculable a una tarea](docs/assets/screenshots/focus.png) |

| Productividad | |
|---|---|
| ![Productividad: métricas personales de enfoque y tareas completadas](docs/assets/screenshots/productivity.png) | |

### Tareas y vistas

| Tabla editable | Dependencias |
|---|---|
| ![Vista tabla con edición en línea y columnas configurables](docs/assets/screenshots/tasks-table.png) | ![Dependencias de una tarea: bloquea y es bloqueada por](docs/assets/screenshots/dependencies.png) |

| Campos personalizados | Etiquetas |
|---|---|
| ![Campos personalizados por proyecto](docs/assets/screenshots/custom-fields.png) | ![Gestión de etiquetas con color y contador de uso](docs/assets/screenshots/tags.png) |

| Favoritas | Completadas |
|---|---|
| ![Favoritas: acceso rápido a las tareas marcadas](docs/assets/screenshots/favorites.png) | ![Completadas: archivo de tareas cerradas](docs/assets/screenshots/completed.png) |

| Papelera | Backlog |
|---|---|
| ![Papelera: restaurar o borrado definitivo](docs/assets/screenshots/trash.png) | ![Backlog del proyecto ordenable por prioridad](docs/assets/screenshots/backlog.png) |

| Reglas de recurrencia | Registros de tiempo |
|---|---|
| ![Reglas de recurrencia: frecuencia y siguiente ocurrencia](docs/assets/screenshots/recurrence-rules.png) | ![Registros de tiempo con timer en vivo por tarea](docs/assets/screenshots/time-entries.png) |

| Importar / exportar | |
|---|---|
| ![Importar y exportar: CSV, JSON y feed iCal por token](docs/assets/screenshots/import-export.png) | |

### Proyecto y planificación

| Proyecto | Tareas del proyecto |
|---|---|
| ![Vista del proyecto: resumen, progreso y accesos a las vistas](docs/assets/screenshots/project.png) | ![Listado de tareas dentro del proyecto](docs/assets/screenshots/project-tasks.png) |

| Ajustes del proyecto | Riesgos |
|---|---|
| ![Ajustes del proyecto: miembros, etiquetas de estado y plantilla](docs/assets/screenshots/project-settings.png) | ![Registro de riesgos: probabilidad × impacto, mitigación y estado](docs/assets/screenshots/risks.png) |

| Portafolios | Plantillas |
|---|---|
| ![Portafolios que agrupan proyectos relacionados](docs/assets/screenshots/portfolios.png) | ![Plantillas de proyecto aplicables con tareas y etiquetas](docs/assets/screenshots/templates.png) |

| Épicas | Roadmap |
|---|---|
| ![Épicas con progreso y tareas asociadas](docs/assets/screenshots/epics.png) | ![Roadmap: épicas como lanes temporales y sprints como hitos](docs/assets/screenshots/roadmap.png) |

| Burndown | Capacidad |
|---|---|
| ![Burndown del sprint con línea ideal de trabajo restante](docs/assets/screenshots/burndown.png) | ![Capacidad del equipo: horas estimadas vs capacidad semanal](docs/assets/screenshots/capacity.png) |

| Dashboards | OKRs |
|---|---|
| ![Dashboards personalizables con widgets de KPIs y gráficas](docs/assets/screenshots/dashboards.png) | ![OKRs con key results e histórico de progreso](docs/assets/screenshots/okrs.png) |

| Decisiones | Reuniones |
|---|---|
| ![Decisiones registradas con contexto y responsable](docs/assets/screenshots/decisions.png) | ![Reuniones: notas, asistentes y action items convertibles en tareas](docs/assets/screenshots/meetings.png) |

| Whiteboards | Wiki |
|---|---|
| ![Whiteboards colaborativos por proyecto](docs/assets/screenshots/whiteboards.png) | ![Wiki con jerarquía de páginas, markdown y versionado](docs/assets/screenshots/wiki.png) |

| Changelog | |
|---|---|
| ![Changelog del proyecto con entradas datadas](docs/assets/screenshots/changelog.png) | |

### Colaboración e integraciones

| Equipos | Invitación |
|---|---|
| ![Equipos con miembros, roles y auditoría de cambios](docs/assets/screenshots/teams.png) | ![Invitación a equipo o proyecto por token seguro](docs/assets/screenshots/invitation.png) |

| Enlaces compartidos | Vista pública |
|---|---|
| ![Enlaces de compartición activos con revocación](docs/assets/screenshots/shares.png) | ![Proyecto compartido read-only sin login](docs/assets/screenshots/share-public.png) |

| Formularios intake | Intake público |
|---|---|
| ![Editor de formularios intake: campos, obligatorios y defaults](docs/assets/screenshots/intake-forms.png) | ![Formulario intake público — crea la tarea sin cuenta](docs/assets/screenshots/intake-public.png) |

| GitHub | Integraciones |
|---|---|
| ![Integración GitHub: PRs, commits, releases y check-runs vinculados](docs/assets/screenshots/github.png) | ![Integraciones: Slack/Discord, n8n y calendarios externos](docs/assets/screenshots/integrations.png) |

| Webhooks | API keys |
|---|---|
| ![Webhooks entrantes y salientes con firma HMAC y entregas](docs/assets/screenshots/webhooks.png) | ![API keys con scopes para la API pública](docs/assets/screenshots/api-keys.png) |

| Notificaciones | Búsqueda |
|---|---|
| ![Centro de notificaciones con preferencias y digest](docs/assets/screenshots/notifications.png) | ![Búsqueda global con sintaxis: assigned:me, due:today, tag:…](docs/assets/screenshots/search.png) |

| Ayuda | |
|---|---|
| ![Ayuda y referencia rápida de atajos](docs/assets/screenshots/help.png) | |

### Cuenta, seguridad y sync

| Cuenta | Perfil |
|---|---|
| ![Cuenta: datos personales, sesiones y desactivación](docs/assets/screenshots/account.png) | ![Perfil: preferencias de usuario y actividad](docs/assets/screenshots/profile.png) |

| Seguridad | Cifrado E2E |
|---|---|
| ![Seguridad: 2FA TOTP, backup codes y sesiones activas](docs/assets/screenshots/security.png) | ![E2EE: claves por dispositivo y backup cifrado con passphrase](docs/assets/screenshots/encryption.png) |

| Sync offline | Sesión expirada |
|---|---|
| ![Sync offline: dispositivos, revocación y conflictos por campo](docs/assets/screenshots/offline-sync.png) | ![Sesión expirada con re-login y conservación de cambios locales](docs/assets/screenshots/session-expired.png) |

| Cuenta suspendida | Actividad |
|---|---|
| ![Cuenta suspendida: aviso y vía de contacto](docs/assets/screenshots/suspended.png) | ![Actividad global: feed unificado de tareas y auditoría](docs/assets/screenshots/activity.png) |

| Auditoría | |
|---|---|
| ![Audit log exportable con actor, acción y timestamp](docs/assets/screenshots/audit.png) | |

### Administración

| Panel admin | Jobs |
|---|---|
| ![Panel de administración con métricas de la instancia](docs/assets/screenshots/admin.png) | ![Colas de trabajos en segundo plano (Celery)](docs/assets/screenshots/admin-jobs.png) |

| Organizaciones | Roles |
|---|---|
| ![Organizaciones: tenants con membresías y roles](docs/assets/screenshots/admin-organizations.png) | ![Roles y permisos granulares por ámbito](docs/assets/screenshots/admin-roles.png) |

| Políticas SLA | Feature flags |
|---|---|
| ![Políticas SLA por prioridad con escalado automático](docs/assets/screenshots/admin-sla.png) | ![Feature flags como kill switch por prefijo](docs/assets/screenshots/feature-flags.png) |

### Acceso y estados

| Login | Registro |
|---|---|
| ![Inicio de sesión](docs/assets/screenshots/login.png) | ![Registro de cuenta](docs/assets/screenshots/register.png) |

| Recuperar contraseña | Restablecer |
|---|---|
| ![Recuperación de contraseña por email](docs/assets/screenshots/forgot-password.png) | ![Formulario de restablecimiento con token](docs/assets/screenshots/reset-password.png) |

| Verificar email | Onboarding |
|---|---|
| ![Verificación de email pendiente](docs/assets/screenshots/verify-email.png) | ![Onboarding inicial de la cuenta](docs/assets/screenshots/onboarding.png) |

| 403 | 404 |
|---|---|
| ![Acceso denegado (403)](docs/assets/screenshots/forbidden.png) | ![Página no encontrada (404)](docs/assets/screenshots/not-found.png) |

### Asistente IA

| | |
|---|---|
| ![Asistente inteligente: sugerencias sobre tareas con aceptar/rechazar](docs/assets/screenshots/ai-assistant.png) | ![Calendarios externos suscritos](docs/assets/screenshots/calendars.png) |

| Workflows | |
|---|---|
| ![Workflows: transiciones de estado configurables por proyecto](docs/assets/screenshots/workflows.png) | |

</details>

> **English** — Self-hosted work management: tasks, projects, sprints, OKRs,
> wiki, SLA automations, offline sync with field-level conflict merge, and
> optional client-side E2EE. Public REST + GraphQL + WebSocket + CalDAV/MCP
> API. Think "self-hosted Todoist × Linear-lite".

---

## Qué es

TODOlist es para equipos e individuos que quieren las capacidades de un
gestor de trabajo serio **sin ceder sus datos**: el servidor solo ve
ciphertext en tareas cifradas, todo es self-hosted single-node, y cada
canal de escritura (REST, GraphQL, CalDAV, MCP, offline sync, GitHub,
automatizaciones) pasa por la misma frontera de autorización.

Ver [docs/SCOPE.md](./docs/SCOPE.md) para qué hace y qué **no** hace
(sin videollamadas, sin marketplace, sin multi-región).

## Estado del proyecto

> [!NOTE]
> Beta funcional. El modelo de datos y la API REST son estables; GraphQL
> y el sync offline pueden recibir cambios compatibles documentados en
> `CHANGELOG.md`. Producción soportada vía Docker Compose/K8s/Helm.

## Inicio rápido

Requisitos: Docker + Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

| URL | Qué es |
|---|---|
| <http://localhost:5173> | Frontend |
| <http://localhost:8000/api/docs/> | Swagger UI (OpenAPI) |
| <http://localhost:8000/graphql/> | GraphQL |
| <http://localhost:8000/admin/> | Admin Django |

Datos de demo (opt-in): `SEED_DEV=1 docker compose up --build`.

## Características

- **Tareas completas** — subtareas, comentarios, adjuntos, dependencias
  con detección de ciclos, recurrencia, estimaciones, time tracking.
- **Vistas** — lista, Kanban con WIP limits, tabla editable, calendario,
  Gantt/roadmap, dashboards con KPIs de flujo.
- **Agilidad real** — sprints con capacidad/burndown, story points,
  velocity estimado-vs-real, DORA metrics.
- **Colaboración** — organizaciones, equipos, roles granulares,
  menciones, invitaciones, wiki con revisiones, intake forms públicos.
- **Automatización** — reglas trigger/condición/acción, políticas SLA
  con escalado, webhooks salientes con HMAC, integraciones Slack/Discord.
- **Integración GitHub** — App OAuth, sync bidireccional, PRs/commits/
  releases/check-runs vinculados a tareas.
- **API pública** — REST (OpenAPI + contract testing), GraphQL con
  depth-limit, WebSockets, CalDAV/iCal, MCP server, API keys con scopes.
- **Privacidad** — E2EE opt-in (AES-GCM + RSA-OAEP por dispositivo,
  el servidor nunca ve plaintext), sync offline con merge por campo.
- **Seguridad** — 2FA TOTP + backup codes, SSO SAML/SCIM por
  organización, audit log exportable, rate limiting por scope.

El detalle por feature y su nivel de madurez: [docs/MATURITY.md](./docs/MATURITY.md).

## Arquitectura

```mermaid
flowchart LR
    User --> Web["React 18 + Vite + MUI (PWA)"]
    Web -->|"REST / GraphQL / WS"| API["Django 5 + DRF + Channels"]
    API --> DB[(PostgreSQL)]
    API --> Redis[("Redis · caché + broker")]
    API --> Worker["Celery + Beat"]
    API -->|webhooks HMAC| Ext[Servicios externos]
    Ext -->|"GitHub sync"| API
```

Todos los canales de escritura convergen en `apps/tasks/services.py` +
`for_user(write=True)` — la frontera única de autorización
([ADR-001](./docs/decisions/ADR-001-permissions-model.md),
[ADR-004](./docs/decisions/ADR-004-multi-channel-parity.md)).

Stack completo y razones: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Configuración

Todas las variables documentadas en [`.env.example`](./.env.example).
Las que **fallan al arrancar** si faltan en producción: `DJANGO_SECRET_KEY`,
`DATA_ENCRYPTION_KEYS`, `POSTGRES_*`. Las flags `FEATURE_*` actúan como
kill switch por prefijo (`/api/ai/*`, `/api/sync/*`, E2EE).

## Estructura

```text
backend/    Django + DRF + Celery + Channels (14 apps, ~50 modelos)
frontend/   React + Vite + MUI + TanStack Query (PWA)
docs/       SCOPE · ARCHITECTURE · decisions/ · operations/ · security/
deploy/     Helm + K8s + Terraform
integrations/n8n-nodes-todolist/   plugin n8n
```

## Verificación

```bash
# Backend — 2.826 tests (pytest, ~12 min con -n 8)
cd backend && python -m pytest tests/ -n 8 -q

# Frontend — 145 tests vitest + typecheck + lint
cd frontend && npx vitest run && npx tsc --noEmit && npx eslint src
```

CI además ejecuta: ruff + bandit, contract testing (schemathesis),
pip-audit + npm audit, gitleaks, markdownlint + check de enlaces,
builds Docker y OpenSSF Scorecard.

## Documentación

- **Usar/operar**: [docs/operations/](./docs/operations/) — SLO/SLI,
  incidentes, backup-restore, PRR, riesgos, revisión trimestral.
- **Desarrollar**: [AGENTS.md](./AGENTS.md) (comandos + decisiones) ·
  [docs/GOLDEN_PATHS.md](./docs/GOLDEN_PATHS.md) ·
  [docs/decisions/](./docs/decisions/) (ADRs) ·
  [docs/DEPENDENCIES.md](./docs/DEPENDENCIES.md).
- **Gobernanza**: [docs/QUALITY.md](./docs/QUALITY.md) ·
  [docs/TECH_DEBT.md](./docs/TECH_DEBT.md) ·
  [docs/DEPRECATION.md](./docs/DEPRECATION.md).
- **Seguridad/datos**: [docs/security/e2ee-threat-model.md](./docs/security/e2ee-threat-model.md) ·
  [docs/PRIVACY.md](./docs/PRIVACY.md) ·
  [docs/architecture/failure-modes.md](./docs/architecture/failure-modes.md).

## Limitaciones conocidas

- Single-node self-hosted — sin escalado multi-región.
- El contenido E2EE no es buscable ni visible para la IA (por diseño;
  ver el [threat model](./docs/security/e2ee-threat-model.md)).
- Sin releases firmados ni SBOM publicado todavía (TD-008 — se activa
  al publicar la primera release).
- E2EE sin clave privada de backup = datos irrecuperables.

Registro completo con prioridades: [docs/TECH_DEBT.md](./docs/TECH_DEBT.md).

## Contribución

[`CONTRIBUTING.md`](./CONTRIBUTING.md) — setup, Definition of Done/Ready,
checklist del revisor. Buen punto de entrada: las recetas de
[docs/GOLDEN_PATHS.md](./docs/GOLDEN_PATHS.md).

## Seguridad

**No abras un issue público** para vulnerabilidades — proceso privado en
[`SECURITY.md`](./SECURITY.md) (GitHub Security Advisories).

## Licencia

[AGPLv3](./LICENSE).
