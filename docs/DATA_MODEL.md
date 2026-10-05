# Modelo de datos

PostgreSQL es la fuente de verdad (SQLite en dev). ~50 modelos en
14 apps Django. La PWA cachea en IndexedDB y drena su cola
(`SyncOperation`) al reconectar. Migraciones Django por app;
GraphQL deriva de los mismos modelos con paridad REST (ADR-004).

## Núcleo de trabajo

| Entidad | Campos clave | Notas |
|---|---|---|
| `User` | username, email, `ical_token`, `inbound_email_token` | tokens opacos rotatables por endpoint |
| `Organization`/`OrganizationMembership` | roles owner/admin/member/guest | tenant raíz opcional; propaga a `accessible_projects` |
| `Project` | name, color, owner, organization, is_favorite | `ProjectStateLabel` renombra estados por proyecto |
| `ProjectMember`/`Invitation` | role; token + expiración 7d | invitación valida destinatario |
| `Task` | title, project, state, priority, due_date, position, `assignee` FK + `assignees` M2M, `watchers` M2M, `reminder_at` | `completed_at` por la capa de servicio (`services.py`) compartida por todos los canales |
| `TaskRelation` | BLOCKS/DEPENDS_ON | ciclos transitivos bloqueados en serializer |
| `RecurrenceRule` | `next_due_date` con `relativedelta` | beat diario 6:00 + management command |
| `Tag`, `Comment` (+`parent`, `reactions`), `Attachment` | | descarga de adjuntos autorizada |
| `CustomFieldValue` | por proyecto | edición/eliminación desde UI |

## Planificación

| Entidad | Campos clave | Notas |
|---|---|---|
| `Sprint` | start/end, state | burndown + burnup por endpoint; cierre con traspaso |
| `Objective`/`KeyResult`/`KeyResultUpdate` | OKRs | updates históricos inmutables (sin U/D) |
| `Epic`, `TimeEntry` | `is_running` | un solo timer vivo por usuario |
| `Meeting` | notes/decisions/attendees | action items → `create_task` |
| `ProjectRisk` | probability×impact→severity | escritura owner/editor |
| `Portfolio`, `ProjectTemplate` | | `apply`/`from_project` crea proyecto completo |
| `WorkflowTransition` | aristas válidas por proyecto | enforcement en service + REST + bulk |
| `Dashboard` | widgets JSON, share por email | datos siempre resueltos con el scope del lector |

## Colaboración

| Entidad | Campos clave | Notas |
|---|---|---|
| `Team`/`TeamMembership` | name, role | CRUD auditado (diff old/new) |
| `Mention` | auto-generada al detectar `@user` | solo lectura |
| `Notification`/`NotificationPreference` | type, read_at | digest diario por beat; preferencias por usuario |
| `WikiPage` | parent (jerárquico), markdown, versionado | lectura miembros, escritura owner/editor |
| `TaskActivity` | signal automática | append-only |
| `AuditLog` | actor, action, resource, diff | append-only, consultable admin |

## Automatización e integraciones

| Entidad | Campos clave | Notas |
|---|---|---|
| `AutomationRule`/`AutomationLog` | trigger (created/state/comment/sprint/scheduled/daily), action (set_assignee/add_tag/…) | SLA: `SlaPolicy` por prioridad con escalado |
| `OutboundWebhook`/`WebhookDelivery` | HMAC + SSRF guard; deliveries read-only | disparado vía outbox |
| `InboundWebhook`, `IntakeForm` (+`public_token`) | crea tareas; throttle 60/h y 20/h | conector genérico + formularios públicos |
| `GitHubPullRequest/Commit/Release/CheckRun` | sync activo cada 15 min + webhook | read-only (vienen de GitHub) |
| `ChatIntegration`, `SavedSearch`, `FeatureFlag` | | |
| `AiSuggestion` | accept/reject/apply | solo auto-aplica priority/story_points |
| `ShareLink` | token, read-only, throttle 60/h | público `/share/:token` |
| `PushSubscription` | p256dh+auth | web push si `VAPID_PRIVATE_KEY` |

## Offline sync y E2EE

| Entidad | Campos clave | Notas |
|---|---|---|
| `SyncOperation` | `base_version` vs current; `base_fields` para merge por campo | conflicto por campo si hay base, por objeto si no |
| `SyncDevice` | is_active, revocación individual/`revoke_all` | |
| `EncryptedTask` | OneToOne a Task; blob AES-256-GCM envuelto por RSA-OAEP-4096 por dispositivo | el servidor nunca ve plaintext ni claves — excluidas de FTS e IA por diseño |
| `OutboxEvent` | eventos de dominio en-txn; beat reintenta FAILED ×5 | ADR-002 |

## Convenciones

- Registros automáticos (`AuditLog`, `TaskActivity`, `Mention`,
  `AutomationLog`, `WebhookDelivery`, `KeyResultUpdate`, feeds de
  GitHub) son **solo lectura por API** — tabla completa en AGENTS.md.
- Optimistic locking por versión en entidades de trabajo.
- `AuditLog` es append-only y alimenta también el activity feed.
