# Arquitectura — TODOlist

## 1. Contexto (C4 nivel 1)

```mermaid
C4Context
    Person(user, "Usuario", "Gestiona tareas/proyectos, solo o en equipo")
    System(todolist, "TODOlist", "Plataforma de gestión de trabajo: tasks, sprints, automatizaciones, sync offline")
    System_Ext(github, "GitHub", "Issues, PRs, commits, releases, check runs, webhooks")
    System_Ext(chat, "Slack/Discord", "Notificaciones a canales")
    System_Ext(oauth, "Google/GitHub OAuth", "Social login")

    Rel(user, todolist, "HTTPS + WSS", "REST/GraphQL, tiempo real")
    Rel(todolist, github, "REST + GraphQL API", "Sync bidireccional")
    Rel(github, todolist, "Webhooks (HMAC)", "Eventos push")
    Rel(todolist, chat, "Webhooks salientes", "Alertas")
    Rel(user, oauth, "OAuth 2.0", "Login social")
```

## 2. Contenedores (C4 nivel 2)

```mermaid
C4Container
    Person(user, "Usuario")

    Container(spa, "SPA React", "React 18 + TS + Vite + MUI + TanStack Query + PWA", "UI, offline queue, SW")
    Container(api, "API Django", "DRF + SimpleJWT + Graphene + Channels", "REST/GraphQL/WS")
    ContainerDb(pg, "PostgreSQL", "", "Datos + FTS (tsvector + GIN)")
    ContainerDb(redis, "Redis", "", "Cache, channel layer, Celery broker")
    Container(celery, "Celery workers", "", "Sync GitHub, recurrencias, retries")
    Container(beat, "Celery beat", "", "Scheduler: sync 15min, recurrencia 6AM")

    Rel(user, spa, "Usa")
    Rel(spa, api, "HTTPS/WSS, cookies httpOnly + CSRF")
    Rel(api, pg, "ORM")
    Rel(api, redis, "cache/sessions/channels")
    Rel(api, celery, "encola tareas")
    Rel(celery, redis, "broker")
    Rel(celery, pg, "ORM")
```

## 3. Mapa de dominios (17 apps)

```mermaid
graph LR
    subgraph Core
        tasks[tasks<br/>15 modelos: Task, Sprint, Epic,<br/>Subtask, Comment, Attachment,<br/>RecurrenceRule, TaskTemplate,<br/>CustomField, TimeEntry, TaskActivity,<br/>TaskRelation, SavedSearch, OutgoingWebhook]
        projects[projects<br/>Project]
        tags[tags]
        okrs[okrs<br/>Objective, KeyResult]
    end
    subgraph Collaboration
        collaboration[collaboration<br/>Team, ProjectMember,<br/>Invitation, Mention, AuditLog]
        notifications[notifications<br/>Notification, Preferences]
    end
    subgraph Integrations
        integrations[integrations<br/>GitHubInstallation/Repo/PR/<br/>Commit/Release/CheckRun,<br/>TaskGitHubLink, WebhookDelivery]
        integrations_chat[integrations_chat<br/>Slack/Discord]
        social_auth[social_auth<br/>OAuth]
    end
    subgraph Platform
        automations[automations<br/>Rule, Log]
        offline_sync[offline_sync<br/>SyncDevice, SyncOperation]
        encryption[encryption<br/>PublicKey, EncryptedTask, KeyShare]
        ai_assistant[ai_assistant<br/>AiSuggestion]
        feature_flags[feature_flags]
        graphql_app[graphql_app<br/>schema + consumers]
        monitoring[monitoring<br/>Prometheus/health/OTel]
        users[users<br/>APIKey, TwoFactor]
    end

    tasks --> projects
    tasks --> collaboration
    tasks --> notifications
    automations --> tasks
    offline_sync --> tasks
    encryption --> tasks
    integrations --> tasks
    ai_assistant --> tasks
    notifications --> users
```

## 4. Secuencia: sync offline con conflicto

```mermaid
sequenceDiagram
    participant C as Cliente (PWA offline)
    participant A as API
    participant DB as PostgreSQL

    C->>A: POST /api/sync/operations/ [op, base_version=3]
    A->>DB: SELECT task FOR UPDATE
    alt base_version < task.version (conflicto)
        DB-->>A: task.version=5
        A-->>C: {status: conflict, server_data, current_version:5}
        Note over C: Política: server wins.<br/>Cliente debe mergear o descartar
    else sin conflicto
        A->>DB: UPDATE task, version=version+1
        A-->>C: {status: applied, current_version:4}
    end
```

### Política de resolución de conflictos

| Caso | Resolución | Quién gana |
|---|---|---|
| Update con `base_version` desactualizada | `conflict` + `server_data` | **Servidor** (last-write-wins implícito: el cliente decide si reintenta) |
| Update sin `base_version` | `rejected` | n/a — se exige para detección |
| Delete con versión desactualizada | `conflict` + `server_data` | **Servidor** |
| Dos usuarios editan campos distintos | Field-level: el último write pisa todo el recurso (no hay merge por campo) | Último que sincroniza |
| `SyncDevice` revocado | Ops rechazadas | Servidor |

La resolución manual queda del lado del cliente: al recibir `conflict` con `server_data`, la PWA muestra el diff y permite reintentar con la nueva `base_version` o descartar la operación local.

## 5. Flujo: webhook GitHub

```mermaid
sequenceDiagram
    participant G as GitHub
    participant A as API
    participant Q as Celery
    participant DB

    G->>A: POST /api/webhooks/github/ (firma HMAC)
    A->>A: verifica firma + idempotencia (delivery_id)
    A->>Q: process_webhook.delay(payload)
    Q->>DB: sync repo/PR/commit/release/check
    alt error recuperable
        Q->>Q: retry con backoff exponencial
    else fallo permanente
        Q->>DB: WebhookDelivery → DLQ
    end
```

## 6. ERD (dominios principales)

```mermaid
erDiagram
    User ||--o{ Task : owns
    User ||--o{ Project : owns
    User ||--o{ APIKey : has
    User ||--o{ UserPublicKey : has
    User ||--o{ SyncDevice : has
    Project ||--o{ Task : contains
    Project ||--o{ ProjectMember : has
    Team ||--o{ TeamMembership : has
    Task ||--o{ Subtask : checklist
    Task ||--o{ Comment : has
    Task ||--o{ Attachment : has
    Task ||--o{ TimeEntry : tracks
    Task ||--o{ TaskActivity : logs
    Task ||--o{ TaskRelation : outgoing
    Task ||--o| EncryptedTask : ciphertext
    Task }o--o{ Tag : tagged
    Task }o--|| Sprint : scheduled
    Task }o--|| Epic : groups
    Task ||--o{ TaskGitHubLink : links
    Sprint ||--o{ Task : contains
    AutomationRule ||--o{ AutomationLog : executes
    EncryptedTask ||--o{ EncryptedKeyShare : wraps
    SyncDevice ||--o{ SyncOperation : syncs
    Objective ||--o{ KeyResult : measures
```

## 7. Decisiones arquitectónicas (ADRs)

| # | Decisión | Contexto | Trade-off |
|---|---|---|---|
| 1 | Monolito modular | 17 apps, un proceso | Simplicidad de deploy vs acoplamiento; límites por app |
| 2 | JWT en cookies httpOnly | SPA + CSRF | Bearer para API clients; double-submit CSRF |
| 3 | SQLite en tests, Postgres en prod | Velocidad CI | Vendor-checks en código (FTS, índices) |
| 4 | E2E encryption opt-in | Feature flag | Server no indexa contenido cifrado (no FTS/IA sobre él) |
| 5 | Conflict resolution: server wins + client merge | Offline-first | Simplicidad; pierde writes intermedios |
| 6 | tasks como god-app | Dominio cohesionado | 15 modelos acoplados; candidato a split futuro |
| 7 | REST + GraphQL | Diversidad de clientes | Doble superficie: documentación/tests ×2 |
| 8 | Mutation testing por app | mutmut 3.x + fork | Orquestador propio, `-p no:django` |
| 9 | Idempotencia webhooks por delivery_id | GitHub retries | DLQ para fallos permanentes |
| 10 | `-p no:django` en mutmut | Fork-safety de pytest-django | Bootstrap manual en conftest |
