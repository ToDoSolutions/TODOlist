# Requisitos — TODOlist

Convención: `FR-x` funcional, `NFR-x` no funcional, con cómo se
verifica. El alcance detallado está en `docs/SCOPE.md` y los flujos
felices en `docs/GOLDEN_PATHS.md`.

## Funcionales

| ID | Requisito | Verificación |
|---|---|---|
| FR-1 | CRUD de tareas con estados, prioridades, fechas, subtareas y etiquetas | tests backend + UI |
| FR-2 | Proyectos con favoritos, plantillas y catálogo comunitario | tests + plantillas builtin |
| FR-3 | Sprints con burndown/burnup, cierre y traspaso de incompletas | `sprintsApi.getMetrics` + tests |
| FR-4 | OKRs por proyecto con progreso | tests + UI |
| FR-5 | Wiki por proyecto con historial y markdown en vivo | tests + preview |
| FR-6 | Automatizaciones con disparadores/condiciones/acciones y SLA | `AutomationRule` + tests |
| FR-7 | Equipos, roles, menciones e invitaciones por email | tests de permisos |
| FR-8 | Notificaciones in-app + webhooks salientes | `Notification` + `ChatIntegration` |
| FR-9 | Share links públicos de solo lectura con caducidad | tests de acceso anónimo |
| FR-10 | Sincronización offline: cola de operaciones con dedup | `SyncOperation` + tests PWA |
| FR-11 | Tareas cifradas E2EE opt-in (el servidor no ve el contenido) | `security/e2ee-threat-model.md` + tests |
| FR-12 | i18n ES/EN en toda la superficie | locales + tests de claves |
| FR-13 | Métricas de productividad (racha, histograma, mejor día) | `taskX2Api.productivity` |
| FR-14 | Audit log consultable por acción/recurso | tests + UI admin |

## No funcionales

| ID | Requisito | Verificación |
|---|---|---|
| NFR-1 | Self-hosted: Docker Compose en un comando | `docker compose up --build` |
| NFR-2 | Licencia AGPL-3.0 | `LICENSE` |
| NFR-3 | Permisos por rol aplicados en servidor, no solo en UI | tests de autorización |
| NFR-4 | PWA instalable; funciona sin conexión y sincroniza al volver | E2E offline |
| NFR-5 | Secrets fuera del repo (`.env.example` documenta todo) | gitleaks en CI |
| NFR-6 | Multi-canal con paridad REST/GraphQL/WS | `decisions/ADR-004` |
| NFR-7 | Audit log append-only | sin endpoints de edición |
| NFR-8 | Despliegue soportado: Compose, K8s y Helm | charts + CI |
