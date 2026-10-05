# Matriz de madurez funcional

Niveles:

| Nivel | Significado |
|---|---|
| 0 | Modelo creado |
| 1 | API implementada |
| 2 | Permisos y validaciones completas |
| 3 | Interfaz funcional |
| 4 | Tests unitarios + integración |
| 5 | Tests E2E / contrato + observabilidad |
| 6 | Demostrable en producción |

Solo se presenta como "feature principal" lo que llega a **nivel ≥5**.

| Feature | Nivel | Canal completo | Notas |
|---|---|---|---|
| Task CRUD + filtros | 6 | REST+GQL+UI | Suite completa, N+1 testeado |
| Kanban / tabla / calendario / Gantt / roadmap | 5 | UI+REST | Gantt incluye dependencias |
| Sprints + burndown/burnup/velocity | 5 | REST+UI | |
| Épicas | 5 | REST+UI | |
| Subtareas + comentarios + reacciones + menciones | 5 | REST+UI | Threading 1 nivel |
| Relaciones/dependencias (blocks/depends_on) | 5 | REST | Ciclos transitivos bloqueados |
| Recurrencia | 5 | REST+Celery | Meses/años calendario reales |
| Búsqueda global con sintaxis | 5 | REST+UI | FTS Postgres + fallback |
| iCal feed | 5 | REST | Token opaco rotatable (no cookies) |
| Time tracking | 4 | REST+UI | |
| Custom fields | 4 | REST+UI | Valores versionables pendiente |
| Attachments | 5 | REST | Descarga autorizada |
| SavedSearch | 5 | REST+UI | |
| Teams + roles | 5 | REST+UI | Audit completo (create/update/delete) |
| ProjectMember + invitations | 5 | REST | Expiración 7d |
| AuditLog | 4 | REST | Read-only; cobertura de acciones aún parcial (solo teams) |
| Meetings + action items → tasks | 4 | REST | |
| Wiki (markdown+versionado) | 5 | REST+UI | Permisos owner/editor |
| OKRs | 4 | REST+UI | KeyResultUpdate inmutable |
| Project risks | 4 | REST | |
| Intake forms → tasks | 4 | REST | |
| Dashboards personalizables | 4 | REST+UI | |
| Automatizaciones | 5 | REST+Celery | Antibucle por profundidad; sin detección estática de ciclos |
| SLA policies | 4 | Celery | Escalado automático |
| Notificaciones + digest | 5 | WS+Celery | |
| WebSockets real-time | 5 | WS | Auth por cookie/?.token; push vía outbox transaccional |
| Offline sync + conflictos | 5 | REST+PWA | Versión + **merge por campo** (base_fields); completed_at consistente |
| Outbox transaccional | 5 | Celery beat | Eventos durables + handlers idempotentes + reintentos |
| Organizations (tenant) | 4 | REST | Propagación de roles a proyectos/tareas; sin billing/limits |
| Workflows por proyecto | 5 | REST+GQL+bulk | Transiciones permitidas; enforcement en todos los canales |
| API keys + scopes + rotación | 5 | REST | |
| 2FA TOTP + backup codes | 5 | REST | |
| Cifrado cliente (EncryptedTask) | 4 | REST | Ver `docs/security/e2ee-threat-model.md` — sin verificación de claves |
| GitHub sync (webhooks+polling) | 5 | REST+Celery | Idempotente, DLQ, HMAC |
| Slack/Discord webhooks | 4 | REST | |
| GraphQL | 4 | GQL | Paridad de update_task verificada; cobertura de mutaciones parcial |
| DORA metrics | 3 | REST | Depende de datos GitHub; definiciones a documentar |
| Workload (40h) | 3 | REST | Capacidad fija; jornada configurable pendiente |
| IA (sugerencias+apply) | 4 | REST | accept/reject/apply; diff + source_version pendiente |
| Feature flags | 4 | REST | |
| Load testing | 4 | Locust | |
| Contract testing (schemathesis) | 5 | OpenAPI | Marker `contract` |
| OTEL/Prometheus | 4 | - | Opcional por env |

## Gaps conocidos (trabajo pendiente real)

1. ~~Outbox transaccional~~ — **implementado** (`apps/events`): eventos
   durables + dispatch + reintentos para efectos externos (WS, webhooks).
   Pendiente: migrar automatizaciones y notificaciones al bus si se quiere
   dispatch asíncrono completo (hoy siguen síncronos por diseño).
2. ~~Tenant explícito~~ — **implementado**: `Organization` +
   `OrganizationMembership` + `Project.organization` con propagación de
   roles a `accessible_projects`/`for_user`.
3. ~~Workflows configurables~~ — **implementado**: `WorkflowTransition` por
   proyecto; enforcement en todos los canales (REST, GraphQL, bulk, sync).
   Pendiente (fase 2): estados con nombre propio por proyecto.
4. **`state=blocked` vs `is_blocked` derivado**: dos señales distintas —
   `blocked` es flag manual de workflow; `is_blocked` se deriva de relaciones
   abiertas. Documentado, no unificado.
5. ~~Merge por campo en offline~~ — **implementado**: `base_fields` en la
   operación permite merge cuando servidor y cliente tocan campos distintos;
   conflicto real solo en el mismo campo.
6. **Adjuntos**: magic bytes + extensiones bloqueadas + tamaño máx +
   filename sanitizado ya existen. Pendiente: antivirus y cuotas por usuario.
7. **Auditoría**: cubre auth + teams + organizations; updates/deletes de
   otras entidades aún no (extender `log_update`/`log_delete` a projects/tasks).
8. **SSRF residual**: `_is_safe_url` valida DNS en el momento del check; no
   pinna la IP al connect (DNS rebinding teórico). Mitigar requiere adapter
   custom de requests.
9. **Sesiones**: no hay registro de refresh-token families para detección de
   reutilización (logout-all existe vía device revoke).
