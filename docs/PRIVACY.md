# Inventario y gobierno de datos

Clasificación por sensibilidad. "Retención" = política por defecto;
self-hosted la decide el operador.

## Inventario

| Dato | Sensibilidad | Ubicación | Acceso | Retención/eliminación |
|---|---|---|---|---|
| Email, password hash, TOTP secret | **alta** | Postgres `users` | solo el propio usuario; hash PBKDF2 | Borrado de cuenta elimina; backup codes PBKDF2 |
| `ical_token`, `inbound_email_token`, API keys (hash) | **alta** | Postgres | opacos; solo se muestran al crear/rotar; `has_*` boolean en /me/ | Revocables por endpoint |
| Contenido tareas/proyectos/wiki | media | Postgres | owner + miembros con rol | CASCADE al borrar proyecto/cuenta |
| Contenido E2EE | alta (servidor no lee) | Postgres ciphertext | solo dispositivos con share | Irrecuperable sin privada — por diseño |
| AuditLog, TaskActivity | media | Postgres | owner | Exportable `/api/audit-logs/export/`; retener ≤ 1 año recomendado |
| IP en logs | baja | stdout/files | operador | Rotación por el runtime de logs |
| Attachments | media | `media/` | descarga autorizada | Backup con DB |
| OAuth tokens GitHub | alta | Postgres `GitHubInstallation.access_token` | la instalación | Borrada al desinstalar |

## Reglas operativas

- Nada de secretos ni tokens en logs: los handlers loggean IDs, no
  valores — verificado en los boundaries de auth/webhook.
- Entornos de test: `seed_dev` genera datos sintéticos — nunca copiar
  una base de producción a dev sin anonimizar.
- Minimización: intake público solo recoge lo que declara el formulario;
  menciones solo mencionan usuarios con acceso al proyecto.
- Eliminación: delete de cuenta es CASCADE real sobre todos los datos
  del usuario (no soft-delete disfrazado).
- Exportación: audit-logs exportable por el propio usuario (CSV/JSONL);
  tareas/proyectos vía API REST autenticada.
