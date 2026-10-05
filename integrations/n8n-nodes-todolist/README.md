# n8n-nodes-todolist

Nodo de comunidad de n8n para [TODOlist](https://github.com/ToDoSolutions/TODOlist):
gestión de tareas/proyectos self-hosted y open-source.

## Instalación

En n8n self-hosted (Settings → Community Nodes):

```bash
npm install n8n-nodes-todolist
```

O en desarrollo: `npm run build` y enlaza `dist/` en
`~/.n8n/custom/` (ver [docs n8n](https://docs.n8n.io/integrations/creating-nodes/deploy/install-private-nodes/)).

## Credenciales

| Campo | Valor |
|---|---|
| Base URL | `https://tu-instancia-todolist` (sin `/` final) |
| API Key | `tl_…` — Settings → API keys en TODOlist |

Scopes: `read` basta para lecturas; `write` para crear/actualizar/borrar
y para registrar el trigger.

## Nodos

### TODOlist (action)

- **Task**: Create / Get / Get Many (filtros: proyecto, estado, búsqueda,
  límite) / Update / Mark Complete / Delete
- **Project**: Get Many
- **Comment**: Create (comentario en una tarea)

### TODOlist Trigger

Al activar el workflow registra un `OutgoingWebhook` en TODOlist
(`POST /api/outgoing-webhooks/`) apuntando al webhook de n8n, y lo borra
al desactivar. Eventos: `task_created`, `task_updated`,
`task_completed`, `task_deleted`, `comment_added`, `sprint_started`,
`sprint_closed`.

## Alternativas sin este paquete

- El nodo HTTP Request de n8n/Zapier/Make funciona directamente contra
  la REST API (`Authorization: ApiKey <tl_…>`).
- `POST /api/inbound/{token}/` crea tareas sin auth adicional —
  conector genérico para cualquier herramienta de automatización.
- Agentes (Claude, IDEs) pueden usar el MCP server en `POST /api/mcp/`.

Ver `docs/INTEGRATIONS.md` en el repo para recetas completas.
