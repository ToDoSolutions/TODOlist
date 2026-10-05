## Qué cambia y por qué

<!-- Describe el problema que resuelve y la decisión tomada. -->

## Cómo se ha verificado

- [ ] `pytest tests/` (backend) — pasan / no aplica
- [ ] `npx tsc -b --noEmit` + `vitest run` (frontend) — pasan / no aplica
- [ ] Tests nuevos para el cambio (obligatorio en permisos/autorización: casos + y −)

## Checklist

- [ ] Sin secretos ni datos sensibles
- [ ] Migraciones reversibles (si aplica)
- [ ] Docs actualizadas (README / AGENTS.md / docs/) si el cambio lo requiere
- [ ] `CHANGELOG.md` actualizado si el cambio es visible para usuarios
