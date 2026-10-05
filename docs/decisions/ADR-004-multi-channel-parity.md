# ADR-004: Capa de servicio única para paridad multi-canal

## Contexto

Una tarea puede crearse/editarse por REST, GraphQL, CalDAV, MCP,
offline sync, automatizaciones, intake, email-to-task, GitHub sync,
plantillas y recurrencia. Cada canal duplicando validación producía
paridad rota: `seq`/`position` sin asignar, `completed_at` no seteado,
workflow transitions ignoradas.

## Decisión

`apps/tasks/services.py` es el único punto de: `update_task`,
`get_editable_task`, `apply_completion_effects`, `validate_state`,
`assert_state_transition`, `next_position_seq`. Toda creación pasa por
`next_position_seq` (position + seq "MP-12"); todo cambio de estado por
`assert_state_transition` (workflows configurables).

## Consecuencias

+ Comportamiento idéntico en los 11 canales — verificado con tests
  de paridad por canal.
+ Refactor de un canal nunca puede saltarse la validación sin que
  sea explícito en el diff.
