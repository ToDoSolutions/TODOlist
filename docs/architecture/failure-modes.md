# Modos de fallo por dependencia

Qué pasa cuando cada dependencia externa se cae, va lenta o devuelve
basura. Diseñado a propósito (Release It!): solo se documentan patrones
que ya existen o decisiones aceptadas explícitamente.

| Dependencia | Si está caída | Si va lenta | Datos inválidos | Duplicados |
|---|---|---|---|---|
| **Postgres** | `health/ready` → 503; la app no sirve | Requests lentos hasta timeout de Daphne | N/A (constraints en schema) | Idempotencia por constraints + `select_for_update` |
| **Redis** (cache/broker) | `health/ready` → 503; Celery para; OAuth state fallback pierde el store | Colas crecen; `process_outbox_events` se acumula | Events quedan FAILED, reintentan | Outbox dedup; `cache.delete` atómico |
| **GitHub API** | `github_client._request` raise → sync queda FAILED, reintenta beat | `requests` timeout por defecto | `resp.json()` falla → error controlado | Webhook dedup por delivery id |
| **Webhooks salientes** (URLs de usuario) | 4xx/5xx → FAILED → retry por beat → dead-letter | SSRF guard + timeout; sin redirects | Firma HMAC; el receptor verifica | Delivery id en el payload |
| **Slack/Discord** | `ChatMessageLog` registra el fallo | Timeout en request | Error registrado en log de integración | `test` action es idempotente |
| **SMTP** (email verify/reset) | Log + error al usuario; no rompe el request | Timeout smtplib | N/A | Tokens de un solo uso |
| **Sentry** | `init_sentry` con DSN vacío = no-op | N/A (SDK async) | N/A | N/A |
| **WebSocket push** | `WS push no disponible` en log — la escritura DB no falla | Canal lento no bloquea REST | Mensaje mal formado → consumer lo descarta | El cliente re-pide estado |

## Patrones aplicados

- **Timeout**: `requests` en github_client y webhooks salientes tienen
  timeout explícito; smtplib el suyo.
- **Retry limitado**: outbox máx. 5 intentos; beat recoge FAILED.
- **Dead letter**: entregas entrantes fallidas → `dead_letter` +
  retry manual (`POST /api/webhooks/retry-dead-letter/`).
- **Degradación funcional**: push WS ausente no aborta la escritura;
  feature flags (`FEATURE_*`) actúan como kill switch por prefijo.
- **Idempotencia**: `clientMessageId`-style dedup en webhooks
  entrantes; sync offline merge por campo con `base_fields`.

## Lo que falta (consciente)

- Sin circuit breaker ante GitHub/Slack persistentemente caídos —
  el volumen self-hosted no lo justifica; está en TECH_DEBT.
- Backup restore manual — ver `backup-restore.md` + TD-007.
