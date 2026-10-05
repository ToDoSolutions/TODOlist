# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El proyecto aún no publica releases versionados — las entradas se agrupan
por fecha sobre `main`.

## [Unreleased]

### Seguridad

- GitHub OAuth: vinculación por email exige email **verificado** en
  `/user/emails` (el email público del perfil puede no estarlo); el state
  OAuth es single-use atómico vía cache.
- Webhooks GitHub entrantes: scoping por `installation`+`repo` del payload.
- Autorización de escritura (`for_user(write=True)`) en AI apply, plan_day,
  intake submit y canales no-REST (GraphQL mutations, CalDAV, MCP,
  offline sync, automatizaciones).
- GraphQL: `UserType` restringido a campos públicos (antes graphene-django
  autogeneraba un tipo con `password`, `ical_token`, `inbound_email_token`,
  `scim_*`); `EpicType` explícito; `limit` con cap en todas las listas.
- E2EE: rotación de clave pública atómica conservando la clave anterior.
- Throttling dedicado en desactivación/borrado de cuenta.

### Corregido

- Notificaciones: `action_url` apunta a la ruta canónica `/app/tasks/{id}`;
  `TasksPage` acepta además `?task=N` de notificaciones antiguas.
- NotificationBell usa navegación SPA (antes `window.location.hash`),
  `aria-label` y manejo de errores; CommandPalette limpia su `setTimeout`.
- Frontend: helpers de API normalizan respuestas `T[] | {results}`.
- OAuth callback: tests actualizados al contrato de email verificado.

### Infraestructura

- `docker-compose`: frontend usa `Dockerfile.dev` (Vite dev), Postgres/Redis
  solo en `127.0.0.1`, `seed_dev` opt-in (`SEED_DEV=1`), `FRONTEND_URL`
  cae a `DJANGO_FRONTEND_URL`, Celery/beat comparten el env del backend.
- Gobernanza: `SECURITY.md`, `CONTRIBUTING.md` (con Definition of
  Done/Ready), `CHANGELOG.md`, Dependabot, plantillas de issue/PR,
  `CODEOWNERS`, `.well-known/security.txt`, workflow OpenSSF Scorecard.
- Docs: `docs/decisions/` (ADRs), `docs/SCOPE.md` (carta técnica),
  `docs/QUALITY.md` (atributos + presupuestos), `docs/TECH_DEBT.md`
  (registro formal), `docs/PRIVACY.md` (inventario/clasificación),
  `docs/DEPENDENCIES.md` (proveedores + plan de salida),
  `docs/DEPRECATION.md` (ciclo de vida y retirada),
  `docs/GOLDEN_PATHS.md` (recetas para tareas comunes),
  `docs/architecture/failure-modes.md` (modos de fallo por
  dependencia), `docs/operations/` (SLO, incident-response,
  backup-restore, production-readiness, risk-register,
  review-checklist trimestral).
- `CONTRIBUTING.md`: Definition of Done/Ready + checklist del revisor.
- README bilingüe: `README.md` (ES) + `README.en.md` (EN) con capturas
  reales de la app (`docs/assets/screenshots/`, regenerables con
  `frontend/e2e/screenshots.ts`).
