# Architecture Decision Records

Formato: un ADR por decisión, contexto → decisión → alternativas →
consecuencias. No se reescriben: si una decisión cambia, se crea un
ADR nuevo que referencia al anterior.

| ADR | Decisión | Estado |
|---|---|---|
| [ADR-001](ADR-001-permissions-model.md) | `for_user(write=)` + `accessible_projects` como única frontera de autorización | Activo |
| [ADR-002](ADR-002-outbox-transactional.md) | Outbox transaccional para efectos externos (WS, webhooks) | Activo |
| [ADR-003](ADR-003-e2ee-client-side.md) | E2EE opcional con clave privada solo en dispositivo | Activo |
| [ADR-004](ADR-004-multi-channel-parity.md) | Capa de servicio única (`tasks/services.py`) para todos los canales de escritura | Activo |
| [ADR-005](ADR-005-tenant-model.md) | Organización → Proyecto → Tarea con roles propagados | Activo |
