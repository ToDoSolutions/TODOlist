# Production Readiness Review

Checklist antes de publicar una funcionalidad o servicio crítico.
Aplica a features nuevas de riesgo (auth, sync, E2EE, integraciones)
— no a fixes triviales.

## Producto

- [ ] Propósito y usuarios definidos (SCOPE.md o ADR)
- [ ] Criterios de aceptación verificables escritos
- [ ] Flujos críticos identificados y con tests

## Arquitectura

- [ ] Límites claros: no cruza la frontera de autorización (ADR-001)
- [ ] Dependencias nuevas justificadas en `docs/DEPENDENCIES.md`
- [ ] Puntos únicos de fallo identificados en `failure-modes.md`

## Operación

- [ ] Health/readiness cubre las dependencias que la feature introduce
- [ ] Logs útiles sin datos sensibles
- [ ] Alerta o runbook si la feature puede degradar (slo.md)

## Fiabilidad

- [ ] Timeouts en toda llamada remota
- [ ] Reintentos limitados si hay retry
- [ ] Idempotencia donde la operación puede repetirse
- [ ] Degradación documentada si la dependencia cae

## Seguridad

- [ ] Autorización verificada server-side (tests + y −)
- [ ] Sin secretos en código/docs/imagen
- [ ] Rate limiting si es endpoint público o costoso
- [ ] Datos nuevos clasificados en `PRIVACY.md`

## Recuperación

- [ ] Migraciones reversibles o plan roll-forward
- [ ] Rollback posible (o feature flag como kill switch)
- [ ] Backups cubren los datos nuevos

## Cierre

- [ ] Riesgo nuevo registrado en `risk-register.md` si aplica
- [ ] `TECH_DEBT.md` actualizado si se acepta deuda consciente
