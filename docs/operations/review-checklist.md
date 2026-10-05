# Revisión trimestral de madurez

Auditoría interna estructurada. Cada apartado produce una entrada en
`docs/TECH_DEBT.md` o un issue si encuentra algo accionable.

## Código

- [ ] `ruff check` y `bandit` en CI limpios
- [ ] Sin archivos `_*.py` temporales ni scripts sueltos en raíz/backend
- [ ] Dependencias: `pip-audit`, `npm audit` revisados; tech-debt TD-002 actualizada
- [ ] Tests: suite completa pasa; flaky tests identificados

## Arquitectura

- [ ] ADRs actualizados; decisiones nuevas registradas en `docs/decisions/`
- [ ] Ningún canal de escritura nuevo sin pasar por `services.py` + `write=True`
- [ ] Ningún modelo User/Project/Task con campos sensibles expuestos en GraphQL/serializers sin revisión

## Seguridad

- [ ] Accesos: roles org/proyecto revisados
- [ ] Secretos: rotación de los operables (`DJANGO_SECRET_KEY`, tokens OAuth, webhook secrets)
- [ ] Vulnerabilidades dependencias: listado actualizado en TECH_DEBT
- [ ] Logs: ningún token/email/secret en output (buscar en `LOGGING` handlers)

## Operación

- [ ] Alertas de `slo.md` probadas con una instancia (no solo definidas)
- [ ] Backup restaurado una vez en instancia limpia (backup-restore.md)
- [ ] Runbooks válidos; postmortems cerrados en `docs/operations/incidents/`
- [ ] Capacidad: `loadtest/locustfile.py` al volumen objetivo actual

## Producto

- [ ] `docs/maturity.md` — features que afirman nivel ≥5 lo cumplen
- [ ] Features sin uso conocido marcadas para deprecación
- [ ] i18n: claves nuevas en ambos idiomas (`node _check_i18n.mjs`)

## Gestión

- [ ] `CODEOWNERS` refleja propietarios reales
- [ ] `TECH_DEBT.md` revisado: P1 bloquean release, obsoletas eliminadas
- [ ] `risk-register.md` actualizado con incidentes del trimestre
