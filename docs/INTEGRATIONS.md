# Integraciones externas

TODOlist se integra con herramientas de automatización en cuatro niveles,
sin código adicional en la mayoría de los casos.

## 1. REST API + API keys

```text
Authorization: ApiKey tl_xxxxxxxx…
```

Scopes: `read` (GET), `write` (mutaciones), `admin` (todo). Crear en
Settings → API keys. Documentación OpenAPI: `GET /api/schema/`.

Funciona tal cual con el nodo/action HTTP de Zapier, Make, n8n,
Power Automate, Shortcuts…

## 2. n8n (community node)

Paquete `n8n-nodes-todolist` en `integrations/n8n-nodes-todolist/`:
nodos **TODOlist** (CRUD de tareas/proyectos/comentarios) y
**TODOlist Trigger** (registra/limpia webhooks automáticamente).

## 3. Webhooks

### Entrantes (crear tareas)

`POST /api/inbound/{token}/` — sin auth extra (el token es la credencial).
Campos: `title` (requerido), `description`, `priority`, `due_date`,
`project`. Throttle 60/h.

Ejemplo Zapier: Trigger → Webhook POST a
`https://tu-instancia/api/inbound/<token>/`.

### Salientes (eventos → tu servicio)

`POST /api/outgoing-webhooks/` `{url, events[], secret?}` — HMAC en
`X-Webhook-Signature`, entregas registradas en `WebhookDelivery`,
reintentos vía outbox. Eventos: `task_created`, `task_updated`,
`task_completed`, `task_deleted`, `comment_added`, `sprint_started`,
`sprint_closed`.

Ejemplo Make: Custom webhook → POST desde TODOlist → módulos siguientes.

### Desde automatizaciones (webhook por regla)

La acción `call_webhook` de `AutomationRule` hace POST a cualquier URL
externa cuando una regla se dispara — el conector universal para n8n,
Make, Zapier o endpoints propios sin registrar nada en la app:

```json
{
  "trigger": "task_completed",
  "action": "call_webhook",
  "action_params": {
    "url": "https://n8n.tu-servidor/webhook/abc",
    "secret": "opcional — firma HMAC en X-Hub-Signature-256"
  }
}
```

Mismo endurecimiento que los webhooks salientes: SSRF guard (solo
https, destinos públicos) y sin redirects. El payload incluye la tarea
y el sprint del contexto; funciona también con triggers sin tarea
(`sprint_closed`, `scheduled`, `daily_check`).

## 4. MCP server (agentes/LLMs)

`POST /api/mcp/` — JSON-RPC 2.0 Streamable HTTP. Configura en clientes
MCP con `Authorization: ApiKey <key>`:

```json
{
  "mcpServers": {
    "todolist": {
      "url": "https://tu-instancia/api/mcp/",
      "headers": { "Authorization": "ApiKey tl_…" }
    }
  }
}
```

Tools disponibles: `tasks_list`, `tasks_create`, `tasks_update`,
`tasks_complete`, `projects_list`, `tags_list`, `users_me` — con los
mismos scopes y permisos por objeto que la REST API.

## 5. Email y calendario

- **Email-to-task**: `POST /api/inbound-email/` (SendGrid/Mailgun
  inbound-parse): `task-<token>@dominio` crea tareas, `[task-N]` comenta.
- **iCal feed**: `GET /api/tasks/calendar.ics/?token=<ical_token>`
  (suscripción read-only en Google/Outlook/Apple).
- **CalDAV**: `https://instancia/api/caldav/` — Basic auth con el
  `ical_token` como password; colección `tasks/` de VTODOs
  bidireccional (Thunderbird, Tasks.org, DAVx5…).
