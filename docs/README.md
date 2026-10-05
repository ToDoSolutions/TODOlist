# Documentación — TODOlist

## Arquitectura y dominio

- [Arquitectura](ARCHITECTURE.md) — visión general del sistema (Django + React)
- [Modelo de datos](DATA_MODEL.md) — entidades y relaciones principales
- [Modos de fallo](architecture/failure-modes.md) — matriz de fallo por dependencia
- [Ámbito](SCOPE.md) — qué cubre (y qué no) el producto
- [Integraciones](INTEGRATIONS.md) — GitHub, iCal, webhooks, MCP
- [Apps nativas](NATIVE_APPS.md) — estrategia móvil/escritorio
- [Análisis competitivo](COMPETITIVE_ANALYSIS.md) — comparativa con herramientas existentes

## Requisitos y gobernanza

- [Requisitos](REQUIREMENTS.md) — funcionales y no funcionales
- [Gobernanza](GOVERNANCE.md) — roles y proceso de decisión
- [Madurez](MATURITY.md) — matriz de madurez por feature
- [Calidad](QUALITY.md) — gates y presupuestos de calidad
- [Dependencias](DEPENDENCIES.md) — política e inventario de dependencias
- [Deprecaciones](DEPRECATION.md) — política de retirada de APIs/features
- [Deuda técnica](TECH_DEBT.md) — registro formal de deuda
- [Golden paths](GOLDEN_PATHS.md) — recorridos críticos de usuario

## Seguridad y privacidad

- [Modelo de amenazas](THREAT_MODEL.md) — análisis STRIDE general
- [E2EE](security/e2ee-threat-model.md) — qué protege (y qué no) el cifrado cliente
- [Privacidad](PRIVACY.md) — datos que trata el sistema

## Decisiones (ADRs)

- [Índice de ADRs](decisions/README.md) — modelo de permisos, outbox, E2EE,
  paridad multicanal, modelo de tenant

## Operaciones

- [Operaciones](OPERATIONS.md) — índice operativo y despliegue
- [SLO](operations/slo.md) — objetivos de fiabilidad
- [Backup y restore](operations/backup-restore.md)
- [Respuesta a incidentes](operations/incident-response.md)
- [Production readiness](operations/production-readiness.md)
- [Checklist de revisión](operations/review-checklist.md)
- [Registro de riesgos](operations/risk-register.md)
