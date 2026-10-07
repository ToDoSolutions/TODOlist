<h1 align="center">TODOlist</h1>

<p align="center">
  <strong>Self-hosted, open-source work management (AGPLv3)</strong><br>
  Tasks, projects, sprints, OKRs, wiki, SLA automations,<br>
  offline sync with field-level conflict merge, and optional client-side E2EE.
</p>

<p align="center">
  <a href="https://github.com/ToDoSolutions/TODOlist/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/ToDoSolutions/TODOlist/ci.yml?branch=main&label=CI" alt="CI">
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/ToDoSolutions/TODOlist" alt="AGPLv3 license">
  </a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/node-20%2B-blue" alt="Node 20+">
</p>

<p align="center">
  <a href="./README.md">Español</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="./docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="./CONTRIBUTING.md">Contributing</a> ·
  <a href="./SECURITY.md">Security</a>
</p>

<p align="center">
  <img src="docs/assets/screenshots/kanban.png" alt="Kanban board with state columns, cards showing priority, tags, story points and due date" width="900">
</p>
<table align="center">
<tr>
  <td><img src="docs/assets/screenshots/dashboard.png" alt="Dashboard with KPIs: open, completed, overdue, blocked tasks; flow metrics and backlog health" width="420"></td>
  <td><img src="docs/assets/screenshots/tasks-list.png" alt="Task list with quick-add, state and priority filters, and saved searches" width="420"></td>
  <td><img src="docs/assets/screenshots/sprints.png" alt="Sprints with active/planned/closed status, date ranges and assigned tasks" width="420"></td>
</tr>
<tr>
  <td><img src="docs/assets/screenshots/calendar.png" alt="Monthly calendar with tasks colored by state on their due dates" width="420"></td>
  <td><img src="docs/assets/screenshots/task-detail.png" alt="Task editor with subtasks, dependencies, attachments, properties and timer" width="420"></td>
  <td><img src="docs/assets/screenshots/gantt.png" alt="Gantt chart with state-colored task bars grouped by project, plus sprints" width="420"></td>
</tr>
<tr>
  <td><img src="docs/assets/screenshots/my-work.png" alt="My Work: inbox with overdue, due today, blocked, in progress and next 7 days" width="420"></td>
  <td><img src="docs/assets/screenshots/automations.png" alt="Automation rules with trigger and action, toggleable, with run counters" width="420"></td>
  <td><img src="docs/assets/screenshots/projects.png" alt="Projects as cards with task, sprint and epic counters" width="420"></td>
</tr>
</table>
<p align="center"><sub>Dashboard · Tasks · Sprints · Calendar · Task detail · Gantt · My Work · Automations · Projects</sub></p>

<details>
<summary>All screenshots — 82 screens grouped by domain</summary>

### Home and inboxes

| Home | Inbox |
|---|---|
| ![Home: today's KPIs, recent projects, active sprint and recent activity](docs/assets/screenshots/app-home.png) | ![Inbox: captured tasks pending triage](docs/assets/screenshots/inbox.png) |

| Attention inbox | Focus |
|---|---|
| ![Attention inbox: invitations, mentions, conflicts and actionable alerts](docs/assets/screenshots/attention.png) | ![Focus: Pomodoro timer linkable to a task](docs/assets/screenshots/focus.png) |

| Productivity | |
|---|---|
| ![Productivity: personal focus and completed-task metrics](docs/assets/screenshots/productivity.png) | |

### Tasks and views

| Editable table | Dependencies |
|---|---|
| ![Table view with inline editing and configurable columns](docs/assets/screenshots/tasks-table.png) | ![Task dependencies: blocks and is blocked by](docs/assets/screenshots/dependencies.png) |

| Custom fields | Tags |
|---|---|
| ![Custom fields per project](docs/assets/screenshots/custom-fields.png) | ![Tag management with color and usage counter](docs/assets/screenshots/tags.png) |

| Favorites | Completed |
|---|---|
| ![Favorites: quick access to starred tasks](docs/assets/screenshots/favorites.png) | ![Completed: closed-task archive](docs/assets/screenshots/completed.png) |

| Trash | Backlog |
|---|---|
| ![Trash: restore or permanent deletion](docs/assets/screenshots/trash.png) | ![Project backlog sortable by priority](docs/assets/screenshots/backlog.png) |

| Recurrence rules | Time entries |
|---|---|
| ![Recurrence rules: frequency and next occurrence](docs/assets/screenshots/recurrence-rules.png) | ![Time entries with live per-task timer](docs/assets/screenshots/time-entries.png) |

| Import / export | |
|---|---|
| ![Import and export: CSV, JSON and tokenized iCal feed](docs/assets/screenshots/import-export.png) | |

### Project and planning

| Project | Project tasks |
|---|---|
| ![Project view: summary, progress and view shortcuts](docs/assets/screenshots/project.png) | ![Task list inside the project](docs/assets/screenshots/project-tasks.png) |

| Project settings | Risks |
|---|---|
| ![Project settings: members, state labels and template](docs/assets/screenshots/project-settings.png) | ![Risk register: probability × impact, mitigation and status](docs/assets/screenshots/risks.png) |

| Portfolios | Templates |
|---|---|
| ![Portfolios grouping related projects](docs/assets/screenshots/portfolios.png) | ![Project templates applicable with tasks and tags](docs/assets/screenshots/templates.png) |

| Epics | Roadmap |
|---|---|
| ![Epics with progress and associated tasks](docs/assets/screenshots/epics.png) | ![Roadmap: epics as time lanes and sprints as milestones](docs/assets/screenshots/roadmap.png) |

| Burndown | Capacity |
|---|---|
| ![Sprint burndown with ideal remaining-work line](docs/assets/screenshots/burndown.png) | ![Team capacity: estimated hours vs weekly capacity](docs/assets/screenshots/capacity.png) |

| Dashboards | OKRs |
|---|---|
| ![Customizable dashboards with KPI widgets and charts](docs/assets/screenshots/dashboards.png) | ![OKRs with key results and progress history](docs/assets/screenshots/okrs.png) |

| Decisions | Meetings |
|---|---|
| ![Recorded decisions with context and owner](docs/assets/screenshots/decisions.png) | ![Meetings: notes, attendees and action items convertible to tasks](docs/assets/screenshots/meetings.png) |

| Whiteboards | Wiki |
|---|---|
| ![Collaborative per-project whiteboards](docs/assets/screenshots/whiteboards.png) | ![Wiki with page hierarchy, markdown and versioning](docs/assets/screenshots/wiki.png) |

| Changelog | |
|---|---|
| ![Project changelog with dated entries](docs/assets/screenshots/changelog.png) | |

### Collaboration and integrations

| Teams | Invitation |
|---|---|
| ![Teams with members, roles and change auditing](docs/assets/screenshots/teams.png) | ![Team or project invitation via secure token](docs/assets/screenshots/invitation.png) |

| Share links | Public view |
|---|---|
| ![Active share links with revocation](docs/assets/screenshots/shares.png) | ![Read-only shared project without login](docs/assets/screenshots/share-public.png) |

| Intake forms | Public intake |
|---|---|
| ![Intake form editor: fields, required flags and defaults](docs/assets/screenshots/intake-forms.png) | ![Public intake form — creates the task without an account](docs/assets/screenshots/intake-public.png) |

| GitHub | Integrations |
|---|---|
| ![GitHub integration: linked PRs, commits, releases and check runs](docs/assets/screenshots/github.png) | ![Integrations: Slack/Discord, n8n and external calendars](docs/assets/screenshots/integrations.png) |

| Webhooks | API keys |
|---|---|
| ![Inbound and outbound webhooks with HMAC signature and deliveries](docs/assets/screenshots/webhooks.png) | ![API keys with scopes for the public API](docs/assets/screenshots/api-keys.png) |

| Notifications | Search |
|---|---|
| ![Notification center with preferences and digest](docs/assets/screenshots/notifications.png) | ![Global search with syntax: assigned:me, due:today, tag:…](docs/assets/screenshots/search.png) |

| Help | |
|---|---|
| ![Help and keyboard shortcut reference](docs/assets/screenshots/help.png) | |

### Account, security and sync

| Account | Profile |
|---|---|
| ![Account: personal data, sessions and deactivation](docs/assets/screenshots/account.png) | ![Profile: user preferences and activity](docs/assets/screenshots/profile.png) |

| Security | E2E encryption |
|---|---|
| ![Security: TOTP 2FA, backup codes and active sessions](docs/assets/screenshots/security.png) | ![E2EE: per-device keys and passphrase-encrypted backup](docs/assets/screenshots/encryption.png) |

| Offline sync | Session expired |
|---|---|
| ![Offline sync: devices, revocation and per-field conflicts](docs/assets/screenshots/offline-sync.png) | ![Session expired with re-login and local-change preservation](docs/assets/screenshots/session-expired.png) |

| Suspended account | Activity |
|---|---|
| ![Suspended account: notice and contact channel](docs/assets/screenshots/suspended.png) | ![Global activity: unified task and audit feed](docs/assets/screenshots/activity.png) |

| Audit | |
|---|---|
| ![Exportable audit log with actor, action and timestamp](docs/assets/screenshots/audit.png) | |

### Administration

| Admin panel | Jobs |
|---|---|
| ![Admin panel with instance metrics](docs/assets/screenshots/admin.png) | ![Background job queues (Celery)](docs/assets/screenshots/admin-jobs.png) |

| Organizations | Roles |
|---|---|
| ![Organizations: tenants with memberships and roles](docs/assets/screenshots/admin-organizations.png) | ![Granular roles and permissions per scope](docs/assets/screenshots/admin-roles.png) |

| SLA policies | Feature flags |
|---|---|
| ![SLA policies per priority with automatic escalation](docs/assets/screenshots/admin-sla.png) | ![Feature flags as per-prefix kill switch](docs/assets/screenshots/feature-flags.png) |

### Access and states

| Login | Register |
|---|---|
| ![Sign in](docs/assets/screenshots/login.png) | ![Account registration](docs/assets/screenshots/register.png) |

| Password recovery | Reset |
|---|---|
| ![Password recovery by email](docs/assets/screenshots/forgot-password.png) | ![Reset form with token](docs/assets/screenshots/reset-password.png) |

| Verify email | Onboarding |
|---|---|
| ![Pending email verification](docs/assets/screenshots/verify-email.png) | ![Initial account onboarding](docs/assets/screenshots/onboarding.png) |

| 403 | 404 |
|---|---|
| ![Access denied (403)](docs/assets/screenshots/forbidden.png) | ![Page not found (404)](docs/assets/screenshots/not-found.png) |

### AI assistant

| | |
|---|---|
| ![Smart assistant: task suggestions with accept/reject](docs/assets/screenshots/ai-assistant.png) | ![Subscribed external calendars](docs/assets/screenshots/calendars.png) |

| Workflows | |
|---|---|
| ![Workflows: per-project configurable state transitions](docs/assets/screenshots/workflows.png) | |

</details>

> **Note** — The UI ships in Spanish and English; these screenshots show the
> Spanish build. Switch language in Account → Preferences.

---

## What is it

TODOlist is for teams and individuals who want serious work management
**without handing over their data**: the server only sees ciphertext on
encrypted tasks, everything is self-hosted single-node, and every write
channel (REST, GraphQL, CalDAV, MCP, offline sync, GitHub, automations)
goes through the same authorization boundary.

See [docs/SCOPE.md](./docs/SCOPE.md) for what it does — and explicitly
does **not** do (no video calls, no marketplace, no multi-region).

## Project status

> [!NOTE]
> Functional beta. The data model and REST API are stable; GraphQL and
> offline sync may receive compatible changes documented in
> `CHANGELOG.md`. Production supported via Docker Compose/K8s/Helm.

## Quick start

Requirements: Docker + Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

| URL | What |
|---|---|
| <http://localhost:5173> | Frontend |
| <http://localhost:8000/api/docs/> | Swagger UI (OpenAPI) |
| <http://localhost:8000/graphql/> | GraphQL |
| <http://localhost:8000/admin/> | Django admin |

Demo data (opt-in): `SEED_DEV=1 docker compose up --build`.

## Features

- **Full tasks** — subtasks, comments, attachments, dependencies with
  cycle detection, recurrence, estimates, time tracking.
- **Views** — list, Kanban with WIP limits, editable table, calendar,
  Gantt/roadmap, flow-KPI dashboards.
- **Real agility** — sprints with capacity/burndown, story points,
  estimated-vs-actual velocity, DORA metrics.
- **Collaboration** — organizations, teams, granular roles, mentions,
  invitations, wiki with revisions, public intake forms.
- **Automation** — trigger/condition/action rules, SLA policies with
  escalation, outbound HMAC webhooks, Slack/Discord integrations.
- **GitHub integration** — App OAuth, bidirectional sync, PRs/commits/
  releases/check-runs linked to tasks.
- **Public API** — REST (OpenAPI + contract testing), GraphQL with
  depth limiting, WebSockets, CalDAV/iCal, MCP server, scoped API keys.
- **Privacy** — opt-in E2EE (AES-GCM + RSA-OAEP per device; the server
  never sees plaintext), offline sync with per-field merge.
- **Security** — TOTP 2FA + backup codes, per-org SAML/SCIM SSO,
  exportable audit log, per-scope rate limiting.

Per-feature detail and maturity level: [docs/MATURITY.md](./docs/MATURITY.md).

## Architecture

```mermaid
flowchart LR
    User --> Web["React 18 + Vite + MUI (PWA)"]
    Web -->|"REST / GraphQL / WS"| API["Django 5 + DRF + Channels"]
    API --> DB[(PostgreSQL)]
    API --> Redis[("Redis · cache + broker")]
    API --> Worker["Celery + Beat"]
    API -->|HMAC webhooks| Ext[External services]
    Ext -->|"GitHub sync"| API
```

Every write channel converges on `apps/tasks/services.py` +
`for_user(write=True)` — the single authorization boundary
([ADR-001](./docs/decisions/ADR-001-permissions-model.md),
[ADR-004](./docs/decisions/ADR-004-multi-channel-parity.md)).

Full stack and rationale: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Configuration

All variables documented in [`.env.example`](./.env.example).
These **fail at startup** if missing in production: `DJANGO_SECRET_KEY`,
`DATA_ENCRYPTION_KEYS`, `POSTGRES_*`. `FEATURE_*` flags act as kill
switches by URL prefix (`/api/ai/*`, `/api/sync/*`, E2EE).

## Structure

```text
backend/    Django + DRF + Celery + Channels (14 apps, ~50 models)
frontend/   React + Vite + MUI + TanStack Query (PWA)
docs/       SCOPE · ARCHITECTURE · decisions/ · operations/ · security/
deploy/     Helm + K8s + Terraform
integrations/n8n-nodes-todolist/   n8n plugin
```

## Verification

```bash
# Backend — 2,826 tests (pytest, ~12 min with -n 8)
cd backend && python -m pytest tests/ -n 8 -q

# Frontend — 145 vitest tests + typecheck + lint
cd frontend && npx vitest run && npx tsc --noEmit && npx eslint src
```

CI also runs: ruff + bandit, contract testing (schemathesis),
pip-audit + npm audit, gitleaks, markdownlint + link check,
Docker builds and OpenSSF Scorecard.

## Documentation

- **Use/operate**: [docs/operations/](./docs/operations/) — SLO/SLI,
  incidents, backup-restore, PRR, risk register, quarterly review.
- **Develop**: [AGENTS.md](./AGENTS.md) (commands + decisions) ·
  [docs/GOLDEN_PATHS.md](./docs/GOLDEN_PATHS.md) ·
  [docs/decisions/](./docs/decisions/) (ADRs) ·
  [docs/DEPENDENCIES.md](./docs/DEPENDENCIES.md).
- **Governance**: [docs/QUALITY.md](./docs/QUALITY.md) ·
  [docs/TECH_DEBT.md](./docs/TECH_DEBT.md) ·
  [docs/DEPRECATION.md](./docs/DEPRECATION.md).
- **Security/data**: [docs/security/e2ee-threat-model.md](./docs/security/e2ee-threat-model.md) ·
  [docs/PRIVACY.md](./docs/PRIVACY.md) ·
  [docs/architecture/failure-modes.md](./docs/architecture/failure-modes.md).

## Known limitations

- Single-node self-hosted — no multi-region scaling.
- E2EE content is not searchable nor visible to the AI assistant (by
  design; see the [threat model](./docs/security/e2ee-threat-model.md)).
- No signed releases or published SBOM yet (TD-008 — activates on the
  first public release).
- E2EE without a private-key backup = unrecoverable data.

Full register with priorities: [docs/TECH_DEBT.md](./docs/TECH_DEBT.md).

## Contributing

[`CONTRIBUTING.md`](./CONTRIBUTING.md) — setup, Definition of Done/Ready,
reviewer checklist. Good entry point: the recipes in
[docs/GOLDEN_PATHS.md](./docs/GOLDEN_PATHS.md).

## Security

**Do not open a public issue** for vulnerabilities — private process in
[`SECURITY.md`](./SECURITY.md) (GitHub Security Advisories).

## License

[AGPLv3](./LICENSE).
