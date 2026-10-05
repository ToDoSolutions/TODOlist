# Operaciones — TODOlist

Superficie operativa del despliegue (Django + DRF + Celery/Redis +
frontend React). El detalle vive en [`operations/`](operations/).

## Comandos habituales

```bash
python manage.py test          # suite Django
python -m pytest tests/ -q     # tests de integración
npm run build                  # build del frontend
npx playwright test            # E2E
```

## Documentos

| Doc | Contenido |
|---|---|
| [operations/backup-restore.md](operations/backup-restore.md) | Backup de la base de datos y restore |
| [operations/incident-response.md](operations/incident-response.md) | Respuesta a incidentes |
| [operations/production-readiness.md](operations/production-readiness.md) | Checklist de producción |
| [operations/review-checklist.md](operations/review-checklist.md) | Checklist operativo de revisión |
| [operations/risk-register.md](operations/risk-register.md) | Registro de riesgos operativos |
| [operations/slo.md](operations/slo.md) | SLI/SLO, RPO/RTO |

## Notas

- PostgreSQL en producción (SQLite solo como fallback de desarrollo).
- La sincronización offline usa outbox transaccional — los conflictos
  se resuelven por cliente, no por operador.
