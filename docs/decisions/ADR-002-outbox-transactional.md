# ADR-002: Outbox transaccional para efectos externos

## Contexto

Los efectos externos (push WebSocket, webhooks salientes, chat
integrations) no pueden correr dentro de la transacción HTTP sin
riesgo de entrega fantasma (evento publicado, transacción rollback)
o latencia acoplada al request.

## Decisión

`apps/events.OutboxEvent` persiste el evento de dominio en la misma
transacción que el cambio; `publish()` despacha síncrono y el beat
`process_outbox_events` (30 s) reintenta FAILED con `select_for_update`
(skip_locked). Efectos internos (AuditLog, Notification, TaskActivity)
siguen síncronos en transacción — son baratos y necesitan consistencia.

## Consecuencias

+ At-least-once garantizado; DLQ con retry manual desde la UI.
+ Los webhooks salientes heredan scoping por owner_id + HMAC + SSRF guard.
+ Lag de ~30 s en reintentos; aceptable para notificaciones.
+ `process_outbox_events` depende del beat — documentado como requisito
  de despliegue (compose lo lleva como servicio separado).
