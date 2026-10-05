# ADR-001: Una única frontera de autorización

## Contexto

La app expone el mismo modelo de datos por REST, GraphQL, CalDAV, MCP,
offline sync, automatizaciones e integraciones. Autorizar por separado
en cada canal produce drift (los bugs encontrados: mutations GraphQL
con read-scope, plan_day/AI apply mutando con solo lectura).

## Decisión

Toda lectura pasa por `Task.objects.for_user(user)` /
`accessible_projects(user)`; toda escritura por `for_user(user,
write=True)` / `accessible_projects(user, write=True)`. Los canales
solo traducen entrada/salida — nunca implementan su propia regla.

## Consecuencias

+ Un fix de permisos cubre todos los canales.
+ Tests de regresión verifican +/− por canal contra la misma regla.
+ Canales nuevos deben usar la capa de servicio, no el ORM directo —
  enforced por revisión y por los tests de autorización.
