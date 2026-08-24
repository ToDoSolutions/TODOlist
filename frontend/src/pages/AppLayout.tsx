import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
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
  Avatar,
  Tooltip,
  Badge,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Stack,
  Select,
  MenuItem,
} from "@mui/material";
import {
  CheckSquare,
  Inbox,
  LogOut,
  Plus,
  Columns,
  List as ListIcon,
  Calendar,
  Tag as TagIcon,
  User as UserIcon,
  Folder,
  Github,
  Flag,
  Layers,
  BarChart3,
  Zap,
  ScrollText,
  Key,
  Shield,
  Sun,
  Moon,
  TrendingDown,
  Users,
  Target,
  Lightbulb,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  Settings,
  LayoutDashboard,
  Bell,
  Clock,
  FileText,
  Webhook,
  Smartphone,
  Lock,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi, tasksApi } from "../api/resources";
import { useAuth } from "../auth/AuthContext";
import { notify } from "../notify";
import NotificationBell from "../components/NotificationBell";
import PwaInstallPrompt from "../components/PwaInstallPrompt";
import { useThemeMode } from "../theme-context";
import { useTranslation } from "react-i18next";
import { isPast, isToday } from "date-fns";

const drawerWidth = 260;

type View = "list" | "kanban" | "calendar";

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { mode: themeMode, toggle: toggleTheme } = useThemeMode();
  const { i18n: i18nObj } = useTranslation();
  const changeLang = (lang: string) => {
    i18nObj.changeLanguage(lang);
    localStorage.setItem("i18n-lang", lang);
  };
  const qc = useQueryClient();
  const [projectDialog, setProjectDialog] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectColor, setProjectColor] = useState("#1976d2");
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});

  const toggleSection = (section: string) =>
    setCollapsedSections((prev) => ({ ...prev, [section]: !prev[section] }));

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  const { data: inboxTasksData } = useQuery({
    queryKey: ["tasks", { project: undefined }],
    queryFn: () => tasksApi.list({}),
  });
  const inboxTasks = Array.isArray(inboxTasksData) ? inboxTasksData : [];

  const overdueCount = inboxTasks.filter(
    (t) =>
      t.due_date &&
      t.state !== "completed" &&
      t.state !== "cancelled" &&
      t.state !== "archived" &&
      isPast(new Date(t.due_date)) &&
      !isToday(new Date(t.due_date))
  ).length;

  const createProject = useMutation({
    mutationFn: () =>
      projectsApi.create({
        name: projectName.trim(),
        description: "",
        color: projectColor,
      }),
    onSuccess: (p) => {
      notify.success("Proyecto creado");
      qc.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/app/project/${p.id}`);
      setProjectDialog(false);
      setProjectName("");
      setProjectColor("#1976d2");
    },
    onError: () => notify.error("No se pudo crear el proyecto"),
  });

  const params = new URLSearchParams(location.search);
  const view = (params.get("view") as View) || "list";

  const setView = (v: View) => {
    const q = new URLSearchParams(params);
    q.set("view", v);
    navigate({ search: q.toString() });
  };

  const isTasksView = location.pathname === "/app" || location.pathname.startsWith("/app/project");

  return (
    <Box sx={{ display: "flex" }}>
      <AppBar
        position="fixed"
        sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}
        color="default"
        elevation={0}
      >
        <Toolbar>
          <CheckSquare size={22} color="#1976d2" />
          <Typography variant="h6" fontWeight={700} ml={1}>
            TODOlist
          </Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {isTasksView && (
              <Stack direction="row" spacing={0.5}>
                <Tooltip title="Lista">
                  <IconButton onClick={() => setView("list")} color={view === "list" ? "primary" : "default"}>
                    <ListIcon size={20} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Kanban">
                  <IconButton onClick={() => setView("kanban")} color={view === "kanban" ? "primary" : "default"}>
                    <Columns size={20} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Calendario">
                  <IconButton onClick={() => setView("calendar")} color={view === "calendar" ? "primary" : "default"}>
                    <Calendar size={20} />
                  </IconButton>
                </Tooltip>
              </Stack>
            )}
            <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
            <Tooltip title={themeMode === "dark" ? "Modo claro" : "Modo oscuro"}>
              <IconButton onClick={toggleTheme} color="inherit">
                {themeMode === "dark" ? <Sun size={20} /> : <Moon size={20} />}
              </IconButton>
            </Tooltip>
            <Select
              size="small"
              value={i18nObj.language}
              onChange={(e) => changeLang(e.target.value)}
              sx={{ minWidth: 60, height: 32 }}
              variant="outlined"
            >
              <MenuItem value="es">ES</MenuItem>
              <MenuItem value="en">EN</MenuItem>
            </Select>
            <NotificationBell />
            <Tooltip title="Mi perfil">
              <IconButton onClick={() => navigate("/app/profile")} color={location.pathname === "/app/profile" ? "primary" : "default"}>
                <Avatar sx={{ width: 28, height: 28, bgcolor: "primary.main", fontSize: 13 }}>
                  {user?.email?.[0]?.toUpperCase()}
                </Avatar>
              </IconButton>
            </Tooltip>
            <Button color="inherit" startIcon={<LogOut size={16} />} onClick={logout}>
              Salir
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box" },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: "auto", pb: 2 }}>
          {/* --- Sección: Principal --- */}
          <List>
            <ListItemButton
              selected={location.pathname === "/app"}
              onClick={() => navigate("/app")}
            >
              <ListItemIcon>
                <Inbox size={20} />
              </ListItemIcon>
              <ListItemText primary="Bandeja de entrada" />
              {overdueCount > 0 && (
                <Badge badgeContent={overdueCount} color="error" />
              )}
            </ListItemButton>
            <NavItem icon={<Folder size={20} />} label="Proyectos" path="/app/projects" current={location.pathname} navigate={navigate} />
            <NavItem icon={<TagIcon size={20} />} label="Etiquetas" path="/app/tags" current={location.pathname} navigate={navigate} />
            <NavItem icon={<Bell size={20} />} label="Notificaciones" path="/app/notifications" current={location.pathname} navigate={navigate} />
          </List>

          {/* --- Sección: Planificación --- */}
          <SectionHeader
            label="Planificación"
            collapsed={!!collapsedSections.planning}
            onToggle={() => toggleSection("planning")}
          />
          {!collapsedSections.planning && (
            <List>
              <NavItem icon={<Flag size={20} />} label="Sprints" path="/app/sprints" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Layers size={20} />} label="Épicas" path="/app/epics" current={location.pathname} navigate={navigate} />
              <NavItem icon={<BarChart3 size={20} />} label="Gantt" path="/app/gantt" current={location.pathname} navigate={navigate} />
              <NavItem icon={<TrendingDown size={20} />} label="Burndown" path="/app/burndown" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Users size={20} />} label="Capacity" path="/app/capacity" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Clock size={20} />} label="Time Tracking" path="/app/time-entries" current={location.pathname} navigate={navigate} />
              <NavItem icon={<FileText size={20} />} label="Plantillas" path="/app/templates" current={location.pathname} navigate={navigate} />
            </List>
          )}

          {/* --- Sección: Métricas y OKRs --- */}
          <SectionHeader
            label="Métricas y OKRs"
            collapsed={!!collapsedSections.metrics}
            onToggle={() => toggleSection("metrics")}
          />
          {!collapsedSections.metrics && (
            <List>
              <NavItem icon={<LayoutDashboard size={20} />} label="Dashboard" path="/app/dashboard" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Target size={20} />} label="OKRs" path="/app/okrs" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Lightbulb size={20} />} label="AI Assistant" path="/app/ai-assistant" current={location.pathname} navigate={navigate} />
            </List>
          )}

          {/* --- Sección: Integraciones y Automatización --- */}
          <SectionHeader
            label="Integraciones"
            collapsed={!!collapsedSections.integrations}
            onToggle={() => toggleSection("integrations")}
          />
          {!collapsedSections.integrations && (
            <List>
              <NavItem icon={<Github size={20} />} label="GitHub" path="/app/github" current={location.pathname} navigate={navigate} />
              <NavItem icon={<MessageSquare size={20} />} label="Chat (Slack/Discord)" path="/app/integrations" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Zap size={20} />} label="Automatizaciones" path="/app/automations" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Webhook size={20} />} label="Webhooks" path="/app/webhooks" current={location.pathname} navigate={navigate} />
            </List>
          )}

          {/* --- Sección: Sistema --- */}
          <SectionHeader
            label="Sistema"
            collapsed={!!collapsedSections.system}
            onToggle={() => toggleSection("system")}
          />
          {!collapsedSections.system && (
            <List>
              <NavItem icon={<Users size={20} />} label="Equipos" path="/app/teams" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Settings size={20} />} label="Campos personalizados" path="/app/custom-fields" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Flag size={20} />} label="Feature Flags" path="/app/feature-flags" current={location.pathname} navigate={navigate} />
              <NavItem icon={<ScrollText size={20} />} label="Auditoría" path="/app/audit" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Key size={20} />} label="API Keys" path="/app/api-keys" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Shield size={20} />} label="Seguridad" path="/app/security" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Smartphone size={20} />} label="Offline Sync" path="/app/offline-sync" current={location.pathname} navigate={navigate} />
              <NavItem icon={<Lock size={20} />} label="Encriptación E2E" path="/app/encryption" current={location.pathname} navigate={navigate} />
              <NavItem icon={<UserIcon size={20} />} label="Mi perfil" path="/app/profile" current={location.pathname} navigate={navigate} />
            </List>
          )}

          <Divider sx={{ mt: 1 }} />
          <Box sx={{ px: 2, py: 1, display: "flex", alignItems: "center" }}>
            <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>
              Proyectos
            </Typography>
            <IconButton size="small" onClick={() => setProjectDialog(true)}>
              <Plus size={16} />
            </IconButton>
          </Box>
          <List>
            {projects.map((p) => (
              <ListItemButton
                key={p.id}
                selected={location.pathname === `/app/project/${p.id}`}
                onClick={() => navigate(`/app/project/${p.id}?view=${view}`)}
              >
                <ListItemIcon>
                  <Folder size={18} color={p.color} />
                </ListItemIcon>
                <ListItemText
                  primary={p.name}
                  secondary={`${p.tasks_count} tareas`}
                  primaryTypographyProps={{ noWrap: true }}
                />
              </ListItemButton>
            ))}
            {projects.length === 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1 }}>
                Sin proyectos. Crea uno con +.
              </Typography>
            )}
          </List>
        </Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
        <Outlet />
      </Box>

      <PwaInstallPrompt />

      <Dialog open={projectDialog} onClose={() => setProjectDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>Nuevo proyecto</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
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
                label="Color"
                type="color"
                value={projectColor}
                onChange={(e) => setProjectColor(e.target.value)}
                sx={{ width: 80 }}
                InputLabelProps={{ shrink: true }}
              />
              <Chip label={projectName || "Vista previa"} sx={{ bgcolor: projectColor, color: "#fff" }} />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProjectDialog(false)}>Cancelar</Button>
          <Button variant="contained" disabled={!projectName.trim() || createProject.isPending} onClick={() => createProject.mutate()}>
            Crear
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

/* --- Componentes auxiliares para el sidebar --- */

function SectionHeader({
  label,
  collapsed,
  onToggle,
}: {
  label: string;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <Box
      onClick={onToggle}
      sx={{
        px: 2,
        pt: 2,
        pb: 0.5,
        display: "flex",
        alignItems: "center",
        cursor: "pointer",
        userSelect: "none",
        "&:hover": { bgcolor: "action.hover" },
      }}
    >
      <Typography
        variant="overline"
        color="text.secondary"
        sx={{ flex: 1, fontSize: "0.65rem", fontWeight: 700 }}
      >
        {label}
      </Typography>
      {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
    </Box>
  );
}

function NavItem({
  icon,
  label,
  path,
  current,
  navigate,
}: {
  icon: React.ReactNode;
  label: string;
  path: string;
  current: string;
  navigate: (to: string) => void;
}) {
  return (
    <ListItemButton
      selected={current === path}
      onClick={() => navigate(path)}
      sx={{ py: 0.75 }}
    >
      <ListItemIcon sx={{ minWidth: 36 }}>{icon}</ListItemIcon>
      <ListItemText
        primary={label}
        primaryTypographyProps={{ fontSize: "0.875rem", noWrap: true }}
      />
    </ListItemButton>
  );
}
