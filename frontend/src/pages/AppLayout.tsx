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
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi, tasksApi } from "../api/resources";
import { useAuth } from "../auth/AuthContext";
import { notify } from "../notify";
import { isPast, isToday } from "date-fns";

const drawerWidth = 260;

type View = "list" | "kanban" | "calendar";

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const [projectDialog, setProjectDialog] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectColor, setProjectColor] = useState("#1976d2");

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
        <Box sx={{ overflow: "auto" }}>
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
            <ListItemButton
              selected={location.pathname === "/app/tags"}
              onClick={() => navigate("/app/tags")}
            >
              <ListItemIcon>
                <TagIcon size={20} />
              </ListItemIcon>
              <ListItemText primary="Etiquetas" />
            </ListItemButton>
          </List>
          <Divider />
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
