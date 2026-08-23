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
} from "@mui/material";
import {
  CheckSquare,
  Inbox,
  LogOut,
  Plus,
  Columns,
  List as ListIcon,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "../api/resources";
import { useAuth } from "../auth/AuthContext";

const drawerWidth = 260;

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const createProject = useMutation({
    mutationFn: () =>
      projectsApi.create({
        name: `Proyecto ${projects.length + 1}`,
        description: "",
        color: "#1976d2",
      }),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/app/project/${p.id}`);
      setCreating(false);
    },
  });

  const params = new URLSearchParams(location.search);
  const view = params.get("view") || "list";

  const setView = (v: "list" | "kanban") => {
    const q = new URLSearchParams(params);
    q.set("view", v);
    navigate({ search: q.toString() });
  };

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
            <IconButton onClick={() => setView("list")} color={view === "list" ? "primary" : "default"}>
              <ListIcon size={20} />
            </IconButton>
            <IconButton onClick={() => setView("kanban")} color={view === "kanban" ? "primary" : "default"}>
              <Columns size={20} />
            </IconButton>
            <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
            <Avatar sx={{ width: 28, height: 28, bgcolor: "primary.main", fontSize: 13 }}>
              {user?.email?.[0]?.toUpperCase()}
            </Avatar>
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
            </ListItemButton>
          </List>
          <Divider />
          <Box sx={{ px: 2, py: 1, display: "flex", alignItems: "center" }}>
            <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>
              Proyectos
            </Typography>
            <IconButton size="small" onClick={() => setCreating(true)} disabled={creating}>
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
                  <Chip
                    size="small"
                    sx={{ bgcolor: p.color, color: "#fff", width: 12, height: 12 }}
                  />
                </ListItemIcon>
                <ListItemText
                  primary={p.name}
                  secondary={`${p.tasks_count} tareas`}
                  primaryTypographyProps={{ noWrap: true }}
                />
              </ListItemButton>
            ))}
            {creating && (
              <ListItemButton disabled>
                <ListItemText primary="Creando proyecto…" />
              </ListItemButton>
            )}
          </List>
        </Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
        <Outlet />
      </Box>
    </Box>
  );
}
