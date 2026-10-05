# Objetivos de fiabilidad (SLI/SLO) y recuperación (RPO/RTO)

Objetivos declarados para una instancia self-hosted o la instancia de
referencia. Medibles con `GET /api/monitoring/metrics/` (Prometheus) y
`GET /api/monitoring/health/` + `/health/ready/`.

## SLI / SLO

| Indicador (SLI) | Objetivo (SLO) | Medición |
|---|---|---|
| Disponibilidad API (`/api/health/ready`) | ≥ 99.5 % mensual | Probe externo cada 60 s |
| Latencia lectura (`GET /api/tasks/`) | p95 < 300 ms | Histograma en `/metrics/` |
| Latencia escritura (`POST/PATCH /api/tasks/`) | p95 < 800 ms | Histograma en `/metrics/` |
| Tasa de errores 5xx | < 0.5 % de requests | Contador por código en `/metrics/` |
| Webhooks salientes entregados | ≥ 99 % sin dead-letter | `OutgoingDelivery.status` |
| Outbox procesado | lag < 60 s | `process_outbox_events` beat (30 s) |

Alertas accionables sugeridas (ejemplo en `deploy/grafana/dashboard.json`):

- `readiness` devolviendo 503 > 2 min → página.
- p95 lectura > 300 ms durante 10 min → warning.
- `dead_letter` deliveries > 0 → warning (hay botón de retry en WebhooksPage).
- Crecimiento de `OutboxEvent` pendientes > 5 min → warning.

## RPO / RTO

| Objetivo | Valor | Mecanismo |
|---|---|---|
| RPO (pérdida máxima de datos) | 24 h | `pg_dump` diario (o WAL archiving si PITR) |
| RTO (tiempo de restauración) | 4 h | Ver `backup-restore.md` |
| Redis | sin RPO | Solo cache/queues; reconstruible |
| Media (attachments) | 24 h | Backup del volumen `media/` |

## Capacidad

Referencias verificadas con `loadtest/locustfile.py`:

- 50 usuarios concurrentes ~ sostenible sin tuning en el compose por defecto.
- Límites ya enforced: rate limiting DRF por scope, payload webhooks
  ≤ 2 MB, listas GraphQL cap 500, `pull_changes` cap 2000 tasks/500
  proyectos (`truncated`), page sizes REST 50/100.
- Queries lentas: activar `pg_stat_statements` en Postgres y revisar
  los serializers marcados N+1 en `AGENTS.md` antes de optimizar.
