# Carta técnica — propósito, alcance y responsables

## Propósito

TODOlist es una plataforma de gestión de trabajo open source (AGPLv3)
y autoalojable: tareas, proyectos, sprints, OKRs, wiki, automatizaciones,
sincronización offline y E2EE opcional. Alternativa self-hosted a
Todoist/Linear/Asana-lite.

## Incluido

- Gestión de trabajo: tareas, subtareas, secciones, dependencias,
  recurrencia, estimaciones, time tracking.
- Colaboración: proyectos compartidos con roles, organizaciones,
  equipos, menciones, comentarios, invitaciones.
- Entrega: sprints, épicas, burndown/velocity, releases vinculadas a
  GitHub.
- Automatización: reglas trigger/acción, SLA policies, webhooks.
- Datos propios: offline sync con conflictos por campo, E2EE opt-in.
- APIs: REST (OpenAPI), GraphQL, WebSockets, CalDAV/iCal, MCP.

## Fuera de alcance (declarado)

- Videollamadas/chat síncrono propio (se integra vía Slack/Discord).
- Marketplace/plugins de terceros.
- Escalado multi-región — el modelo es self-hosted single-node.
- Facturación, SSO enterprise gestionado por el proyecto (SAML/SCIM
  existen pero los opera quien despliega).

## Responsables

Proyecto de un mantenedor; `CODEOWNERS` cubre todas las áreas con
`@owner`. Las funciones (producto, arquitectura, seguridad, releases,
operación, docs) recaen en el mantenedor — el riesgo de bus factor
está registrado como R-08 en `docs/operations/risk-register.md` y se
mitiga con AGENTS.md + ADRs + CONTRIBUTING.

## Criterio de "terminado"

La funcionalidad llega a nivel 5–6 de `docs/maturity.md` (tests +
observabilidad) y cumple la Definition of Done de `CONTRIBUTING.md`.
