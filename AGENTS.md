# TODOlist - Guía de desarrollo

## Comandos

### Backend
```bash
cd backend
.venv\Scripts\activate
python manage.py runserver          # Desarrollo
python manage.py test               # Tests Django
python -m pytest tests/ -q          # Tests pytest (2220 tests: 1936 + 284 contract)
mutmut run                           # Mutation testing con mutmut 3.x
python manage.py generate_recurring # Generar tareas recurrentes manualmente
python manage.py makemigrations     # Crear migraciones
python manage.py migrate            # Aplicar migraciones
```

### Frontend
```bash
cd frontend
npm install
npm run dev                         # Desarrollo (Vite)
npm run build                       # Build producción
npx tsc --noEmit                    # Type check
npx vitest run                      # Tests (138 tests)
npx playwright test                 # E2E (requiere backend en :8000 y vite)
```

### E2E (Playwright)

`frontend/e2e/critical.spec.ts` cubre los 4 recorridos críticos (onboarding completo, búsqueda global, Mi trabajo, deep link + logout). Necesita el backend corriendo en `127.0.0.1:8000` — si no responde, los tests se saltan. El registro está limitado a 5/hora por IP; para corridas repetidas crear usuarios fijos por shell (`manage.py shell`) y exportar `E2E_EMAIL`/`E2E_PASSWORD` (compartido) y `E2E_FRESH_EMAIL`/`E2E_FRESH_PASSWORD` (sin proyectos, para el test de onboarding).

## Arquitectura

- **Backend**: Django 5 + DRF + Celery + Redis
- **Frontend**: React 18 + TypeScript + Vite + MUI + TanStack Query
- **50 modelos** en **14 apps** (con modelos) + 3 apps sin modelos (graphql_app, monitoring, social_auth)

## Decisiones de diseño recientes

- **Capa de servicio de tareas** (`apps/tasks/services.py`): `update_task`, `get_editable_task`, `apply_completion_effects`, `normalize_title`, `validate_state`, `validate_priority`, `parse_due_date`. Todos los canales (REST, GraphQL, GitHub sync, offline sync, bulk_update) comparten validación y efectos de `completed_at`/recurrencia — antes GraphQL y offline sync no seteaban `completed_at` (bug de paridad, corregido).
- **Dependencias con ciclos transitivos**: `TaskRelationSerializer.validate` bloquea ciclos de cualquier longitud sobre aristas normalizadas "depende de" (`depends_on` A→B, `blocks` B→A) + duplicados semánticos (`X depends_on Y ≡ Y blocks X`).
- **blocked vs is_blocked**: `state=blocked` es un flag manual de workflow; `is_blocked` (en `/dependencies/`) es derivado de relaciones BLOCKS/DEPENDS_ON abiertas. Son señales distintas y deliberadas.
- **iCal token**: `User.ical_token` opaco y rotatable (`POST/DELETE /api/users/me/calendar_token/`); el feed `calendar.ics` acepta `?token=` además de sesión — los clientes de calendario no pueden enviar JWT.
- **i18n frontend** (`frontend/src/i18n/`): recursos es/en repartidos en `batch*.ts` por dominio (`p.auth.*`, `p.task.*`, `p.shell.*`, `p.admin.*`, `p.board.*`, `p.collab.*`, `p.integr.*`, `p.misc.*`, `p.ops.*`, `p.plan.*`, `p.work.*`) mezclados en `index.ts`; comunes en el core (`common.*`, `nav.*`, `task.state.*`, `task.priority.*`). Comprobación: `node _check_i18n.mjs` — audita claves usadas vs definidas y dupes. En tests i18n se carga vía `setupFiles` (src/test/setup.ts).
- **E2E cifrado en cliente** (`lib/e2ee.ts` + EncryptionPage): RSA-OAEP-4096 por dispositivo envolviendo una clave AES-GCM simétrica; la privada solo vive en el dispositivo (backups cifrados con passphrase).
- **Recurrencia calendario real**: `next_due_date` usa `relativedelta` para monthly/yearly (timedelta de 30/365 días derivaba en meses cortos y bisiestos).
- **Auditoría de equipos**: `TeamViewSet` registra `create`/`update` (diff old/new)/`delete` en AuditLog.
- **Outbox transaccional** (`apps/events`): `OutboxEvent` persiste eventos de dominio en la transacción del cambio; `publish()` despacha síncrono, beat `process_outbox_events` (30s) reintenta FAILED (máx. 5 intentos). Los efectos externos (push WS, webhooks salientes) van por handlers registrados; los internos (TaskActivity, AuditLog, Notification) siguen síncronos en la transacción. Los webhooks salientes ahora sí se disparan en task.created/updated/deleted con HMAC + SSRF guard.
- **Organization (tenant raíz opcional)**: `Organization` + `OrganizationMembership` (roles owner/admin/member/guest) en collaboration; `Project.organization` opcional — owner/admin de org → escritura en todos sus proyectos, member → lectura, guest → nada implícito. Propagado a `accessible_projects` y `Task.objects.for_user`. CRUD en `/api/organizations/` con auditoría.
- **Workflows configurables**: `WorkflowTransition` por proyecto (`/api/workflow-transitions/`); si el proyecto define transiciones, solo esas aristas son válidas — enforcement en `task_service.update_task`, serializer REST y bulk_update. Sin transiciones → comportamiento libre (backward compat).
- **Offline sync merge por campo**: con `base_fields` en la operación, el conflicto se evalúa por campo (solo conflicta lo que ambos lados tocaron); sin `base_fields` sigue conflicto a nivel objeto.
- **Docs**: `docs/maturity.md` (matriz de madurez por feature), `docs/security/e2ee-threat-model.md` (cifrado cliente: qué protege y qué no).

## Operaciones limitadas por diseño

Algunos modelos no exponen CRUD completo intencionalmente. Esta tabla documenta qué operaciones están limitadas y por qué:

| Modelo | Operación ausente | Razón |
|---|---|---|
| TaskActivity | C/U/D | Solo lectura: registro automático de actividad vía signals |
| AuditLog | C/U/D | Solo lectura: registro automático de auditoría |
| Mention | C/U/D | Solo lectura: generada automáticamente al detectar @usuario en comentarios |
| Notification | C/D | Generada automáticamente por signals; solo marcar como leída |
| NotificationPreference | C/D | Auto-creada por usuario; solo edición de preferencias |
| AutomationLog | C/U/D | Solo lectura: registro automático de ejecuciones de automatización |
| KeyResultUpdate | U/D | Histórico inmutable: los registros de progreso no se editan ni eliminan |
| GitHubPullRequest | C/U/D | Solo lectura: sincronizados desde GitHub via webhooks y sync activo |
| GitHubCommit | C/U/D | Solo lectura: sincronizados desde GitHub via webhooks y sync activo |
| GitHubRelease | C/U/D | Solo lectura: sincronizados desde GitHub via webhooks y sync activo |
| GitHubCheckRun | C/U/D | Solo lectura: sincronizados desde GitHub via webhooks y sync activo |
| WebhookDelivery | C/U/D | Solo lectura: registro automático de entregas de webhooks |
| ChatMessageLog | C/U/D | Solo lectura: registro automático de mensajes enviados |
| AiSuggestion | C/U | Generada por IA; solo accept/reject/apply via action endpoint |

## Funcionalidades implementadas

- **RecurrenceRule**: Scheduler celery beat diario a las 6:00 AM + management command
- **Automation triggers**: TASK_CREATED, TASK_STATE_CHANGED, COMMENT_ADDED, SPRINT_CLOSED via signals
- **EncryptedTask**: FK OneToOne a Task + rotación de claves + gestión multi-dispositivo; cifrado real en cliente (`src/lib/e2ee.ts`: AES-256-GCM + RSA-OAEP wrap; self-share para recuperación; `GET /api/public-keys/lookup/?email=` para la pública del destinatario)
- **SyncOperation**: Detección de conflictos por versión (base_version vs current version)
- **SyncDevice**: Listado, revocación, campo is_active
- **GitHub sync activo**: Celery task cada 15 min sincroniza PRs, commits, releases, check runs
- **AiSuggestion**: accept/reject/apply con aplicación real a la tarea
- **Invitation**: Token seguro, expiración 7 días, validación de destinatario
- **Attachment**: Endpoint de descarga autorizado con Content-Disposition
- **Webhooks UI**: Separación visual de entrantes (GitHub) y salientes
- **Team CRUD**: Editar y eliminar equipos con confirmación
- **CustomFieldValue**: Editar y eliminar valores
- **Mentions**: Chip visual en TaskDialog cuando un comentario contiene @usuario
- **User account management**: Desactivar y eliminar propia cuenta con confirmación
- **SavedSearch edición**: Renombrar búsquedas guardadas desde la UI
- **ProjectMember edición/eliminación**: Cambiar rol y eliminar miembros de proyecto desde la UI
- **WebhookDelivery filtrado por usuario**: Las entregas de webhook se filtran por los repos del usuario autenticado
- **Automation SET_ASSIGNEE**: Asignar responsable a una tarea por ID o email
- **Automation ADD_TAG**: Añadir etiqueta a una tarea (crea si no existe)
- **Automation TASK_COMPLETED trigger**: Se dispara al pasar una tarea a estado completed
- **Automation TASK_BLOCKED trigger**: Se dispara al pasar una tarea a estado blocked
- **Automation SPRINT_STARTED trigger**: Se dispara al activar un sprint
- **Automation DAILY_CHECK trigger**: Se dispara al ejecutar run_daily_checks para usuarios con reglas habilitadas
- **Task.assignee**: Campo FK opcional a User para asignar responsables
- **SlaPolicy**: políticas SLA por prioridad (response_hours/resolution_hours) + escalado automático en run_daily_checks (bump de prioridad + notificación owner/assignee + tag sla-breached; primera respuesta: tareas aún `pending` pasado `response_hours` → tag sla-no-response + notificación única)
- **Notificación de asignación**: `notify_on_task_assigned` dispara también en reasignaciones (pre_save captura el assignee previo; `assignee == owner` nunca notifica)
- **Intake `assignee`**: el campo reservado se resuelve a User por email/username/id con acceso al proyecto; si no resuelve cae a la descripción (el dato no se pierde)
- **AiSuggestion.apply**: solo auto-aplica priority/story_points; `description_improvement` es orientativa y devuelve 400 (los consejos no se escriben en la tarea)
- **Feed iCal por token**: la UI (Importar/Exportar) puede generar/revocar la URL suscribible vía `POST/DELETE /api/users/me/calendar_token/`
- **Roadmap endpoint**: `GET /api/tasks/roadmap/` — épicas como lanes con rango temporal + progreso, sprints como milestones (página /app/roadmap)
- **Velocity endpoint**: `GET /api/tasks/velocity/` — puntos completados por sprint + estimado vs tiempo real (TimeEntry)
- **Gantt dependencies**: get_gantt_data incluye `dependencies` (TaskRelation) para flechas entre barras
- **GraphQL/REST parity**: mutations usan for_user(write=True), queries incluyen proyectos compartidos (accessible_projects)
- **E2E exclusion**: tareas vinculadas a EncryptedTask se excluyen de FTS search y de la IA (no hay plaintext que procesar)
- **Contract testing**: schemathesis sobre el schema OpenAPI (marker `contract`); postprocessing hook documenta 401/403/404/429
- **N+1**: get_queryset con select_related/prefetch completos; counts de Project/Sprint/Epic anotados con `annotate` (el serializer usa `*_count_ann` con fallback); tests de regresión N+1 en `test_nplus1.py`
- **Device revoke_all**: `POST /api/sync/devices/revoke_all/` — logout masivo de dispositivos (solo afecta a los propios)
- **OpenTelemetry**: `apps/monitoring/otel.py` — activar con `OTEL_ENABLED=1` + `OTEL_EXPORTER_OTLP_ENDPOINT` (traza HTTP→DB→Celery→requests)
- **Workload Management**: `GET /api/tasks/workload/` — carga por miembro (horas estimadas vs capacidad 40h/sem, % utilización, flag `over_allocated` >100%)
- **Métricas DORA**: `GET /api/metrics/dora/?days=N` — deployment frequency, lead time (mediana PR merge), change failure rate, MTTR (fallo→éxito check runs)
- **Wiki integrada**: `/api/wiki/` — app `wiki` con WikiPage jerárquica (parent), markdown, versionado; lectura para todos los miembros, escritura solo owner/editor
- **Activity feed global**: `GET /api/activity-feed/?limit=N` — feed unificado TaskActivity+AuditLog ordenado desc
- **Comment threading + reacciones**: `Comment.parent` (un nivel) + `POST /api/comments/{id}/react/` toggle emoji por usuario (JSONField reactions)
- **Automations SCHEDULED**: trigger `scheduled` con `schedule_hours` (intervalo); ejecutado por el beat horario, respeta `last_triggered_at`
- **Burnup chart**: `GET /api/tasks/burnup/?sprint_id=N` — completado acumulado vs scope (detecta scope creep, complementa burndown)
- **Vista Mi trabajo**: `GET /api/tasks/my-work/` — overdue/due_today/in_progress/blocked (con blocker)/upcoming del usuario
- **Búsqueda global con sintaxis**: `GET /api/tasks/global-search/?q=` — `assigned:me`, `status:open/closed`, `tag:`, `project:`, `priority:`, `type:`, `due:overdue/today/week`, `updated:Nd`, `"frase literal"`; busca también en comentarios, wiki y proyectos
- **Dependencias**: `GET /api/tasks/{id}/dependencies/` — is_blocked, blocked_by, blocks, related (relaciones BLOCKS/DEPENDS_ON abiertas)
- **iCal feed**: `GET /api/tasks/calendar.ics/` — deadlines como VEVENT suscribible (Google/Outlook/Apple)
- **Gestión de riesgos**: `/api/project-risks/` — ProjectRisk por proyecto (probability×impact→severity, mitigation, status); escritura solo owner/editor
- **Reuniones**: `/api/meetings/` — notes/decisions/attendees + `POST {id}/create_task/` convierte action items en tareas vinculadas
- **Formularios intake**: `/api/intake-forms/` — schema JSON de campos (text/number/date/select/checkbox, required) + `POST {id}/submit/` valida y crea la tarea con task_defaults
- **Dashboards personalizables**: `/api/dashboards/` — widgets JSON por usuario; `GET {id}/data/` resuelve 9 tipos (my_tasks, kpis, blocked, workload, velocity, prs_open, overdue, upcoming_deadlines, recent_activity). Compartición: `POST {id}/share/ {email}` / `unshare/` — lectura para el destinatario (`is_owner=false`, no puede editar/borrar/reshare); los datos se resuelven siempre con el scope de quien consulta
- **Load testing**: `loadtest/locustfile.py` — escenarios de lectura intensiva (tasks/kanban/dashboard/sync)
- **WebSocket real-time**: ws_signals emiten task.created/updated/deleted y notification.new/count a grupos `user_{id}_*`; auth JWT por cookie httpOnly (o `?token=` para clientes no-browser) en `config/ws_auth.py`; frontend `useRealtime` invalida caches de TanStack Query
- **Notification digest**: Celery task `send_daily_digests` (8:00 AM) agrupa notificaciones no leídas para usuarios con `digest_enabled`
- **Full-text search**: `TaskViewSet.search` usa PostgreSQL SearchVector/Rank (config spanish+english) con fallback icontains en SQLite
- **Recordatorios por tarea**: `Task.reminder_at` + beat `send_due_reminders` (60s) → notificación "reminder" una sola vez (`reminder_sent`)
- **Web push**: `PushSubscription` (endpoint+p256dh+auth) + `GET /api/push/vapid-key/`; `notify()` envía via pywebpush si `VAPID_PRIVATE_KEY` está configurada (404/410 purgan suscripciones); frontend registra `/push-sw.js` dedicado
- **Multi-asignación**: `Task.assignees` M2M (acceso de escritura + notificación de asignación); `Task.watchers` M2M (acceso de lectura + notificación en comentarios/cambios de estado vía `POST /tasks/{id}/watch|unwatch/`)
- **Timer en vivo**: `TimeEntry.is_running` + `POST /tasks/{id}/timer_start|timer_stop/` + `GET timer_status` — un solo timer por usuario (iniciar uno para el anterior)
- **Quick-add NLP**: `frontend/src/lib/quickAdd.ts` — parser ES/EN (fechas, prioridades p0-p5, #proyecto, @tag) alimenta la barra de TasksPage
- **Undo al borrar**: snackbar "Deshacer" recrea la tarea con snapshot de campos
- **Intake forms públicos**: `IntakeForm.public_token` + `POST /api/intake-forms/public/{token}/submit/` (AllowAny, throttle 20/h)
- **Enlaces de compartición**: `ShareLink` → `GET /api/public/share/{token}/` (AllowAny, throttle 60/h) read-only; frontend público `/share/:token` sin auth
- **Webhooks entrantes**: `InboundWebhook` → `POST /api/inbound/{token}/` crea tarea (conector genérico tipo Zapier/Make, throttle 60/h)
- **Email-to-task**: `User.inbound_email_token` + `POST /api/inbound-email/` (provider-agnostic SendGrid/Mailgun); `task-<token>@` crea tarea, asunto `[task-N]` + remitente propio crea comentario
- **Portafolios**: `Portfolio` agrupa proyectos (`/api/portfolios/`, `/app/portfolios`)
- **Plantillas de proyecto**: `ProjectTemplate` + `apply`/`from_project` → crea proyecto con tareas/tags/state labels
- **Etiquetas de estado por proyecto**: `ProjectStateLabel` renombra los 8 estados a nivel de vista (KanbanBoard consume `useStateLabels`)
- **Calendarios externos**: `ExternalCalendar` + beat `sync_external_calendars` (15min) parsea VEVENTs vía icalendar; overlay en CalendarView
- **Pizarras**: `Whiteboard` por proyecto (nodos/edges JSON), `/app/whiteboards` con drag & conectar
- **Adjuntos por enlace**: `Attachment.external_url` (Drive/Dropbox/etc.) sin fichero
- **Duplicar tarea**: `POST /tasks/{id}/duplicate/` — clona escalares + tags/assignees/checklist/custom-field values + hijos directos (nuevo id, owner=request.user, completed→pending); UI en TaskListItem y TaskDialog
- **Snooze de recordatorio**: `POST /tasks/{id}/snooze_reminder/` {minutes} — reprograma reminder_at y rearma reminder_sent; acción "Posponer" en NotificationsPage (15min/1h/mañana 9:00)
- **Productividad (karma)**: `GET /api/tasks/productivity/?days=N` — completadas/día (zero-fill) + racha actual + media + mejor día; página /app/productivity con gráfico (recharts)
- **Pomodoro / Enfoque**: `/app/focus` — temporizador 25/5 configurable (localStorage), vinculable a tarea abierta, contador de pomodoros y minutos de enfoque del día
- **Calendar drag-reschedule**: CalendarView con dnd-kit — arrastrar chip a un día PATCH due_date (conserva la hora; 18:00 si era todo el día); click sigue abriendo edición (distance 4px)
- **Salud de proyecto**: `Project.health` (on_track/at_risk/off_track) + `ProjectStatusUpdate` (histórico inmutable de updates con nota; crear uno sincroniza project.health); `/api/project-status-updates/`; badge en overview, dot en ProjectsPage, `latest_status_update` en serializer
- **Capacidad semanal configurable**: `User.weekly_capacity_hours` (default 40, PATCH /api/users/me/ y /api/auth/me/); workload usa el valor por miembro (antes 40h fijas); input en Perfil
- **KeyResult ↔ tareas**: `KeyResult.linked_tasks` M2M (write por PATCH con validación for_user) + `linked_progress` (% completadas) + `linked_tasks_detail`; UI en OkrsPage
- **Audit coverage**: signals post_save/post_delete en collaboration loguean `create`/`delete` de Task y Project en AuditLog (actor=owner; updates siguen en view-level como el patrón TeamViewSet)
- **SSO enterprise (OIDC)**: `allauth.socialaccount.providers.openid_connect` condicionado por `OIDC_ISSUER` (+`OIDC_PROVIDER_ID`/`OIDC_DISPLAY_NAME`/`OIDC_CLIENT_*`); `GET /api/sso/providers/` público lista providers habilitados con `login_url`; `SOCIALACCOUNT_LOGIN_ON_GET` + `LOGIN_REDIRECT_URL=/api/auth/social/jwt/?next=/app` hacen el post-login emitir cookies JWT y volver a la app (`social_jwt_callback` acepta `next` validado con `url_has_allowed_host_and_scheme`; sin `next` responde JSON como antes)
- **Videollamadas integradas**: `Meeting.video_room` + `POST /meetings/{id}/video/` (idempotente, genera slug `todolist-m{pk}-{token}`) y `close_video/`; `JITSI_BASE_URL` (default meet.jit.si, self-hostable); UI en MeetingsPage: Unirse/Copiar/Embeber (iframe allow camera+mic)/Finalizar
- **Marketplace de integraciones**: sección Catálogo en `/app/integrations` — grid de cards (GitHub, chat, webhooks, iCal, email-to-task, push, SSO, API keys, importadores) con estado Conectado/Disponible/No configurado y enlace de configuración
- **Apps nativas**: scaffold Capacitor (`frontend/capacitor.config.ts`, deps @capacitor/*, scripts `cap:sync/android/ios`); guía completa de requisitos en `docs/native-apps.md` (VITE_API_URL absoluta, CORS/cookies cross-site para orígenes capacitor://localhost y https://localhost)
- **Importadores**: Trello JSON y Todoist CSV en Importar/Exportar (parseo cliente + importación secuencial con progreso)
- **Aprobaciones de tarea**: `TaskApproval` (requester/approver/status/note/decision_note); `POST /tasks/{id}/request_approval|approve|reject/` — decide solo el approver del último pendiente (403), notify `approval_request`/`approval_decision` (tipos no listados en `Notification.Type`, patrón ya usado por `reminder`); TaskSerializer expone `approvals`, `pending_approval_for_me`, `logged_seconds` (annotate `logged_seconds_ann` con **Subquery correlacionada**, no `Sum` sobre el join — `for_user` hace fan-out); UI en TaskDialog + acciones inline en NotificationsPage
- **Formulario intake público (página)**: `GET /api/intake-forms/public/{token}/` devuelve `{name, description, schema, enabled}` (AllowAny, throttle 20/h); frontend standalone `/intake/:token` (`PublicIntakePage`, sin auth, fetch plano igual que `/share/:token`); `IntakeFormsPage.publicUrl` copia el enlace frontend, no el endpoint de submit
- **Out of office**: `User.out_of_office` + `out_of_office_until` (PATCH en `/auth/me/` y `/users/me/`); `ProjectMemberSerializer` expone `user_out_of_office*` (badge "OOO" en pickers de asignación/aprobadores); toggle + fecha en ProfilePage
- **Notificaciones por email**: `notify()` envía `send_mail` para tipos `task_assigned|mention|reminder` solo si `EMAIL_NOTIFICATIONS_ENABLED=1` (env) Y el usuario activó `email_enabled` por tipo en `NotificationPreference`; `fail_silently` + try/except (nunca rompe el in-app)
- **Automations: nuevas acciones**: `create_subtask` (checklist Subtask), `set_due_offset` ({days}, ±3650), `post_comment` (author=rule.owner||task.owner), `move_to_project` (valida `accessible_projects(write=True)`)
- **Paleta de comandos (Ctrl/Cmd+K)**: `CommandPalette` montado en AppLayout vía `useCommandPalette` hook; navegación rápida (~20 rutas) + búsqueda global en vivo (≥2 chars, mismo endpoint que SearchPage); `TaskDialog` muestra barra "registradas / estimadas" (`logged_seconds` vs `estimate_hours`)
- **Skeletons de carga**: `components/ui/skeletons.tsx` (TaskList/Kanban/CardGrid/Table/Dashboard/Page) reemplaza CircularProgress de página en TasksPage/Dashboard/MyWork/Projects/Notifications y en el fallback Suspense de rutas — los spinners quedan solo para cargas inline pequeñas
- **Menú contextual de tarea (clic derecho)**: `TaskContextMenu` en TaskListItem (compartido con KanbanBoard via `useContextMenu` de `ui/contextMenu.ts`): completar/reabrir, programar hoy/mañana, prioridad p0-p5 y estado con submenús anidados, duplicar, eliminar (mismo flujo confirm/undo que el menú "..."); quick-actions al hover en la fila (calendario→hoy, flag→ciclo prioridad) con reveal también por `:focus-within` para a11y
- **Columnas kanban colapsables**: chevron por columna → strip vertical de 44px (label rotado + count, sigue siendo droppable); persistido en `useUiStore.kanbanCollapsed` por `${projectId|global}:${state}`
- **Progreso de proyecto en cards**: `ProjectSerializer.completed_tasks_count` (annotate `Count(tasks, filter=Q(state="completed"))` en get_queryset, patrón `*_ann`); ProjectsPage muestra anillo determinate con % + "n de m completadas"
- **Cabecera "Hoy" en Mi trabajo**: PageHeader con fecha localizada ("Hoy · sábado 26 de septiembre") + subtítulo de atención
- **Orden manual en lista (drag & drop)**: `Task.position` + `POST /api/tasks/reorder/ {task_ids}` (posiciones secuenciales, solo write-access, 404 si alguna inaccesible); `ordering=position` es la opción "Manual" del selector de ordenación de TasksPage; `TaskRows reorderable` activa DndContext+SortableContext (handle GripVertical, sensors igual que KanbanBoard) solo ≤60 filas — por encima sigue el render virtualizado sin DnD
- **Transición de ruta**: `AppLayout` envuelve `<Outlet/>` en un `Box key={location.pathname}` con `keyframes` de Emotion (fade+slide 180ms ease-out); reduced-motion ya la neutraliza vía CssBaseline global
- **Secciones de proyecto**: `ProjectSection(project, name, order)` + `Task.section` (SET_NULL, validada same-project y write-access en `validate_section`); CRUD `/api/project-sections/` (list exige `?project=`) + `reorder/`; UI: agrupar por sección en lista (`?group=sections`, sin virtualizar), diálogo de gestión en TasksPage, selector en TaskDialog
- **Refs de tarea legibles**: `Project.issue_prefix` (auto-derivado de iniciales si vacío, editable) + `Task.seq` por proyecto (asignado en `perform_create`; backfill `tasks/0017` por created_at); serializer expone `ref` ("MP-42", fallback al id); se muestra en fila, tarjeta kanban y cabecera del diálogo
- **Rollover de sprint**: `POST /api/sprints/{id}/close/` acepta `move_incomplete_to` (sprint_id|"backlog"|null; `next_sprint_id` legacy sigue); terminales = completed/cancelled/archived; SprintsPage muestra diálogo con cuenta de incompletas y destino
- **Checklist de onboarding**: `OnboardingChecklist` en DashboardPage — 5 pasos (proyecto/tarea/tag auto-derivados de queries compartidas; paleta y kanban vía flags `uiStore.onboarding` marcados desde AppLayout/TasksPage); dismissible y persistido
- **Temas de acento**: `ACCENTS` en theme.ts (indigo/emerald/rose/amber/cyan) + `uiStore.accent` + `createAppTheme(dark, density, accent)`; selector de swatches en AccountPage
- **Shift+click selección**: `toggleSelect(id, shiftKey)` en TaskRows con `lastSelectedRef` — rango inclusivo sobre el orden visible
- **Rollover UI**: SprintsPage cierra con diálogo — cuenta de incompletas + destino (otro sprint / backlog / dejar); usa `sprintCloseApi.close` (`move_incomplete_to`), `sprintsApi.close` legacy sigue en resources.ts para otros usos
- **Backfill migraciones de datos**: `projects/0010` (issue_prefix derivado + desambiguación por owner), `tasks/0017` (seq por created_at), `tasks/0018` (position cronológico)
- **Endpoints rescatados**: `tasks/burnup` expuesto como toggle burndown/burnup en BurndownPage; `metrics/dora` y `tasks/audit_dashboard` registrados como widgets de dashboard (`WIDGET_TYPES` en resolver.py + render en DashboardsPage)
- **Email digest gated**: `send_daily_digests` respeta `EMAIL_NOTIFICATIONS_ENABLED` (early return)
- **Endpoints rescatados (ronda 2)**: `intake-submissions` ahora tiene visor en IntakeFormsPage (botón Envíos por formulario; serializer expone `submitted_by_email`/`task_title`, `?form=` filtra); `sync/devices` tiene sección "Dispositivos conectados" en SecurityPage (revoke/remove/revoke_all). El historial de KRs NO usaba `/kr-updates/` pero ya era visible vía `kr.updates` embebido — krUpdatesApi se dejó sin crear para no duplicar
- **i18n limpieza**: ~130 strings literales eliminadas de 12 páginas (Dashboard, Encryption, AppLayout nav, Sprints, Risks, Home, Trash, Dashboards, Projects); reutiliza claves existentes (common.*/nav.*/p.shell.*/p.plan.*/p.collab.*) y un barrido `_hc`-style está documentado como patrón; `TasksPage` resuelve el título por contexto (inbox → `nav.inbox`, sin proyecto → `p.taskx.palette.navTasks`)

- **Ayuda en producto**: `/app/help` (centro de ayuda con FAQ), `/app/changelog` (novedades), diálogo de atajos (Shift+? o menú «?» del toolbar)
- **Regresiones corregidas**: `DELETE /api/projects/{id}` con tareas daba 500 (post_delete de Task accedía a `task.project` ya borrado en cascade); CSP Trusted Types en `index.html` referenciaba una política `dompurify` nunca registrada → pantalla en blanco en Chromium (directiva eliminada hasta implementarla de verdad)

## Funcionalidades pendientes

- Ninguna pendiente. Todas las funcionalidades planificadas están implementadas y testadas.

## Permisos

- **Autenticación**: Todos los endpoints requieren `IsAuthenticated`. JWT en cookies httpOnly (`todolist_access`/`todolist_refresh`) + CSRF double-submit (`todolist_csrf`); header `Bearer` sigue disponible para clientes API
- **Filtrado por queryset**: La mayoría de ViewSets filtran por `owner=request.user` o `user=request.user` en `get_queryset()`
- **Autorización por objeto**: El filtrado del queryset protege list/retrieve/update/destroy en ViewSets estándar
- **Acciones personalizadas**: Validan ownership explícitamente (ver `AttachmentViewSet.download`, `InvitationViewSet.accept/decline`, `SuggestionActionView`)
- **Tests de seguridad horizontal**: 25 tests IDOR verifican que usuario B obtiene 404 en recursos ajenos

## Tests

- **Backend**: 2146 tests (1872 + 284 contract) en `backend/tests/` cubren auth, 2FA, tareas, proyectos, colaboración, automatizaciones, notificaciones, recurrencias, OKRs, integraciones, cifrado, offline sync, seguridad horizontal (IDOR), nuevas features (invitation expiry, encrypted task FK, key rotation, sync conflicts, attachment download, recurrence owner filtering), E2E/integración (OAuth GitHub mock, Slack mock, Discord mock, descarga real, user account management, saved search update, project member update/remove), gap fixes (webhook delivery user filtering, SET_ASSIGNEE/ADD_TAG actions, TASK_COMPLETED/TASK_BLOCKED/SPRINT_STARTED/DAILY_CHECK triggers), tests dirigidos de automatización (evaluate_conditions, execute_action, trigger_automation), tests de vistas de automatización (CRUD, test, logs), tests de servicios IA (estimate_priority, estimate_story_points, detect_blockers, improve_description), tests de vistas IA (suggestions, apply actions), tests GraphQL (queries y mutations), tests de vistas de tareas (filtros, bulk operations, relaciones), tests de modelos de tareas (subtask_progress, generate_next_occurrence, Epic.progress, TaskTemplate), tests de webhooks (idempotencia, reintentos, DLQ, eventos GitHub), tests de cliente GitHub (JWT, issues, PRs, OAuth, webhook signature), tests de sync GitHub (pull_requests, commits, releases, check_runs, sync_repo_data), tests de sync service (task_to_issue, issue_to_task, create_issue, import_issue), tests de vistas de integraciones (installations, repos, links, PRs, releases, OAuth, webhooks), tests de tareas Celery (sync_repo_issues, sync_all, webhook_retry), tests de offline sync (apply operations, conflict detection, get_changes_since, views), tests de auditoría (log_action, log_login, log_role_change), tests de menciones (extract_mentions, process_mentions), tests de modelos de usuario (APIKey, TwoFactorSecret), tests de cifrado (register_public_key, create_encrypted_task, add_key_share), tests de notificaciones (notify, mark_as_read, get_unread_count), tests de chat (send_slack_message, send_discord_message), tests de monitoreo (MetricsMiddleware, metrics_view)
- **Frontend**: 138 tests en `frontend/src/` cubren API resources, client (CSRF/tokenStorage/notify), useRealtime (WS), AuthContext, AppLayout, TaskDialog, KanbanBoard, TaskListItem, TaskTableView, NotificationBell, PwaInstallPrompt, LoginPage (incl. flujo 2FA), RegisterPage, OfflineSyncPage (push/pull/conflictos) ProjectsPage (CRUD + confirmación de borrado), MyWorkPage (agrupación por urgencia) y CommandPalette (búsqueda global)
- La suite puede emitir warnings de deprecación de dependencias (jwt, graphene); revisar al actualizar versiones

## Notas de seguridad de dependencias

- `pip-audit` reporta vulns residuales solo en tooling de tests: `pytest 8.4.2` (schemathesis exige `<9`), `starlette 0.52.1` (schemathesis exige `<1`), `setuptools` (versiones >=78 rompen distutils_hack en py3.11). Ninguna afecta al runtime (Django).
