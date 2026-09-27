import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// Recursos por batch: cada bloque de páginas exporta { es, en } con claves
// namespaced (p.<bloque>.*). Se mergean sobre el núcleo common/nav/task.
import batchTaskUi from "./batchTaskUi";
import batchBoard from "./batchBoard";
import batchAuth from "./batchAuth";
import batchWork from "./batchWork";
import batchPlan from "./batchPlan";
import batchCollab from "./batchCollab";
import batchAdmin from "./batchAdmin";
import batchOps from "./batchOps";
import batchIntegr from "./batchIntegr";
import batchMisc from "./batchMisc";
import batchShell from "./batchShell";
import batchOrg from "./batchOrg";
import batchPublic from "./batchPublic";
import batchExtras from "./batchExtras";
import batchTaskX from "./batchTaskX";
import batchPush from "./batchPush";
import batchEnt from "./batchEnt";

const core = {
  es: {
    translation: {
      // Sidebar
      "nav.inbox": "Bandeja de entrada",
      "nav.favorites": "Favoritas",
      "nav.completed": "Completadas",
      "nav.savedSearches": "Búsquedas guardadas",
      "nav.projects": "Proyectos",
      "nav.dashboard": "Dashboard",
      "nav.automations": "Automatizaciones",
      "nav.audit": "Auditoría",
      "nav.apiKeys": "API Keys",
      "nav.security": "Seguridad",
      "nav.myWork": "Mi trabajo",
      "nav.wiki": "Wiki",
      "nav.tags": "Etiquetas",
      "nav.notifications": "Notificaciones",
      "nav.sprints": "Sprints",
      "nav.epics": "Épicas",
      "nav.gantt": "Gantt",
      "nav.roadmap": "Roadmap",
      "nav.burndown": "Burndown",
      "nav.capacity": "Capacidad",
      "nav.timeTracking": "Registro de tiempo",
      "nav.templates": "Plantillas",
      "nav.okrs": "OKRs",
      "nav.aiAssistant": "Asistente Inteligente",
      "nav.github": "GitHub",
      "nav.chat": "Chat (Slack/Discord)",
      "nav.webhooks": "Webhooks",
      "nav.teams": "Equipos",
      "nav.customFields": "Campos personalizados",
      "nav.featureFlags": "Feature Flags",
      "nav.offlineSync": "Sincronización offline",
      "nav.encryption": "Encriptación E2E",
      "nav.profile": "Mi perfil",
      "nav.focus": "Enfoque",
      "nav.productivity": "Productividad",
      "section.planning": "Planificación",
      "section.metrics": "Métricas y OKRs",
      "section.integrations": "Integraciones",
      "section.system": "Sistema",
      "common.tasks": "tareas",
      "common.noProjectsHint": "Sin proyectos. Crea uno con +.",
      "common.name": "Nombre",
      "common.color": "Color",
      "common.lightMode": "Modo claro",
      "common.darkMode": "Modo oscuro",
      // Common
      "common.create": "Crear",
      "common.cancel": "Cancelar",
      "common.save": "Guardar",
      "common.delete": "Eliminar",
      "common.edit": "Editar",
      "common.search": "Buscar",
      "common.loading": "Cargando...",
      "common.noResults": "Sin resultados",
      "common.confirm": "Confirmar",
      "common.close": "Cerrar",
      // Task states
      "task.state.backlog": "Backlog",
      "task.state.pending": "Pendiente",
      "task.state.in_progress": "En progreso",
      "task.state.blocked": "Bloqueada",
      "task.state.in_review": "En revisión",
      "task.state.completed": "Completada",
      "task.state.cancelled": "Cancelada",
      "task.state.archived": "Archivada",
      // Priorities
      "task.priority.p0": "P0 Crítica",
      "task.priority.p1": "P1 Alta",
      "task.priority.p2": "P2 Media-alta",
      "task.priority.p3": "P3 Media",
      "task.priority.p4": "P4 Baja",
      "task.priority.p5": "P5 Algún día",
      // Views
      "view.list": "Lista",
      "view.kanban": "Kanban",
      "view.table": "Tabla",
      "view.calendar": "Calendario",
      // Auth
      "auth.login": "Iniciar sesión",
      "auth.register": "Registrarse",
      "auth.logout": "Cerrar sesión",
      "auth.email": "Email",
      "auth.password": "Contraseña",
    },
  },
  en: {
    translation: {
      // Sidebar
      "nav.inbox": "Inbox",
      "nav.favorites": "Favorites",
      "nav.completed": "Completed",
      "nav.savedSearches": "Saved searches",
      "nav.projects": "Projects",
      "nav.dashboard": "Dashboard",
      "nav.automations": "Automations",
      "nav.audit": "Audit",
      "nav.apiKeys": "API Keys",
      "nav.security": "Security",
      "nav.myWork": "My work",
      "nav.wiki": "Wiki",
      "nav.tags": "Tags",
      "nav.notifications": "Notifications",
      "nav.sprints": "Sprints",
      "nav.epics": "Epics",
      "nav.gantt": "Gantt",
      "nav.roadmap": "Roadmap",
      "nav.burndown": "Burndown",
      "nav.capacity": "Capacity",
      "nav.timeTracking": "Time tracking",
      "nav.templates": "Templates",
      "nav.okrs": "OKRs",
      "nav.aiAssistant": "AI Assistant",
      "nav.github": "GitHub",
      "nav.chat": "Chat (Slack/Discord)",
      "nav.webhooks": "Webhooks",
      "nav.teams": "Teams",
      "nav.customFields": "Custom fields",
      "nav.featureFlags": "Feature flags",
      "nav.offlineSync": "Offline sync",
      "nav.encryption": "E2E encryption",
      "nav.profile": "My profile",
      "nav.focus": "Focus",
      "nav.productivity": "Productivity",
      "section.planning": "Planning",
      "section.metrics": "Metrics & OKRs",
      "section.integrations": "Integrations",
      "section.system": "System",
      "common.tasks": "tasks",
      "common.noProjectsHint": "No projects. Create one with +.",
      "common.name": "Name",
      "common.color": "Color",
      "common.lightMode": "Light mode",
      "common.darkMode": "Dark mode",
      // Common
      "common.create": "Create",
      "common.cancel": "Cancel",
      "common.save": "Save",
      "common.delete": "Delete",
      "common.edit": "Edit",
      "common.search": "Search",
      "common.loading": "Loading...",
      "common.noResults": "No results",
      "common.confirm": "Confirm",
      "common.close": "Close",
      // Task states
      "task.state.backlog": "Backlog",
      "task.state.pending": "Pending",
      "task.state.in_progress": "In progress",
      "task.state.blocked": "Blocked",
      "task.state.in_review": "In review",
      "task.state.completed": "Completed",
      "task.state.cancelled": "Cancelled",
      "task.state.archived": "Archived",
      // Priorities
      "task.priority.p0": "P0 Critical",
      "task.priority.p1": "P1 High",
      "task.priority.p2": "P2 Medium-high",
      "task.priority.p3": "P3 Medium",
      "task.priority.p4": "P4 Low",
      "task.priority.p5": "P5 Someday",
      // Views
      "view.list": "List",
      "view.kanban": "Kanban",
      "view.table": "Table",
      "view.calendar": "Calendar",
      // Auth
      "auth.login": "Sign in",
      "auth.register": "Sign up",
      "auth.logout": "Sign out",
      "auth.email": "Email",
      "auth.password": "Password",
    },
  },
};

const batches = [
  batchTaskUi,
  batchBoard,
  batchAuth,
  batchWork,
  batchPlan,
  batchCollab,
  batchAdmin,
  batchOps,
  batchIntegr,
  batchMisc,
  batchShell,
  batchPush,
  batchOrg,
  batchPublic,
  batchExtras,
  batchTaskX,
  batchEnt,
];

const resources = {
  es: {
    translation: Object.assign({}, core.es.translation, ...batches.map((b) => b.es)),
  },
  en: {
    translation: Object.assign({}, core.en.translation, ...batches.map((b) => b.en)),
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng: localStorage.getItem("i18n-lang") || "es",
  fallbackLng: "es",
  interpolation: { escapeValue: false },
});

export default i18n;
