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

Per-feature detail and maturity level: [docs/maturity.md](./docs/maturity.md).

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
