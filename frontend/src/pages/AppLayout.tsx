import { useEffect, useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useProject } from "../auth/ProjectContext";
import {
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Typography,
  AppBar,
  Toolbar,
  Button,
  IconButton,
  Divider,
  Chip,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Stack,
  Menu,
  MenuItem,
  ListSubheader,
  BottomNavigation,
  BottomNavigationAction,
  Paper,
  useMediaQuery,
} from "@mui/material";
import {
  CheckSquare,
  CheckCircle2,
  Inbox,
  LogOut,
  Plus,
  X,
  Folder,
  Github,
  Flag,
  Layers,
  BarChart3,
  Map,
  Zap,
  ScrollText,
  Key,
  Shield,
  TrendingDown,
  TrendingUp,
  Timer,
  Users,
  Target,
  ChevronDown,
  ChevronUp,
  Settings,
  LayoutDashboard,
  Bell,
  FileText,
  Briefcase,
  BookOpen,
  Search,
  Menu as MenuIcon,
  HelpCircle,
  Sun,
  Moon,
  User as UserIcon,
  Home,
  Calendar,
  AlertTriangle,
  KanbanSquare,
  Star,
  Wifi,
  WifiOff,
  Link2,
  Scale,
  Clock,
  Lightbulb,
  MessageSquare,
  Repeat,
  FolderOpen,
  CalendarPlus,
  Presentation,
  Share2,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi, tasksApi } from "../api/resources";
import { savedSearchesApi } from "../api/resources";
import { notificationsApi } from "../api/resources";
import { useAuth } from "../auth/AuthContext";
import { notify } from "../notify";
import NotificationBell from "../components/NotificationBell";
import PwaInstallPrompt from "../components/PwaInstallPrompt";
import PwaUpdatePrompt from "../components/PwaUpdatePrompt";
import CommandPalette from "../components/CommandPalette";
import ShortcutsDialog from "../components/ShortcutsDialog";
import { useCommandPalette } from "../hooks/useCommandPalette";
import { useHotkeys } from "react-hotkeys-hook";
import { useUiStore } from "../store/uiStore";
import { useRealtime } from "../hooks/useRealtime";
import { useTheme } from "@mui/material/styles";
import { keyframes } from "@emotion/react";
import { useThemeMode } from "../theme-context";
import { useTranslation } from "react-i18next";
import pkg from "../../package.json";

const APP_VERSION = pkg.version;
const drawerWidth = 260;

// Transición de ruta sutil (estilo Linear): el wrapper del <Outlet/> va
// keyed por pathname, así cada navegación remonta el contenido y esta
// animación corre una sola vez. Sin enter/exit ni librería extra.
// La regla global prefers-reduced-motion del CssBaseline ya la neutraliza.
const fadeSlideIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

type View = "list" | "table" | "kanban" | "calendar";

export default function AppLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const { user, logout } = useAuth();
  useRealtime(!!user);
  const navigate = useNavigate();
  const location = useLocation();
  const projectCtx = useProject();
  const { mode: themeMode, toggle: toggleTheme } = useThemeMode();
  const { t, i18n: i18nObj } = useTranslation();
  const changeLang = (lang: string) => {
    i18nObj.changeLanguage(lang);
    localStorage.setItem("i18n-lang", lang);
  };
  const qc = useQueryClient();
  const palette = useCommandPalette();
  const markPaletteUsed = useUiStore((s) => s.markPaletteUsed);
  useEffect(() => {
    if (palette.open) markPaletteUsed();
  }, [palette.open, markPaletteUsed]);
  const [projectDialog, setProjectDialog] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectColor, setProjectColor] = useState("#1976d2");

  // --- Estado de navegación móvil / menús ---
  const [mobileNav, setMobileNav] = useState(false);
  const [avatarAnchor, setAvatarAnchor] = useState<HTMLElement | null>(null);
  const [createAnchor, setCreateAnchor] = useState<HTMLElement | null>(null);
  const [helpAnchor, setHelpAnchor] = useState<HTMLElement | null>(null);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  // Shift+? abre la referencia de atajos (convención tipo Gmail/GitHub)
  useHotkeys("shift+?", (e) => {
    e.preventDefault();
    setShortcutsOpen(true);
  });

  const { data: projectsData, isLoading: projectsLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  // Badges del sidebar: bandeja sin clasificar + vencidas en Mi trabajo.
  // Reutilizan la cache ["my-work"] que HomePage ya consulta.
  const { data: myWorkBadge } = useQuery({
    queryKey: ["my-work"],
    queryFn: tasksApi.myWork,
    staleTime: 60_000,
  });
  const { data: inboxCount } = useQuery({
    queryKey: ["tasks", "inbox-count"],
    queryFn: () => tasksApi.count({ no_project: "true" }),
    staleTime: 60_000,
  });
  const overdueCount = myWorkBadge?.overdue?.length ?? 0;

  // Badge de no leídas en el nav (misma queryKey que el bell/notifications).
  const { data: unreadBadge } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: notificationsApi.unreadCount,
    staleTime: 30_000,
  });
  const unreadCount =
    typeof unreadBadge === "number"
      ? unreadBadge
      : ((unreadBadge as { count?: number } | undefined)?.count ?? 0);

  // Búsquedas guardadas → sección del sidebar (acceso de un clic,
  // estilo filtros fijados de Todoist/Linear).
  const { data: savedSearchesData } = useQuery({
    queryKey: ["saved-searches"],
    queryFn: savedSearchesApi.list,
    staleTime: 60_000,
  });
  const savedSearches = Array.isArray(savedSearchesData) ? savedSearchesData : [];

  /** Construye la URL de /app/tasks con los params del filtro guardado
   *  (mismo mapeo que loadSavedSearch en TasksPage). */
  const savedSearchUrl = (filtersJson: string): string => {
    try {
      const f = JSON.parse(filtersJson) as Record<string, string | undefined>;
      const qp = new URLSearchParams();
      for (const [src, dst] of [
        ["state", "state"],
        ["priority", "priority"],
        ["tag", "tag"],
        ["sprint", "sprint"],
        ["epic", "epic"],
        ["search", "q"],
      ] as const) {
        if (f[src]) qp.set(dst, f[src]!);
      }
      const qs = qp.toString();
      return `/app/tasks${qs ? `?${qs}` : ""}`;
    } catch {
      return "/app/tasks";
    }
  };

  // Onboarding: solo la primera vez y solo si no hay proyectos todavía
  const onboardingDone = useUiStore((s) => s.onboardingDone);
  useEffect(() => {
    if (
      !projectsLoading &&
      projects.length === 0 &&
      !onboardingDone &&
      location.pathname !== "/app/onboarding"
    ) {
      navigate("/app/onboarding");
    }
  }, [projectsLoading, projects.length, onboardingDone, location.pathname, navigate]);

  const createProject = useMutation({
    mutationFn: () =>
      projectsApi.create({
        name: projectName.trim(),
        description: "",
        color: projectColor,
      }),
    onSuccess: (p) => {
      notify.success(t("p.shell.projectCreated"));
      qc.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/app/project/${p.id}`);
      setProjectDialog(false);
      setProjectName("");
      setProjectColor("#1976d2");
    },
    onError: () => notify.error(t("p.shell.projectCreateError")),
  });

  const params = new URLSearchParams(location.search);
  const view = (params.get("view") as View) || "list";

  // Ruta dentro de un proyecto activo (o filtro contextual aplicado)
  const inProject = location.pathname.startsWith("/app/project/");

  const ROUTE_TITLES: Record<string, string> = {
    "/app": "p.shell.home",
    "/app/inbox": "nav.inbox",
    "/app/my-work": "nav.myWork",
    "/app/wiki": "nav.wiki",
    "/app/projects": "nav.projects",
    "/app/sprints": "nav.sprints",
    "/app/backlog": "p.shell.backlog",
    "/app/workflows": "p.shell.workflows",
    "/app/admin": "p.shell.administration",
    "/app/activity": "p.shell.activity",
    "/app/meetings": "p.shell.meetings",
    "/app/risks": "p.shell.risks",
    "/app/intake-forms": "p.shell.forms",
    "/app/trash": "p.shell.trash",
    "/app/import-export": "p.shell.importExport",
    "/app/attention": "p.shell.attentionInbox",
    "/app/account": "p.shell.myAccount",
    "/app/epics": "nav.epics",
    "/app/dashboard": "nav.dashboard",
    "/app/automations": "nav.automations",
    "/app/gantt": "nav.gantt",
    "/app/burndown": "nav.burndown",
    "/app/capacity": "nav.capacity",
    "/app/roadmap": "nav.roadmap",
    "/app/okrs": "nav.okrs",
    "/app/teams": "nav.teams",
    "/app/notifications": "nav.notifications",
    "/app/profile": "p.shell.profile",
    "/app/security": "nav.security",
    "/app/ai-assistant": "p.shell.aiAssistant",
    "/app/github": "nav.github",
    "/app/time-entries": "p.shell.time",
    "/app/audit": "nav.audit",
    "/app/integrations": "p.shell.integrations",
    "/app/offline-sync": "p.shell.sync",
    "/app/dashboards": "p.shell.dashboards",
    "/app/help": "p.shell.help",
    "/app/changelog": "p.shell.changelog",
    "/app/search": "p.shell.searchLabel",
    "/app/admin/sla": "p.shell.sla",
    "/app/admin/jobs": "p.shell.jobs",
    "/app/admin/roles": "p.shell.roles",
    "/app/admin/organizations": "p.shell.organizations",
    "/app/tags": "nav.tags",
    "/app/templates": "nav.templates",
    "/app/custom-fields": "nav.customFields",
    "/app/webhooks": "nav.webhooks",
    "/app/feature-flags": "p.shell.featureFlags",
    "/app/encryption": "p.shell.encryption",
    "/app/recurrence-rules": "p.shell.recurrence",
    "/app/decisions": "p.shell.decisions",
    "/app/dependencies": "p.shell.dependencies",
    "/app/onboarding": "p.shell.onboarding",
    "/app/api-keys": "p.shell.apiKeys",
    "/app/403": "p.shell.forbidden",
    "/app/suspended": "p.shell.suspended",
    "/app/portfolios": "nav.portfolios",
    "/app/shares": "nav.shares",
    "/app/calendars": "p.extras.cal.title",
    "/app/whiteboards": "p.extras.wb.title",
    "/app/focus": "nav.focus",
    "/app/productivity": "nav.productivity",
    "/app/favorites": "nav.favorites",
    "/app/completed": "nav.completed",
  };
  const routeTitleKey = ROUTE_TITLES[location.pathname];
  const pageTitle = routeTitleKey
    ? t(routeTitleKey)
    : inProject
      ? t("p.shell.project")
      : "TODOlist";

  useEffect(() => {
    document.title = `${pageTitle} · TODOlist`;
  }, [pageTitle]);

  const openCreate = (e: React.MouseEvent<HTMLElement>) =>
    setCreateAnchor(e.currentTarget);

  const pid = projectCtx.project?.id;
  const createItems = [
    {
      label: t("p.shell.createTask"),
      action: () => {
        const base = inProject && pid ? `/app/project/${pid}/tasks` : "/app/inbox";
        navigate(`${base}?view=${view}&new=1`);
      },
    },
    { label: t("p.shell.newProject"), action: () => setProjectDialog(true) },
    { label: t("p.shell.newSprint"), action: () => navigate("/app/sprints") },
    { label: t("p.shell.newEpic"), action: () => navigate("/app/epics") },
    { label: t("p.shell.newObjective"), action: () => navigate("/app/okrs") },
    { label: t("p.shell.newWikiPage"), action: () => navigate("/app/wiki") },
    { label: t("p.shell.newMeeting"), action: () => navigate("/app/meetings") },
    { label: t("p.shell.newForm"), action: () => navigate("/app/intake-forms") },
    { label: t("p.shell.invitePeople"), action: () => navigate("/app/teams") },
  ];

  // Estado de conexión para la barra de estado
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // --- Navegación reorganizada por espacios (IA):
  // Área personal · Proyectos · Equipo · Administración. Las funciones de
  // proyecto solo aparecen dentro del contexto de un proyecto activo.
  const favoriteProjects = useUiStore((s) => s.favoriteProjects);
  const recentProjects = useUiStore((s) => s.recentProjects);
  const toggleFavorite = useUiStore((s) => s.toggleFavoriteProject);
  const density = useUiStore((s) => s.density);
  const setDensity = useUiStore((s) => s.setDensity);

  const [showAllProjects, setShowAllProjects] = useState(false);
  const favorites = projects.filter((p) => favoriteProjects.includes(p.id));

  // Lista única sin duplicados: favoritos primero, luego recientes, luego resto.
  // Capada a 8 entradas para que el Drawer no crezca con el nº de proyectos.
  const orderedProjects = (() => {
    const seen = new Set<number>();
    const out: typeof projects = [];
    const push = (p: (typeof projects)[number] | undefined) => {
      if (p && !seen.has(p.id)) {
        seen.add(p.id);
        out.push(p);
      }
    };
    favorites.forEach(push);
    recentProjects.forEach((id) => push(projects.find((p) => p.id === id)));
    projects.forEach(push);
    return out;
  })();
  const PROJECT_LIST_CAP = 8;
  const visibleProjects = showAllProjects
    ? orderedProjects
    : orderedProjects.slice(0, PROJECT_LIST_CAP);
  const hiddenProjectsCount = orderedProjects.length - visibleProjects.length;

  const goProject = (p: { id: number; name: string; color: string }) => {
    projectCtx.setProject(p);
    navigate(`/app/project/${p.id}`);
    setMobileNav(false);
  };

  const projectRow = (p: {
    id: number;
    name: string;
    color: string;
    tasks_count?: number;
  }) => (
    <ListItemButton
      key={p.id}
      selected={projectCtx.project?.id === p.id}
      onClick={() => goProject({ id: p.id, name: p.name, color: p.color })}
      sx={{ py: 0.5 }}
    >
      <ListItemIcon sx={{ minWidth: 32 }}>
        <Folder size={17} color={p.color} />
      </ListItemIcon>
      <ListItemText
        primary={p.name}
        primaryTypographyProps={{ noWrap: true, fontSize: "0.85rem" }}
      />
      <IconButton
        size="small"
        aria-label={
          favoriteProjects.includes(p.id)
            ? t("p.shell.removeFavorite")
            : t("p.shell.markFavorite")
        }
        onClick={(e) => {
          e.stopPropagation();
          toggleFavorite(p.id);
        }}
        sx={{ opacity: favoriteProjects.includes(p.id) ? 1 : 0.35 }}
      >
        <Star
          size={14}
          fill={favoriteProjects.includes(p.id) ? "currentColor" : "none"}
        />
      </IconButton>
    </ListItemButton>
  );

  const projectNav = inProject && projectCtx.project && (
    <>
      <Divider sx={{ mt: 1 }} />
      <NavGroup label={projectCtx.project.name.toUpperCase()} />
      <List dense>
        <NavItem
          icon={<LayoutDashboard size={18} />}
          label={t("p.shell.summary")}
          path={`/app/project/${pid}`}
          current={location.pathname + location.search}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
      <NavGroup label={t("p.shell.work")} />
      <List dense>
        <NavItem
          icon={<CheckSquare size={18} />}
          label={t("p.shell.tasks")}
          path={`/app/project/${pid}/tasks?view=list`}
          current={location.pathname + location.search}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<KanbanSquare size={18} />}
          label={t("view.kanban")}
          path={`/app/project/${pid}/tasks?view=kanban`}
          current={location.pathname + location.search}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Calendar size={18} />}
          label={t("view.calendar")}
          path={`/app/project/${pid}/tasks?view=calendar`}
          current={location.pathname + location.search}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
      <NavGroup label={t("section.planning")} />
      <List dense>
        <NavItem
          icon={<Inbox size={18} />}
          label={t("p.shell.backlog")}
          path="/app/backlog"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Flag size={18} />}
          label={t("nav.sprints")}
          path="/app/sprints"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Layers size={18} />}
          label={t("nav.epics")}
          path="/app/epics"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Map size={18} />}
          label={t("nav.roadmap")}
          path="/app/roadmap"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<BarChart3 size={18} />}
          label={t("nav.gantt")}
          path="/app/gantt"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<AlertTriangle size={18} />}
          label={t("p.shell.risks")}
          path="/app/risks"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Link2 size={18} />}
          label={t("p.shell.dependencies")}
          path="/app/dependencies"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
      <NavGroup label={t("p.shell.knowledge")} />
      <List dense>
        <NavItem
          icon={<BookOpen size={18} />}
          label={t("nav.wiki")}
          path="/app/wiki"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Users size={18} />}
          label={t("p.shell.meetings")}
          path="/app/meetings"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Scale size={18} />}
          label={t("p.shell.decisions")}
          path="/app/decisions"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
      <NavGroup label={t("p.shell.results")} />
      <List dense>
        <NavItem
          icon={<LayoutDashboard size={18} />}
          label={t("nav.dashboard")}
          path="/app/dashboard"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<TrendingDown size={18} />}
          label={t("nav.burndown")}
          path="/app/burndown"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Users size={18} />}
          label={t("nav.capacity")}
          path="/app/capacity"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
      <NavGroup label={t("p.shell.operations")} />
      <List dense>
        <NavItem
          icon={<Zap size={18} />}
          label={t("nav.automations")}
          path="/app/automations"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<FileText size={18} />}
          label={t("p.shell.forms")}
          path="/app/intake-forms"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Github size={18} />}
          label={t("p.shell.integrations")}
          path="/app/github"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
      <List dense>
        <NavItem
          icon={<Settings size={18} />}
          label={t("p.misc.projectSettings.breadcrumb")}
          path={`/app/project/${pid}/settings`}
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
    </>
  );

  const drawerContent = (
    <Box sx={{ overflow: "auto", pb: 2 }}>
      {/* Área personal */}
      <NavGroup label={t("p.shell.home")} />
      <List dense>
        <NavItem
          icon={<Home size={18} />}
          label={t("p.shell.home")}
          path="/app"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Briefcase size={18} />}
          label={t("nav.myWork")}
          path="/app/my-work"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
          badge={overdueCount}
          badgeColor="error"
        />
        <NavItem
          icon={<Inbox size={18} />}
          label={t("p.shell.attentionInbox")}
          path="/app/attention"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Inbox size={18} />}
          label={t("nav.inbox")}
          path="/app/inbox"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
          badge={inboxCount}
        />
        <NavItem
          icon={<CheckSquare size={18} />}
          label={t("p.taskx.palette.navTasks")}
          path="/app/tasks"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Star size={18} />}
          label={t("nav.favorites")}
          path="/app/favorites"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<CheckCircle2 size={18} />}
          label={t("nav.completed")}
          path="/app/completed"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Search size={18} />}
          label={t("p.shell.searchLabel")}
          path="/app/search"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Clock size={18} />}
          label={t("p.shell.time")}
          path="/app/time-entries"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Repeat size={18} />}
          label={t("p.shell.recurrence")}
          path="/app/recurrence-rules"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Lightbulb size={18} />}
          label={t("p.shell.aiAssistant")}
          path="/app/ai-assistant"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Bell size={18} />}
          label={t("nav.notifications")}
          path="/app/notifications"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
          badge={unreadCount}
          badgeColor="error"
        />
        <NavItem
          icon={<Timer size={18} />}
          label={t("nav.focus")}
          path="/app/focus"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<TrendingUp size={18} />}
          label={t("nav.productivity")}
          path="/app/productivity"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>

      {/* Búsquedas guardadas */}
      {savedSearches.length > 0 && (
        <>
          <NavGroup label={t("nav.savedSearches")} />
          <List dense>
            {savedSearches.slice(0, 8).map((ss) => (
              <NavItem
                key={ss.id}
                icon={<Search size={18} />}
                label={ss.name}
                path={savedSearchUrl(ss.filters)}
                current={`${location.pathname}${location.search}`}
                navigate={navigate}
                onNavigate={() => setMobileNav(false)}
              />
            ))}
          </List>
        </>
      )}

      {/* Proyectos */}
      <NavGroup
        label={t("nav.projects")}
        action={
          <IconButton
            size="small"
            onClick={() => setProjectDialog(true)}
            aria-label={t("p.shell.newProject")}
          >
            <Plus size={14} />
          </IconButton>
        }
      />
      <List dense>
        <NavItem
          icon={<Folder size={18} />}
          label={t("p.shell.allProjects")}
          path="/app/projects"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<FolderOpen size={18} />}
          label={t("nav.portfolios")}
          path="/app/portfolios"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Share2 size={18} />}
          label={t("nav.shares")}
          path="/app/shares"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<CalendarPlus size={18} />}
          label={t("p.extras.cal.title")}
          path="/app/calendars"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Presentation size={18} />}
          label={t("p.extras.wb.title")}
          path="/app/whiteboards"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
      <List dense>
        {visibleProjects.map(projectRow)}
        {hiddenProjectsCount > 0 ? (
          <ListItemButton onClick={() => setShowAllProjects(true)} sx={{ py: 0.5 }}>
            <ListItemIcon sx={{ minWidth: 32 }}>
              <ChevronDown size={16} />
            </ListItemIcon>
            <ListItemText
              primary={t("p.shell.showMore", { count: hiddenProjectsCount })}
              primaryTypographyProps={{ fontSize: "0.8rem", color: "text.secondary" }}
            />
          </ListItemButton>
        ) : showAllProjects && orderedProjects.length > PROJECT_LIST_CAP ? (
          <ListItemButton onClick={() => setShowAllProjects(false)} sx={{ py: 0.5 }}>
            <ListItemIcon sx={{ minWidth: 32 }}>
              <ChevronUp size={16} />
            </ListItemIcon>
            <ListItemText
              primary={t("p.shell.showLess")}
              primaryTypographyProps={{ fontSize: "0.8rem", color: "text.secondary" }}
            />
          </ListItemButton>
        ) : null}
        {projects.length === 0 && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ px: 2, py: 1, display: "block" }}
          >
            {t("common.noProjectsHint")}
          </Typography>
        )}
      </List>

      {/* Navegación contextual del proyecto */}
      {projectNav}

      {/* Equipo */}
      <NavGroup label={t("nav.teams")} />
      <List dense>
        <NavItem
          icon={<Users size={18} />}
          label={t("p.shell.peopleTeams")}
          path="/app/teams"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Users size={18} />}
          label={t("nav.capacity")}
          path="/app/capacity"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<Target size={18} />}
          label={t("nav.okrs")}
          path="/app/okrs"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<BarChart3 size={18} />}
          label={t("p.shell.reports")}
          path="/app/dashboard"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<LayoutDashboard size={18} />}
          label={t("p.shell.dashboards")}
          path="/app/dashboards"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<ScrollText size={18} />}
          label={t("p.shell.activity")}
          path="/app/activity"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>

      {/* Administración */}
      <NavGroup label={t("p.shell.administration")} />
      <List dense>
        <NavItem
          icon={<Settings size={18} />}
          label={t("p.shell.adminWorkspace")}
          path="/app/admin"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
        <NavItem
          icon={<MessageSquare size={18} />}
          label={t("p.shell.integrationsChat")}
          path="/app/integrations"
          current={location.pathname}
          navigate={navigate}
          onNavigate={() => setMobileNav(false)}
        />
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: "flex" }}>
      <AppBar
        position="fixed"
        sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}
        color="default"
        elevation={0}
      >
        <Toolbar>
          {isMobile && (
            <IconButton
              edge="start"
              onClick={() => setMobileNav(true)}
              aria-label={t("p.shell.openNav")}
              sx={{ mr: 1 }}
            >
              <MenuIcon size={20} />
            </IconButton>
          )}
          <CheckSquare size={22} style={{ color: theme.palette.primary.main }} />
          <Typography variant="h6" fontWeight={700} ml={1} component="div">
            TODOlist
          </Typography>
          {/* Breadcrumbs compactos: contexto de proyecto, no chip descartable */}
          {projectCtx.project && (
            <Box
              sx={{
                ml: 1.5,
                display: { xs: "none", sm: "flex" },
                alignItems: "center",
                gap: 0.5,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                /
              </Typography>
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  bgcolor: projectCtx.project.color,
                }}
              />
              <Typography variant="body2" fontWeight={600} noWrap>
                {projectCtx.project.name}
              </Typography>
              <Tooltip title={t("p.shell.clearProjectFilter")}>
                <IconButton
                  size="small"
                  onClick={() => {
                    projectCtx.clearProject();
                    navigate("/app");
                  }}
                  aria-label={t("p.shell.clearProjectFilter")}
                >
                  <X size={14} />
                </IconButton>
              </Tooltip>
            </Box>
          )}
          <Box sx={{ flexGrow: 1 }} />
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {/* Buscar / lanzador de comandos — centro-derecha */}
            <Button
              size="small"
              variant="outlined"
              color="inherit"
              startIcon={<Search size={15} />}
              onClick={() => palette.setOpen(true)}
              sx={{
                textTransform: "none",
                color: "text.secondary",
                borderColor: "divider",
                px: 1.5,
                minWidth: 0,
              }}
            >
              {isMobile ? "" : t("common.search")}
              {!isMobile && (
                <Box
                  component="kbd"
                  sx={{
                    ml: 1,
                    px: 0.6,
                    border: 1,
                    borderColor: "divider",
                    borderRadius: 0.75,
                    fontSize: 11,
                    lineHeight: 1.6,
                    bgcolor: "action.hover",
                  }}
                >
                  ⌘K
                </Box>
              )}
            </Button>
            {/* Acción global Crear */}
            <Button
              size="small"
              variant="contained"
              startIcon={<Plus size={15} />}
              onClick={openCreate}
              sx={{ textTransform: "none" }}
            >
              {isMobile ? "" : t("common.create")}
            </Button>
            <Menu
              anchorEl={createAnchor}
              open={!!createAnchor}
              onClose={() => setCreateAnchor(null)}
            >
              {createItems.map((item) => (
                <MenuItem
                  key={item.label}
                  onClick={() => {
                    setCreateAnchor(null);
                    item.action();
                  }}
                >
                  {item.label}
                </MenuItem>
              ))}
            </Menu>
            {!isMobile && (
              <>
                <Tooltip title={t("p.taskx.palette.navHelp")}>
                  <IconButton
                    color="inherit"
                    aria-label={t("p.taskx.palette.navHelp")}
                    onClick={(e) => setHelpAnchor(e.currentTarget)}
                  >
                    <HelpCircle size={20} />
                  </IconButton>
                </Tooltip>
                <Menu
                  anchorEl={helpAnchor}
                  open={!!helpAnchor}
                  onClose={() => setHelpAnchor(null)}
                >
                  <MenuItem
                    onClick={() => {
                      setHelpAnchor(null);
                      navigate("/app/help");
                    }}
                  >
                    <ListItemIcon>
                      <HelpCircle size={16} />
                    </ListItemIcon>
                    {t("p.shell.help")}
                  </MenuItem>
                  <MenuItem
                    onClick={() => {
                      setHelpAnchor(null);
                      setShortcutsOpen(true);
                    }}
                  >
                    <ListItemIcon>
                      <Key size={16} />
                    </ListItemIcon>
                    {t("p.shell.ui.shortcuts.title")}
                  </MenuItem>
                  <MenuItem
                    onClick={() => {
                      setHelpAnchor(null);
                      navigate("/app/changelog");
                    }}
                  >
                    <ListItemIcon>
                      <ScrollText size={16} />
                    </ListItemIcon>
                    {t("p.shell.changelog")}
                  </MenuItem>
                </Menu>
              </>
            )}
            <NotificationBell />
            {/* Avatar: perfil, apariencia, idioma, seguridad, logout */}
            <IconButton
              onClick={(e) => setAvatarAnchor(e.currentTarget)}
              aria-label={t("p.shell.userMenu")}
              size="small"
            >
              <Box
                sx={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  bgcolor: "primary.main",
                  color: "primary.contrastText",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                {user?.email?.[0]?.toUpperCase()}
              </Box>
            </IconButton>
            <Menu
              anchorEl={avatarAnchor}
              open={!!avatarAnchor}
              onClose={() => setAvatarAnchor(null)}
            >
              <ListSubheader sx={{ lineHeight: 2 }}>{user?.email}</ListSubheader>
              <MenuItem
                onClick={() => {
                  setAvatarAnchor(null);
                  navigate("/app/profile");
                }}
              >
                <ListItemIcon>
                  <UserIcon size={16} />
                </ListItemIcon>
                {t("nav.profile")}
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setAvatarAnchor(null);
                  navigate("/app/security");
                }}
              >
                <ListItemIcon>
                  <Shield size={16} />
                </ListItemIcon>
                {t("nav.security")}
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setAvatarAnchor(null);
                  navigate("/app/api-keys");
                }}
              >
                <ListItemIcon>
                  <Key size={16} />
                </ListItemIcon>
                {t("nav.apiKeys")}
              </MenuItem>
              <Divider />
              <MenuItem onClick={toggleTheme}>
                <ListItemIcon>
                  {themeMode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                </ListItemIcon>
                {themeMode === "dark" ? t("common.lightMode") : t("common.darkMode")}
              </MenuItem>
              <MenuItem
                onClick={() => changeLang(i18nObj.language === "es" ? "en" : "es")}
              >
                <ListItemIcon>
                  <Typography
                    variant="caption"
                    fontWeight={700}
                    sx={{ width: 16, textAlign: "center" }}
                  >
                    {i18nObj.language === "es" ? "EN" : "ES"}
                  </Typography>
                </ListItemIcon>
                {i18nObj.language === "es" ? "English" : "Español"}
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setAvatarAnchor(null);
                  navigate("/app/account");
                }}
              >
                <ListItemIcon>
                  <Settings size={16} />
                </ListItemIcon>
                {t("p.shell.myAccount")}
              </MenuItem>
              <Divider />
              <ListSubheader sx={{ lineHeight: 2 }}>{t("p.shell.density")}</ListSubheader>
              {(["comfortable", "standard", "compact"] as const).map((d) => (
                <MenuItem key={d} onClick={() => setDensity(d)} dense>
                  <ListItemIcon>
                    {density === d ? (
                      <CheckSquare size={14} />
                    ) : (
                      <Box sx={{ width: 14 }} />
                    )}
                  </ListItemIcon>
                  {d === "comfortable"
                    ? t("p.shell.densityComfortable")
                    : d === "standard"
                      ? t("p.shell.densityStandard")
                      : t("p.shell.densityCompact")}
                </MenuItem>
              ))}
              <Divider />
              <MenuItem
                onClick={() => {
                  setAvatarAnchor(null);
                  navigate("/app/admin");
                }}
              >
                <ListItemIcon>
                  <Users size={16} />
                </ListItemIcon>
                {t("p.shell.adminWorkspace")}
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setAvatarAnchor(null);
                  navigate("/app/help");
                }}
              >
                <ListItemIcon>
                  <HelpCircle size={16} />
                </ListItemIcon>
                {t("p.taskx.palette.navHelp")}
              </MenuItem>
              <MenuItem onClick={logout}>
                <ListItemIcon>
                  <LogOut size={16} />
                </ListItemIcon>
                {t("auth.logout")}
              </MenuItem>
            </Menu>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Drawer: permanente en escritorio, temporal en móvil */}
      {isMobile ? (
        <Drawer
          variant="temporary"
          open={mobileNav}
          onClose={() => setMobileNav(false)}
          ModalProps={{ keepMounted: true }}
          sx={{ "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box" } }}
        >
          <Toolbar />
          {drawerContent}
        </Drawer>
      ) : (
        <Drawer
          variant="permanent"
          sx={{
            width: drawerWidth,
            flexShrink: 0,
            "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box" },
          }}
        >
          <Toolbar />
          {drawerContent}
        </Drawer>
      )}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: { xs: 2, md: 3 },
          mt: { xs: 7, md: 8 },
          pb: { xs: 10, md: 6 }, // bottom nav móvil / barra de estado escritorio
          minWidth: 0,
        }}
      >
        <Box key={location.pathname} sx={{ animation: `${fadeSlideIn} 180ms ease-out` }}>
          <Outlet />
        </Box>
      </Box>

      {/* Navegación inferior móvil: 5 destinos + crear */}
      {isMobile && (
        <Paper
          sx={{
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: (t) => t.zIndex.appBar,
          }}
          elevation={3}
        >
          <BottomNavigation
            value={
              location.pathname === "/app"
                ? 0
                : location.pathname === "/app/my-work"
                  ? 1
                  : location.pathname === "/app/projects"
                    ? 2
                    : -1
            }
            showLabels
          >
            <BottomNavigationAction
              label={t("p.shell.home")}
              icon={<Home size={20} />}
              onClick={() => {
                projectCtx.clearProject();
                navigate("/app");
              }}
            />
            <BottomNavigationAction
              label={t("nav.myWork")}
              icon={<Briefcase size={20} />}
              onClick={() => navigate("/app/my-work")}
            />
            <BottomNavigationAction
              label={t("nav.projects")}
              icon={<Folder size={20} />}
              onClick={() => navigate("/app/projects")}
            />
            <BottomNavigationAction
              label={t("common.search")}
              icon={<Search size={20} />}
              onClick={() => palette.setOpen(true)}
            />
            <BottomNavigationAction
              label={t("common.create")}
              icon={<Plus size={20} />}
              onClick={openCreate}
            />
          </BottomNavigation>
        </Paper>
      )}

      {/* Barra de estado: conexión, versión — solo escritorio (móvil usa bottom nav) */}
      {!isMobile && (
        <Paper
          component="footer"
          square
          variant="outlined"
          sx={{
            position: "fixed",
            bottom: 0,
            left: drawerWidth,
            right: 0,
            px: 2,
            py: 0.4,
            display: "flex",
            gap: 2,
            alignItems: "center",
            borderLeft: 0,
            borderRight: 0,
            borderBottom: 0,
            zIndex: (t) => t.zIndex.drawer - 1,
          }}
        >
          <Stack direction="row" spacing={0.75} alignItems="center">
            {online ? <Wifi size={12} /> : <WifiOff size={12} color="#d32f2f" />}
            <Typography
              variant="caption"
              color={online ? "text.secondary" : "error.main"}
            >
              {online ? t("p.shell.online") : t("p.shell.offlineNotice")}
            </Typography>
          </Stack>
          <Box flex={1} />
          <Typography variant="caption" color="text.disabled">
            TODOlist v{APP_VERSION}
          </Typography>
        </Paper>
      )}

      <PwaInstallPrompt />
      <PwaUpdatePrompt />
      <CommandPalette open={palette.open} onClose={() => palette.setOpen(false)} />
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />

      <Dialog
        open={projectDialog}
        onClose={() => setProjectDialog(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>{t("p.shell.newProject")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              fullWidth
              autoFocus
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && projectName.trim()) {
                  e.preventDefault();
                  createProject.mutate();
                }
              }}
            />
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label={t("common.color")}
                type="color"
                value={projectColor}
                onChange={(e) => setProjectColor(e.target.value)}
                sx={{ width: 80 }}
                InputLabelProps={{ shrink: true }}
              />
              <Chip
                label={projectName || t("p.shell.importExport.stepPreview")}
                sx={{ bgcolor: projectColor, color: "common.white" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProjectDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!projectName.trim() || createProject.isPending}
            onClick={() => createProject.mutate()}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

/* --- Componentes auxiliares para el sidebar --- */

function NavGroup({
  label,
  action,
  nested,
}: {
  label: string;
  action?: React.ReactNode;
  nested?: boolean;
}) {
  return (
    <Box
      sx={{
        px: 2,
        pl: nested ? 4 : 2,
        pt: 1.5,
        pb: 0.25,
        display: "flex",
        alignItems: "center",
      }}
    >
      <Typography
        variant="overline"
        color="text.secondary"
        sx={{ flex: 1, fontSize: "0.62rem", fontWeight: 700, letterSpacing: 0.8 }}
      >
        {label}
      </Typography>
      {action}
    </Box>
  );
}

function NavItem({
  icon,
  label,
  path,
  current,
  navigate,
  onNavigate,
  badge,
  badgeColor = "default",
}: {
  icon: React.ReactNode;
  label: string;
  path: string;
  current: string;
  navigate: (to: string) => void;
  onNavigate?: () => void;
  badge?: number;
  badgeColor?: "default" | "error";
}) {
  return (
    <ListItemButton
      selected={current === path}
      onClick={() => {
        navigate(path);
        onNavigate?.();
      }}
      sx={{ py: 0.75 }}
    >
      <ListItemIcon sx={{ minWidth: 36 }}>{icon}</ListItemIcon>
      <ListItemText
        primary={label}
        primaryTypographyProps={{ fontSize: "0.875rem", noWrap: true }}
      />
      {!!badge && badge > 0 && (
        <Box
          component="span"
          sx={{
            minWidth: 20,
            height: 18,
            px: 0.6,
            borderRadius: 9,
            fontSize: "0.7rem",
            fontWeight: 600,
            lineHeight: "18px",
            textAlign: "center",
            bgcolor: badgeColor === "error" ? "error.main" : "action.selected",
            color: badgeColor === "error" ? "error.contrastText" : "text.secondary",
          }}
        >
          {badge > 99 ? "99+" : badge}
        </Box>
      )}
    </ListItemButton>
  );
}
