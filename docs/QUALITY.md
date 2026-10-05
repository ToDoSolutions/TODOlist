# Atributos de calidad prioritarios

Declaración explícita de qué importa más en este proyecto y cómo se mide.
Una decisión que empeore un atributo `critical` exige justificación en el PR.

## Prioridades

| Atributo | Prioridad | Objetivo | Medición | Umbral |
|---|---|---|---|---|
| Seguridad | crítica | Sin escaladas de privilegio ni fuga entre tenants | tests de autorización +/− por canal, bandit, pip-audit | 0 bypass conocidos |
| Fiabilidad | crítica | Escrituras atómicas, sync sin pérdida | tests de conflicto sync, outbox | RPO 24h, RTO 4h (slo.md) |
| Mantenibilidad | alta | Cambio pequeño sin tocar N módulos | `ruff`, tiempo de CI, líneas por vista | CI < 15 min |
| Privacidad | alta | Mínimos datos; E2EE real donde aplica | threat model + tests cifrado | ver ADR-003 |
| Rendimiento | media | p95 lecturas < 300 ms | `/api/monitoring/metrics/` | presupuestos abajo |
| Accesibilidad | media | WCAG 2.2 AA en flujos principales | revisión manual + aria-* | navegable por teclado |
| Escalabilidad | baja | Self-hosted single-node basta | locustfile | 50 usuarios concurrentes |

## Presupuestos técnicos (comprobables)

```yaml
budgets:
  api_p95_read_ms: 300           # /metrics/ histogram
  api_p95_write_ms: 800
  frontend_tests_min: 3
  backend_suite_min: 60          # serial; ~12 con -n 8
  graphql_max_rows_per_query: 500  # MAX_LIST_LIMIT en schema.py
  webhook_payload_max_bytes: 2097152
  sync_pull_max_tasks: 2000
```

Los que tienen enforcement automático: tamaño de payload webhook,
caps de listas GraphQL y sync pull, page sizes REST, rate limits DRF.
Los demás se comprueban en la revisión trimestral (ver
`docs/operations/review-checklist.md`).
