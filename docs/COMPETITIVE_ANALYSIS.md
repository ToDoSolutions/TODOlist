# Análisis competitivo — TODOlist (2025–2026)

> Estado al momento del análisis. Precios anuales por asiento salvo indicación.

## 1. Qué es realmente TODOlist

Inventario funcional verificado en el código (74 modelos, ~80 páginas frontend):

| Dominio | Implementación |
|---|---|
| Tareas | 8 estados, P0–P5, recurrencia (relativedelta), checklist subtasks, parent tasks, dependencias con detección de ciclos transitivos, multi-assignee, watchers, tags, adjuntos, comentarios+threads+reacciones, custom fields, templates, approvals, bulk ops, undo, trash |
| Agile | Sprints, epics, velocity, burndown+burnup, backlog, roadmap, Gantt con dependencias, workflow transitions por proyecto, project state labels |
| Organización | Projects, Teams, Organizations (roles), Portfolios, ProjectTemplates, members por proyecto |
| Gestión | OKRs, riesgos por proyecto, reuniones+decisiones+action items, dashboards compartibles (9 tipos de widget), activity feed global, audit log |
| Automación | 10 triggers × 13 acciones, condiciones, SLA policies (response/resolution hours + escalado), reglas scheduled, anti-loop |
| Captura | Quick-add NLP propio ES/EN, intake forms públicos, inbound webhooks, email→task, share links públicos |
| Integraciones | GitHub (PRs, commits, releases, check runs, DORA metrics), Slack/Discord (saliente), iCal feed, calendarios externos, import/export |
| API | REST + GraphQL + WebSockets, API keys con scopes, OpenAPI |
| Plataforma | Offline sync (versionado + merge por campo), PWA + push, feature flags, i18n es/en, E2EE opcional por tarea (AES-256-GCM + RSA-OAEP-4096) |
| IA | `ai_assistant` = **heurísticas** (prioridad, story points, blockers, mejora de descripción) — no LLM |

## 2. Mapa del mercado

El mercado de PM software ≈ **$9.1B (2025) → $16.9B (2030)** (CAGR ~13%). Se divide en 5 segmentos; TODOlist compite en todos pero es nativo de dos:

| Segmento | Players | Precio típico | TODOlist |
|---|---|---|---|
| Tareas personales | Todoist, TickTick, MS To Do, Reminders | $0–8/mes | ✅ core fuerte |
| PM colaborativo | Asana, ClickUp, Monday, Notion, Trello | $5–25/user/mes | ⚠️ amplitud sí, polish no |
| Dev/agile | Jira, Linear, Plane, Height | $7–16/user/mes | ⚠️ parcial |
| Daily planning | Motion, Sunsama, Reclaim, Akiflow | $10–35/mes | ❌ sin auto-scheduling |
| Self-hosted/OSS | Plane, OpenProject, Vikunja, Leantime, Wekan | $0 + open-core | ✅ nativo |

## 3. Comparativa profunda por segmento

### 3.1 vs Todoist/TickTick (tareas personales)

| Eje | TODOlist | Todoist | TickTick |
|---|---|---|---|
| Quick-add NLP | Regex ES/EN: fechas, p0-5, !prio, #proj, @tag | NLP maduro 19 idiomas + **Ramble** voz (38 idiomas) | NLP propio, fuerte en EN/ZH |
| Recurrencia | ✅ RecurrenceRule + relativedelta | ✅ NLP recurrente complejo | ✅ |
| Límites artificiales | Ninguno | 300 tareas/proyecto, 4 niveles subtask | 999 tareas/lista paid |
| Extras personales | TimeEntry+timer, FocusPage | Karma gamificación | **Hábitos, Pomodoro, Eisenhower** |
| Calendario | iCal feed (export) + Gantt | Sync bidireccional Google/Outlook (paid) | Bidireccional Google, suscripción CalDAV |
| Offline | ✅ merge por campo | Sync engine local-first | ✅ |
| Precio | Gratis (self-host) | Pro $5/mes (subió dic-2025) | Premium $3/mes |
| Apps nativas | ❌ PWA | ✅ widgets, Siri, watch | ✅ widgets completos |

**Veredicto**: gana en límites y profundidad de datos; pierde en NLP real, móvil y calendario bidireccional.

### 3.2 vs Linear/Jira (dev/agile)

| Eje | TODOlist | Linear | Jira |
|---|---|---|---|
| Modelo ágil | Sprints manuales, epics | **Cycles auto-generados + auto-rollover + cooldown** | Sprints manuales, Plans (Premium) |
| Triage | Intake forms públicos | **Triage inbox + rules + IA de routing** | Workflows custom máximos |
| SLA | ✅ SlaPolicy + escalado | ✅ Issue SLAs (Business+) | Solo en JSM |
| GitHub | ✅ sync PRs/commits/releases/checks + DORA | ✅ sync issues **bidireccional** + Diffs (review nativa) | Dev info panel (commits/PRs vinculados, no sync) |
| Métricas | velocity, burndown, DORA | Insights en tiempo real | Insights + marketplace |
| API | REST+GraphQL+WS | GraphQL pública + Agents API | REST v3 + JQL |
| Precio | Gratis | $10–16/user (subida ene-2026) | $7.91–14.54/user |

**Veredicto**: sorprendentemente cerca de Linear en modelo (sprints, SLA, DORA, intake), pero Linear gana en sync engine, triage IA, y bidireccionalidad GitHub. Contra Jira, TODOlist es más simple y rápido de operar — ventaja real para equipos pequeños.

### 3.3 vs Asana/ClickUp/Monday (work management)

| Eje | TODOlist | Asana | ClickUp | Monday |
|---|---|---|---|---|
| Jerarquía | Org→Portfolio→Project→Epic→Task→Subtask | Workspace→Team→Project→Task (1 nivel subtask) | Space→Folder→List→Task (7 niveles) | Board→Group→Item→Subitem |
| Multi-homing | ❌ una tarea = un proyecto | ✅ nativo (diferenciador clave) | ✅ "tasks in multiple lists" | ⚠️ connect boards |
| Goals/OKR | ✅ app okrs | ✅ Goals (Advanced+, maduros) | ✅ Goals básicos | ⚠️ débil |
| Vistas | ~10 (list, board, Gantt, roadmap, calendar…, whiteboards) | 5 nativas | **15+** | 27+ board views |
| Automaciones | 10×13, SLA, scheduled — sin límite | Ilimitadas (desde may-2025) | 100–250K/mes según plan | 250–250K/mes (desde Standard) |
| Time tracking | ✅ nativo gratis | Advanced+ ($24.99) | ✅ nativo | Pro+ ($19) |
| Automations IA | ❌ | AI Studio (créditos) + AI Teammates | Brain $9–28/user | AI Blocks (créditos) |
| Precio | Gratis | $10.99–24.99 | $7–12 | $9–19 |

**Veredicto**: en features brutas TODOlist cubre ~80% de lo que un equipo no-enterprise usa de Asana/ClickUp, incluyendo lo que ellos paywalleán (time tracking, goals, forms, automaciones ilimitadas). Pierde en multi-homing, polish, ecosistema y gobernanza enterprise (SSO/SCIM, data residency).

### 3.4 vs self-hosted/OSS (su segmento nativo)

| | TODOlist | Plane (60k★) | OpenProject (16k★) | Vikunja | Leantime | Wekan |
|---|---|---|---|---|---|---|
| Stack | Django+React | Django+Next.js | Rails+Angular | Go+Vue | PHP | Meteor |
| Licencia | — (verificar) | AGPL CE + Commercial cerrado | GPLv3 | AGPLv3 | AGPLv3 | MIT |
| Sprints/cycles | ✅ | ✅ cycles | ✅ boards | ❌ | ⚠️ | ❌ |
| Recurrencia | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Time tracking | ✅ gratis | ❌ | ✅ | ⚠️ solo Pro | ✅ | ❌ |
| OKR/goals | ✅ | ❌ | ⚠️ | ❌ | ✅ | ❌ |
| Wiki/docs | ✅ | ✅ Pages | ✅ | ❌ | ✅ | ❌ |
| Automatizaciones | ✅ + SLA | ⚠️ | ⚠️ | ❌ | ⚠️ plugins | ⚠️ reglas |
| CalDAV | ❌ (iCal feed) | ❌ | ❌ | ✅ | ❌ | ❌ |
| E2EE | ✅ opcional | ❌ | ❌ | ❌ | ❌ | ❌ |
| Intake público | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| API | REST+GraphQL+WS | REST | REST+webhooks | REST | API+plugins | REST |

**Veredicto del segmento**: TODOlist es **el OSS self-hosted con mayor amplitud funcional** — ninguno combina sprints + recurrencia + OKR + wiki + intake + SLA + offline sync + E2EE. Plane gana en comunidad/tracción y UX pulida; OpenProject en PM enterprise tradicional (presupuestos, BIM, LDAP); Vikunja en simplicidad+CalDAV.

### 3.5 vs daily planners / notas

- **Motion/Reclaim/Sunsama/Akiflow ($15–35/mes)**: auto-scheduling (constraint solver sobre calendario) y rituals de planificación — TODOlist no tiene nada equivalente. Es el único dominio funcional realmente ausente.
- **Notion/Trello/Obsidian**: flexibilidad/ecosistema vs estructura. TODOlist es más opinionado y con mejor modelo de tareas, pero sin extensibilidad de plugins ni marketplace.
- **E2EE en notas** (Standard Notes, Notesnook, Joplin): validan que hay willingness-to-pay ~$5–10/mes por privacidad, sin que ninguno gestione trabajo de verdad.

## 4. El hueco de mercado verificado

**Nadie combina: tareas + proyectos + OKR + wiki + automatizaciones + offline + E2EE + self-hosted.**

- E2EE en PM mainstream: **cero** (Todoist/Asana/ClickUp/Linear = AES-256 at rest solo).
- E2EE en OSS: solo experimentos de 1–2 devs (MSKanban, re/task, SealTask, TaskFlow) — todos inmaduros, ninguno con gestión de proyectos real.
- Los self-hosted maduros (Plane, OpenProject, Vikunja) no cifran nada en cliente.
- Señales de mercado: Proton compró Standard Notes (2024); 82% de vendors enterprise soportan self-hosted; ~46% de self-hosters citan privacidad/independencia/control como motivación; Jira Data Center EOL mar-2029 empuja migraciones.

## 5. Debilidades competitivas reales de TODOlist

Ordenadas por impacto para adopción:

1. **Sin apps móviles nativas** — PWA + scaffold RN/Capacitor incoherente. En tareas personales esto es casi blocker (Todoist/TickTick ganan por widgets, share sheet, recordatorios nativos).
2. **Sin CalDAV bidireccional** — solo iCal feed export. Vikunja ya lo hace; es la ventana más fácil de cerrar.
3. **IA = heurísticas, no LLM** — `ai_assistant` es scoring por reglas; competidores tienen agentes, triage semántica, auto-scheduling. Oportunidad: BYOK/LLM local como diferenciador privado.
4. **Sin MCP server** — en 2026 todos los grandes exponen MCP (Notion, Linear, Asana, Atlassian, ClickUp). Un MCP server propio es barato de construir sobre la API REST existente y es expectativa de la categoría.
5. **Una tarea = un proyecto** — sin multi-homing (diferenciador Asana/ClickUp).
6. **Ecosistema de integraciones** — ~6 conectores vs 80–300.
7. **Sin marketplace/plugins** — ni siquiera registro de custom actions en automatizaciones.
8. **Comunidad/tracción** — 0★ vs 60k de Plane; sin hosted cloud de referencia.
9. **Enterprise readiness** — sin SSO/SAML/SCIM/LDAP, sin audit-log export a SIEM, sin data residency story.

> **Estado post-implementación (2026-09):**
>
> 1. Móvil: unificado en Capacitor sobre el PWA (scaffold RN retirado).
> 2. CalDAV/VTODO: server propio (`apps/caldav`) — bidireccional.
> 3. IA: BYOK OpenAI-compatible opcional (las heurísticas siguen de base).
> 4. MCP: `POST /api/mcp/` JSON-RPC con API keys + scopes.
> 5. Multi-homing: `Task.extra_projects` — canónico autoritativo para
>    sprint/epic/section/seq/workflow; borrar un proyecto re-homea las
>    tareas multi-homeadas en vez de borrarlas.
> 6. Integraciones: n8n node, webhooks entrantes/salientes (HMAC+SSRF),
>    email-to-task, acción `call_webhook` en automatizaciones.
> 7. Extensibilidad: catálogo público de plantillas de proyecto
>    (community templates) + `call_webhook` como punto de extensión.
> 8. Enterprise: SSO vía OIDC genérico (`OIDC_ISSUER` — Keycloak,
>    EntraID, Okta), audit-log export CSV/JSONL a SIEM, auditoría de
>    equipos/proyectos. **Implementado**: SAML nativo (allauth saml provider), SCIM 2.0 (/scim/v2, Users+Groups a Organizations) y enforcement de SSO por dominio. **Pendiente**: LDAP directo, data residency.

## 6. Ventajas defendibles

1. **E2EE opcional por tarea** — único en su clase, arquitectura ya construida (EncryptedTask + key shares).
2. **Amplitud con coherencia** — service layer compartida entre REST/GraphQL/sync/automatizaciones (muchos competidores OSS tienen paridad rota entre APIs).
3. **Offline sync con merge por campo** — más fino que el conflicto a nivel objeto típico.
4. **SLA nativo** — solo Linear Business y JSM lo tienen; ningún OSS.
5. **Todo el feature set de pago de otros, gratis**: time tracking, goals, forms, automaciones ilimitadas, dashboards.

## 7. Estrategia recomendada

**Posicionamiento**: *"El work management open-source con E2EE"* — no competir frontal con Todoist (móvil/NLP) ni Asana (enterprise), sino ocupar el hueco self-hosted+privado donde hoy solo hay Plane (sin E2EE, sin recurrencia, sin OKR, sin time tracking en CE) y Vikunja (sin PM serio).

**Prioridades de alto ROI**:

| Prioridad | Acción | Por qué |
|---|---|---|
| 1 | E2EE usable en flujo normal (hoy es solo una página de gestión) | Convierte el moat teórico en real |
| 2 | CalDAV server (VTodo) | Solo Vikunja lo tiene en OSS; cierra el gap de calendario |
| 3 | MCP server sobre la API | Estándar 2026, coste bajo, abre el ecosistema de agentes |
| 4 | LLM opcional BYOK en ai_assistant | IA sin renunciar a privacidad = diferenciador del hueco |
| 5 | Licencia clara (AGPLv3) + README en inglés | Requisito para tracción OSS (Plane lo hizo así) |
| 6 | Mobile: elegir UN camino (Capacitor sobre el PWA existente) | Mata la inconsistencia RN+Capacitor |
| 7 | Demo cloud + `docker compose up` en 2 min | Conversión OSS = fricción de instalación |
| 8 | Auto-scheduling simple (daily plan, drag tasks→slots de FocusPage) | Aproxima el segmento $15–35/mes sin solver completo |

**Monetización si algún día se busca** (benchmark open-core validado por Plane/Cal.com/Infisical): CE self-host AGPL gratis + cloud $6–9/seat + Enterprise (SSO/SCIM/audit) — el hueco privado soporta prima.

## 8. Resumen ejecutivo

TODOlist no compite como producto comercial contra Todoist/Asana — les faltan años de UX, móvil y ecosistema. Pero en su segmento nativo (**OSS self-hosted**) tiene **la mayor amplitud funcional del panorama** y un diferenciador que nadie más tiene maduro: **E2EE**. El gap principal no es de features sino de packaging: licencia, tracción, móvil, MCP e IA conectable. Con esas piezas, ocupa un hueco de mercado real y verificado.
