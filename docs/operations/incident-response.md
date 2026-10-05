# Respuesta a incidentes

## Clasificación de severidad

| Sev | Definición | Ejemplos |
|---|---|---|
| S1 | Pérdida de datos, breach, servicio caído | Fuga de datos entre tenants, DB corrupta, auth bypass |
| S2 | Feature crítica degradada | Login roto, sync offline rechaza todo, webhooks en DLQ masivo |
| S3 | Degradación con workaround | Latencia alta, una integración caída, widget roto |
| S4 | Menor | Error cosmético, typo, caso borde sin impacto |

## Procedimiento S1/S2

1. **Contener**: si es de seguridad, revoca lo comprometido primero
   (rota `DJANGO_SECRET_KEY` → invalida JWTs; `ical_token`/`inbound_email_token`
   rotan por endpoint; API keys revocables; desactiva el GitHubInstallation).
   Si es disponibilidad, roll-forward o rollback al último deploy bueno.
2. **Diagnosticar**: logs del backend (stdout vía `LOGGING` en settings),
   Sentry si `SENTRY_DSN` está configurado, `/api/monitoring/metrics/`,
   `docker compose logs`, `OutboxEvent`/`OutgoingDelivery` con status FAILED.
3. **Comunicar**: issue interno con timeline; para vulnerabilidades,
   coordinar divulgación por el canal de `SECURITY.md` (nunca en público
   antes del fix).
4. **Corregir**: hotfix con test de regresión (caso positivo + negativo
   para bugs de autorización — ver CONTRIBUTING).
5. **Post-mortem**: causa raíz, qué lo detectó, qué lo habría detectado
   antes, acciones con responsable. Guardar en `docs/operations/incidents/`.

## Contactos / propiedad

- Propietario del servicio: ver `README` / mantenedor del repo.
- Reportes de seguridad externos: `SECURITY.md`.

## Errores frecuentes (cheat sheet)

| Síntoma | Primer sitio donde mirar |
|---|---|
| Login/OAuth falla | `github_oauth_state` en cache (TTL 10 min), `DJANGO_FRONTEND_URL`, emails verificados |
| Sync offline rechaza ops | `SyncOperation.status`, `for_user(write=True)` en `_validate_task_changes` |
| Webhooks entrantes ignorados | firma `X-Hub-Signature-256`, scoping instalación+repo |
| E2EE "no puedo leer tareas" | clave privada del dispositivo, rotación conserva clave antigua |
| Celery no procesa | `process_outbox_events` en beat, Redis reachable desde `health/ready` |
