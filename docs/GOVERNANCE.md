# Gobernanza — TODOlist

## Roles

- **Mantenedor**: revisa y mergea PRs, decide dirección, corta
  releases, gestiona secretos de CI y despliegues.
- **Contribuidor**: issues, PRs y documentación.
- Áreas críticas (ver `.github/CODEOWNERS`): `apps/users/`,
  `apps/encryption/`, `apps/integrations/` — requieren revisión
  obligatoria.

## Proceso de cambios

- Todo cambio llega por PR con CI verde (`ci.yml`, `security.yml`,
  `scorecard.yml`). Ramas `feature/*` → `main`.
- Cambios de API: actualizar schema OpenAPI + `docs/DEPRECATION.md`
  si rompe compatibilidad; nunca romper clientes sin release note.
- Migraciones de esquema: `makemigrations` revisado a mano; datos
  destructivos requieren migración de datos con plan de rollback.
- Decisiones arquitectónicas: ADR en `docs/decisions/` — no se
  borran, se marcan *Superseded*.

## Calidad

- `python -m pytest tests/ -q` (2826 tests) + `manage.py test`
  deben pasar; `npx tsc --noEmit` + `npx vitest run` en frontend.
- Contract testing con schemathesis en el pipeline.
- Mutation testing con `mutmut` para módulos críticos.

## Seguridad

- Vulnerabilidades: canal privado de `SECURITY.md`, nunca issue
  público. SLA de respuesta en SECURITY.
- Dependencias: audits semanales automatizados; actualizaciones de
  seguridad prioritarias sobre features.
