# Modelo de amenazas — TODOlist

STRIDE aplicado al sistema self-hosted. El sub-modelo E2EE
(tareas cifradas extremo a extremo) tiene su propio documento:
[`security/e2ee-threat-model.md`](security/e2ee-threat-model.md).

## Activos

- Datos de trabajo de usuarios (tareas, proyectos, adjuntos).
- Credenciales (hashes, tokens de sesión, secretos de webhook).
- Claves E2EE (viven en el cliente — el servidor nunca las ve).
- Integridad del audit log (append-only).

## Superficie de ataque

| Entrada | Mitigación |
|---|---|
| API REST/GraphQL/WS | auth por sesión/token; permisos por rol en servidor; validación DRF/serializers |
| Share links | token aleatorio, solo lectura, caducidad; sin enlaces a recursos privados |
| Webhooks salientes | secreto por integración, firma de payload; sin SSRF a meta-puertos internos |
| Adjuntos | extensión/tamaño limitados; servidos con `nosniff`; fuera del document root |
| Cola de sync offline | `client_id` de dedup; `client_id` spoofable no otorga acceso (dedup solo) |
| Canal E2EE | contenido cifrado en cliente; el servidor solo ve blobs opacos |
| Sesión admin Django | CSRF + host allow-list; no se publica `/admin` sin auth |

## STRIDE resumido

| Amenaza | Ejemplo | Controles |
|---|---|---|
| Spoofing | token de share link robado | caducidad + revocación; tokens de alta entropía |
| Tampering | edición cruzada de proyectos | optimistic locking + permisos de rol por query |
| Repudiation | "yo no borré eso" | `AuditLog` append-only con actor+meta |
| Info disclosure | proyecto ajeno en listados | querysets filtrados por membresía (servidor) |
| DoS | flood de webhooks/notificaciones | rate limits en entrada + colas con reintento |
| Elevation | invitado que se hace admin | checks de rol por endpoint, no por UI |

## Confianza

- El operador de la instancia ve todo lo no cifrado — es su
  servidor; se documenta en `docs/PRIVACY.md`.
- Los secretos de despliegue viven fuera del repo (`.env`).
- La cadena E2EE asume el dispositivo del usuario como frontera:
  un cliente comprometido compromete sus claves (ver sub-modelo).

## Lo que NO está en alcance

- Compromiso del host del operador (fuera del modelo aplicación).
- Tor/VPN anonimato: no es un objetivo del producto.
