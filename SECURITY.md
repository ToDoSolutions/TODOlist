# Política de seguridad

## Cómo reportar una vulnerabilidad

**No abras un issue público para vulnerabilidades.** Usa uno de estos canales:

- [GitHub Security Advisories](https://github.com/ToDoSolutions/TODOlist/security/advisories/new) (privado, recomendado)
- Email al mantenedor del repositorio (ver perfil del propietario en GitHub)

Incluye:

- Descripción del problema y su impacto potencial
- Pasos para reproducir o PoC
- Versión/commit afectado
- Sugerencia de mitigación, si la tienes

Recibirás acuse de recibo en **72 h** y una evaluación inicial en **7 días**.
Si el reporte se confirma, coordinamos contigo la corrección y la divulgación.

## Alcance

Lo que consideramos en alcance (ejemplos):

- Escalada de privilegios entre usuarios/proyectos/organizaciones
- Bypass de autenticación, 2FA, OAuth o permisos de escritura
- XSS, inyección, SSRF en webhooks salientes
- Fugas de datos cifrados E2E o de tokens (ical, inbound email, API keys)
- Bypass de firma en webhooks entrantes de GitHub

Fuera de alcance: auto-XSS, clickjacking en endpoints que ya exigen auth,
denegaciones de servicio que requieran credenciales válidas con rate
limiting ya aplicado, y problemas en despliegues de terceros.

## Controles implementados (resumen)

- Auth: JWT con rotación, 2FA TOTP + backup codes (PBKDF2), OAuth GitHub
  con verificación de email (`/user/emails` — el email del perfil no basta).
- Autorización: `Task.objects.for_user(write=True)` en todo canal de
  escritura (REST, GraphQL, CalDAV, MCP, offline sync, automatizaciones);
  `accessible_projects(write=True)` en proyecto/organización.
- Webhooks entrantes: HMAC `X-Hub-Signature-256`, dedup por delivery id,
  scoping por instalación+repo del payload.
- Webhooks salientes: HMAC por destino + guard anti-SSRF.
- E2EE opcional: RSA-OAEP-4096 por dispositivo envolviendo AES-GCM; el
  servidor solo ve ciphertext. Threat model: `docs/security/e2ee-threat-model.md`.
- Rate limiting en endpoints sensibles (registro, login, reset, OAuth,
  desactivación/borrado de cuenta, intake público).
- CI: `ruff` + `bandit` en cada push/PR; `pip-audit` revisado en
  `backend/pyproject.toml` (vulns residuales solo en tooling de tests).

## Soporte de versiones

Solo la rama `main` recibe correcciones de seguridad. El proyecto no
publica releases versionados todavía — despliega el último `main`.
