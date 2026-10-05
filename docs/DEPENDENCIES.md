# Dependencias y servicios externos

## Política de dependencias

- Declaradas explícitamente: `backend/requirements.txt` (pinned `==`),
  `frontend/package-lock.json`, `integrations/n8n-nodes-todolist/package.json`.
- Dependabot revisa semanalmente pip + npm + github-actions.
- `pip-audit`/`npm audit` en CI; vulns residuales conocidas se registran
  en `docs/TECH_DEBT.md` (TD-002), nunca se ignoran en silencio.
- Una dependencia nueva se justifica en el PR: qué resuelve, tamaño,
  mantenimiento, alternativa stdlib.

## Servicios externos que toca el código

| Servicio | Uso | Riesgo si cae | Salida |
|---|---|---|---|
| GitHub API | OAuth login, sync repos/PRs, webhooks | Login GitHub caído; sync en retry | Desinstalar integración; login por password sigue |
| Slack/Discord | Notificaciones chat | Log de fallo; sin impacto core | Eliminar integración |
| SMTP | Verificación email, reset password | Usuarios no pueden registrarse | Verificación manual admin |
| Sentry | Observabilidad errores | Ciego a errores; core sigue | Quitar `SENTRY_DSN` |
| Redis | Cache, Celery broker, OAuth state | `health/ready` 503 | Requerido — es infra propia |
| Postgres | Todo lo transaccional | Servicio caído | Requerido — backup-restore.md |
| n8n (plugin) | `integrations/n8n-nodes-todolist` | Solo consumidores del plugin | Independiente |

## Proveedores de librerías críticas

| Dependencia | Criticidad | Plan de salida |
|---|---|---|
| Django + DRF | alta | Coste alto de migración — aceptado |
| Celery | alta | Alternativas (dramatiq, rq) evaluables |
| graphene-django | media | Endpoints REST cubren todo lo que GraphQL hace — se podría retirar |
| python3-saml, django-scim | media | Features opt-in por flag |
| MUI + TanStack Query | alta | Refactor grande — aceptado |

Política de compatibilidad: el proyecto corre en Python 3.11+/Node 20+/
Postgres 14+/Redis 7+. Cambios incompatibles de API se anuncian en
`CHANGELOG.md` con migración.
