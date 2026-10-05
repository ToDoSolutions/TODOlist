# Registro de deuda técnica

Formato por entrada: ID, zona, origen, consecuencia, riesgo, coste de
no corregirla, prioridad (P1 bloquea release / P2 próxima iteración /
P3 backlog), revisión.

| ID | Zona | Deuda | Riesgo | P |
|---|---|---|---|---|
| TD-001 | tests | Suite serial ~47 min; xdist en Windows inestable (`node down`) — workaround `--max-worker-restart` | CI lento / falsos negativos | P2 |
| TD-002 | deps | Vulns residuales en tooling de test: pytest (schemathesis exige <9), starlette (<1), setuptools | Solo tooling, no runtime; revisar al actualizar schemathesis | P3 |
| TD-003 | auth | Sesiones OAuth en cache fallback (SPA sin cookie) — TTL 10 min | Aceptado: compromiso SPA; documentado | P3 |
| TD-004 | E2EE | Sin búsqueda server-side sobre ciphertext — excluidas de FTS e IA | Feature gap inherente al diseño | aceptada |
| TD-005 | GraphQL | Sin relay/paginación cursor — `limit` cap es la mitigación actual | Listas grandes requieren varias queries | P3 |
| TD-006 | docs | AGENTS.md es el registro de decisiones de facto; migrando a `docs/decisions/` | Conocimiento disperso durante transición | P2 |
| TD-007 | ops | Backups restaurados manualmente — sin simulacro automatizado | RTO 4h no verificado continuamente | P2 |
| TD-008 | releases | Sin versionado SemVer ni artefactos firmados (nivel 4 del checklist) | Procedencia no verificable; aplica al publicar | P3 |
| TD-009 | tasks/views.py | `TaskViewSet.bulk_update` — complejidad F(44), archivo 84KB, churn 9 en 6m → hotspot #1 (criticidad alta: canal de escritura) | Cada campo nuevo toca el punto más complejo del repo | P2 |
| TD-010 | offline_sync/services.py | `_apply_task_operation` — E(39); bajo churn pero zona de paridad crítica (sync merge) | Regresión de merge llega lejos antes de detectarse | P2 |
| TD-011 | tasks/serializers.py | `TaskRelationSerializer` D(26) + `validate` D(25) — ciclos transitivos + normalización de aristas en un método | Regla de negocio densa difícil de extender | P3 |
| TD-012 | frontend | `TaskDialog.tsx` 78KB, `TasksPage.tsx` 59KB, `GitHubPage.tsx` 53KB — mega-componentes con datos+presentación+permisos | Cambios de UI caros; churn alto en AppLayout (17) | P2 |
| TD-013 | deps | ~20 paquetes Python outdated (celery 5.4→5.6, django-redis 5→7, gunicorn 22→26, drf-spectacular…); npm también | Drift acumulado; algunas majors rompen | P2 |
| TD-014 | frontend shell | `resources.ts` churn 21/6m — cada endpoint nuevo toca el api-client | Acoplamiento concentrado; es la capa correcta, pero mide velocidad de cambio de la API | observación |

## Último barrido de detección (2026-10)

Método: radon cc (complejidad), git log churn 6m (hotspots =
complejidad × frecuencia), vulture (código muerto), eslint, pip-audit,
marcadores TODO/FIXME, skip/xfail en tests.

- Complejidad media global: **A (3.2)** — sana. Los hotspots de arriba
  son excepciones localizadas, no patrón general.
- Código muerto: vulture limpio (4 hits, todos falsos positivos —
  imports de side-effect de signals y firmas DRF).
- Marcadores: los "TODO" son falsos positivos de iCal (`VTODO`) y del
  nombre del producto; no hay deuda marcada oculta.
- Tests: ~30 skip/xfail en ~2.826, concentrados en mutation coverage —
  todos condicionales legítimos, ninguna suite desactivada.
- ESLint: 0 warnings tras limpiar un `useTranslation` sin uso.

Revisión: mensual o por release — marcar obsoletas, recalcular
prioridad, vincular incidentes a la deuda que los facilitó.
