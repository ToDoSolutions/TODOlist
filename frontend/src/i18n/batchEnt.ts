// Batch "enterprise": catálogo de integraciones (IntegrationsPage),
// botones SSO del login y videollamadas de reuniones (MeetingsPage).
// Claves namespaced bajo p.ent.{market,sso,video}.*.
// NOTA: registrar este batch en i18n/index.ts (import + array batches).
export default {
  es: {
    // --- Catálogo de integraciones ---
    "p.ent.market.title": "Catálogo de integraciones",
    "p.ent.market.desc":
      "Conecta TODOlist con tus herramientas: chat, calendarios, webhooks, SSO y más.",
    "p.ent.market.configure": "Configurar",
    "p.ent.market.status.connected": "Conectado",
    "p.ent.market.status.available": "Disponible",
    "p.ent.market.status.unconfigured": "No configurado",
    "p.ent.market.github.name": "GitHub",
    "p.ent.market.github.desc":
      "Sincroniza repositorios, PRs, commits y releases con tus tareas.",
    "p.ent.market.chat.name": "Chat (Slack/Discord)",
    "p.ent.market.chat.desc":
      "Recibe eventos de tareas en tus canales de Slack o Discord.",
    "p.ent.market.inbound.name": "Webhooks entrantes",
    "p.ent.market.inbound.desc":
      "Crea tareas desde servicios externos con un simple POST.",
    "p.ent.market.outbound.name": "Webhooks salientes",
    "p.ent.market.outbound.desc":
      "Notifica a tus endpoints cuando las tareas cambian (firmado con HMAC).",
    "p.ent.market.ical.name": "Feed iCal",
    "p.ent.market.ical.desc":
      "Suscríbete a tus deadlines desde Google, Outlook o Apple Calendar.",
    "p.ent.market.email.name": "Email-to-task",
    "p.ent.market.email.desc":
      "Crea tareas y comentarios enviando un email a tu dirección única.",
    "p.ent.market.push.name": "Notificaciones push",
    "p.ent.market.push.desc":
      "Avisos web push en este dispositivo, incluso con el navegador cerrado.",
    "p.ent.market.sso.name": "SSO empresarial (OIDC)",
    "p.ent.market.sso.desc": "Login corporativo con tu proveedor de identidad (OIDC).",
    "p.ent.market.apiKeys.name": "API keys",
    "p.ent.market.apiKeys.desc":
      "Tokens personales para integrar la API REST con tus scripts.",
    "p.ent.market.import.name": "Importar (Trello/Todoist)",
    "p.ent.market.import.desc": "Trae tus tableros y tareas desde Trello, Todoist o CSV.",
    // --- SSO en login ---
    "p.ent.sso.fallback": "Continuar con SSO",
    // --- Videollamada en reuniones ---
    "p.ent.video.sectionTitle": "Videollamada",
    "p.ent.video.create": "Crear videollamada",
    "p.ent.video.creating": "Creando…",
    "p.ent.video.join": "Unirse",
    "p.ent.video.copyLink": "Copiar enlace",
    "p.ent.video.copied": "Enlace copiado",
    "p.ent.video.embed": "Embeber",
    "p.ent.video.hideEmbed": "Ocultar",
    "p.ent.video.end": "Finalizar",
    "p.ent.video.createdOk": "Videollamada creada",
    "p.ent.video.createError": "No se pudo crear la videollamada.",
    "p.ent.video.endedOk": "Videollamada finalizada",
    "p.ent.video.endError": "No se pudo finalizar la videollamada.",
  } as Record<string, string>,
  en: {
    // --- Integration catalog ---
    "p.ent.market.title": "Integration catalog",
    "p.ent.market.desc":
      "Connect TODOlist with your tools: chat, calendars, webhooks, SSO and more.",
    "p.ent.market.configure": "Configure",
    "p.ent.market.status.connected": "Connected",
    "p.ent.market.status.available": "Available",
    "p.ent.market.status.unconfigured": "Not configured",
    "p.ent.market.github.name": "GitHub",
    "p.ent.market.github.desc":
      "Sync repositories, PRs, commits and releases with your tasks.",
    "p.ent.market.chat.name": "Chat (Slack/Discord)",
    "p.ent.market.chat.desc":
      "Get task events delivered to your Slack or Discord channels.",
    "p.ent.market.inbound.name": "Inbound webhooks",
    "p.ent.market.inbound.desc":
      "Create tasks from external services with a simple POST.",
    "p.ent.market.outbound.name": "Outbound webhooks",
    "p.ent.market.outbound.desc":
      "Notify your endpoints when tasks change (HMAC-signed).",
    "p.ent.market.ical.name": "iCal feed",
    "p.ent.market.ical.desc":
      "Subscribe to your deadlines from Google, Outlook or Apple Calendar.",
    "p.ent.market.email.name": "Email-to-task",
    "p.ent.market.email.desc":
      "Create tasks and comments by sending an email to your unique address.",
    "p.ent.market.push.name": "Push notifications",
    "p.ent.market.push.desc":
      "Web push alerts on this device, even with the browser closed.",
    "p.ent.market.sso.name": "Enterprise SSO (OIDC)",
    "p.ent.market.sso.desc": "Corporate login with your identity provider (OIDC).",
    "p.ent.market.apiKeys.name": "API keys",
    "p.ent.market.apiKeys.desc":
      "Personal tokens to integrate the REST API with your scripts.",
    "p.ent.market.import.name": "Import (Trello/Todoist)",
    "p.ent.market.import.desc":
      "Bring your boards and tasks from Trello, Todoist or CSV.",
    // --- SSO on login ---
    "p.ent.sso.fallback": "Continue with SSO",
    // --- Meeting video call ---
    "p.ent.video.sectionTitle": "Video call",
    "p.ent.video.create": "Start video call",
    "p.ent.video.creating": "Starting…",
    "p.ent.video.join": "Join",
    "p.ent.video.copyLink": "Copy link",
    "p.ent.video.copied": "Link copied",
    "p.ent.video.embed": "Embed",
    "p.ent.video.hideEmbed": "Hide",
    "p.ent.video.end": "End",
    "p.ent.video.createdOk": "Video call created",
    "p.ent.video.createError": "Could not create the video call.",
    "p.ent.video.endedOk": "Video call ended",
    "p.ent.video.endError": "Could not end the video call.",
  } as Record<string, string>,
};
