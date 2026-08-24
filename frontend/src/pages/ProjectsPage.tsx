import { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Grid,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Folder } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { projectsApi } from "../api/resources";
import type { Project } from "../types";
import { notify } from "../notify";

interface ProjectForm {
  name: string;
  description: string;
  color: string;
}

const emptyForm: ProjectForm = {
  name: "",
  description: "",
  color: "#1976d2",
};

export default function ProjectsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProjectForm>(emptyForm);

  const { data: projects = [], isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  const createMut = useMutation({
    mutationFn: () => projectsApi.create(form),
    onSuccess: () => {
      notify.success("Proyecto creado");
      qc.invalidateQueries({ queryKey: ["projects"] });
      setDialogOpen(false);
      setForm(emptyForm);
    },
    onError: () => notify.error("Error al crear proyecto"),
  });

  const updateMut = useMutation({
    mutationFn: () => projectsApi.update(editingId!, form),
    onSuccess: () => {
      notify.success("Proyecto actualizado");
      qc.invalidateQueries({ queryKey: ["projects"] });
      setEditOpen(false);
      setEditingId(null);
      setForm(emptyForm);
    },
    onError: () => notify.error("Error al actualizar proyecto"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => projectsApi.remove(id),
    onSuccess: () => {
      notify.info("Proyecto eliminado");
      qc.invalidateQueries({ queryKey: ["projects"] });
      setDeleteId(null);
    },
    onError: () => notify.error("Error al eliminar proyecto"),
  });

  const openEdit = (project: Project) => {
    setEditingId(project.id);
    setForm({
      name: project.name,
      description: project.description,
      color: project.color,
    });
    setEditOpen(true);
  };

  const projectToDelete = projects.find((p) => p.id === deleteId);

  return (
    <Box maxWidth={1100} mx="auto">
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={700}>
          Proyectos
        </Typography>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={() => {
            setForm(emptyForm);
            setDialogOpen(true);
          }}
        >
          Nuevo proyecto
        </Button>
      </Stack>

      {isLoading && (
        <Stack alignItems="center" py={6}>
          <CircularProgress />
        </Stack>
      )}

      {error && !isLoading && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Error al cargar los proyectos.
        </Alert>
      )}

      {!isLoading && projects.length === 0 && !error && (
        <Alert severity="info">
          No hay proyectos todavía. Crea tu primer proyecto con el botón "Nuevo proyecto".
        </Alert>
      )}

      {!isLoading && projects.length > 0 && (
        <Grid container spacing={2}>
          {projects.map((project) => (
            <Grid key={project.id} item xs={12} sm={6} md={4}>
              <Paper
                variant="outlined"
                onClick={() => navigate(`/app/project/${project.id}`)}
                sx={{
                  p: 2,
                  cursor: "pointer",
                  height: "100%",
                  transition: "all 0.2s ease",
                  "&:hover": {
                    borderColor: project.color,
                    boxShadow: 3,
                  },
                }}
              >
                <Stack direction="row" alignItems="flex-start" spacing={1.5}>
                  <Folder size={24} color={project.color} style={{ flexShrink: 0, marginTop: 2 }} />
                  <Box flex={1} minWidth={0}>
                    <Stack direction="row" alignItems="center" justifyContent="space-between">
                      <Typography variant="h6" noWrap sx={{ fontWeight: 600 }}>
                        {project.name}
                      </Typography>
                      <Stack direction="row" spacing={0.5} onClick={(e) => e.stopPropagation()}>
                        <Tooltip title="Editar">
                          <IconButton size="small" onClick={() => openEdit(project)}>
                            <Pencil size={16} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Eliminar">
                          <IconButton size="small" onClick={() => setDeleteId(project.id)}>
                            <Trash2 size={16} />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </Stack>

                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        mt: 0.5,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                        minHeight: 40,
                      }}
                    >
                      {project.description || "Sin descripción"}
                    </Typography>

                    <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 1.5 }}>
                      <Chip
                        size="small"
                        label={`${project.tasks_count ?? 0} tareas`}
                        variant="outlined"
                      />
                      <Chip
                        size="small"
                        label={`${project.sprints_count ?? 0} sprints`}
                        variant="outlined"
                      />
                      <Chip
                        size="small"
                        label={`${project.epics_count ?? 0} épicas`}
                        variant="outlined"
                      />
                      {project.is_archived && (
                        <Chip size="small" label="Archivado" color="default" />
                      )}
                      <Box
                        sx={{
                          width: 14,
                          height: 14,
                          borderRadius: "50%",
                          bgcolor: project.color,
                          ml: "auto",
                          border: "1px solid rgba(0,0,0,0.1)",
                        }}
                      />
                    </Stack>
                  </Box>
                </Stack>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Create dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Nuevo proyecto</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              autoFocus
            />
            <TextField
              label="Descripción"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="body2">Color:</Typography>
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                style={{ width: 50, height: 30, border: "none", cursor: "pointer" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() => createMut.mutate()}
            disabled={!form.name || createMut.isPending}
          >
            Crear
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Editar proyecto</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              autoFocus
            />
            <TextField
              label="Descripción"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="body2">Color:</Typography>
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                style={{ width: 50, height: 30, border: "none", cursor: "pointer" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() => updateMut.mutate()}
            disabled={!form.name || updateMut.isPending}
          >
            Guardar
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Eliminar proyecto</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            ¿Seguro que deseas eliminar{" "}
            <strong>{projectToDelete?.name ?? "este proyecto"}</strong>? Esta acción no se puede
            deshacer.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>Cancelar</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
            disabled={deleteMut.isPending}
          >
            Eliminar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
