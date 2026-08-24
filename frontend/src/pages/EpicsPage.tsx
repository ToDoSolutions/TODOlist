import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  LinearProgress,
  IconButton,
  Tooltip,
  Alert,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, Trash2, Pencil, Eye } from "lucide-react";
import { epicsApi, projectsApi, type Epic } from "../api/resources";
import type { Task } from "../types";
import { STATE_LABELS, PRIORITY_LABELS } from "../types";
import { notify } from "../notify";
import { useProject } from "../auth/ProjectContext";

const EPIC_STATES: Epic["state"][] = ["planned", "in_progress", "completed", "cancelled"];

interface EpicForm {
  title: string;
  description: string;
  color: string;
  state: Epic["state"];
  start_date: string;
  end_date: string;
  project_id: string;
}

const emptyForm: EpicForm = {
  title: "",
  description: "",
  color: "#9c27b0",
  state: "planned",
  start_date: "",
  end_date: "",
  project_id: "",
};

export default function EpicsPage() {
  const qc = useQueryClient();
  const { project: ctxProject } = useProject();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [viewTasksEpic, setViewTasksEpic] = useState<Epic | null>(null);
  const [form, setForm] = useState<EpicForm>(emptyForm);

  const { data: epics = [], isLoading } = useQuery({
    queryKey: ["epics"],
    queryFn: epicsApi.list,
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData)
    ? projectsData
    : (projectsData as any)?.results || [];

  const { data: epicTasks = [], isLoading: isLoadingEpicTasks } = useQuery({
    queryKey: ["epic-tasks", viewTasksEpic?.id],
    queryFn: () => epicsApi.getTasks(viewTasksEpic!.id),
    enabled: !!viewTasksEpic,
  });

  const createMut = useMutation({
    mutationFn: () =>
      epicsApi.create({
        ...form,
        project_id: form.project_id ? Number(form.project_id) : null,
      } as any),
    onSuccess: () => {
      notify.success("Épica creada");
      qc.invalidateQueries({ queryKey: ["epics"] });
      setDialogOpen(false);
      setForm(emptyForm);
    },
    onError: () => notify.error("Error al crear épica"),
  });

  const updateMut = useMutation({
    mutationFn: () =>
      epicsApi.update(editingId!, {
        ...form,
        project_id: form.project_id ? Number(form.project_id) : null,
      } as any),
    onSuccess: () => {
      notify.success("Épica actualizada");
      qc.invalidateQueries({ queryKey: ["epics"] });
      setEditOpen(false);
      setEditingId(null);
      setForm(emptyForm);
    },
    onError: () => notify.error("Error al actualizar épica"),
  });

  const deleteMut = useMutation({
    mutationFn: epicsApi.remove,
    onSuccess: () => {
      notify.info("Épica eliminada");
      qc.invalidateQueries({ queryKey: ["epics"] });
    },
    onError: () => notify.error("Error al eliminar épica"),
  });

  const stateLabels: Record<string, string> = {
    planned: "Planificada",
    in_progress: "En progreso",
    completed: "Completada",
    cancelled: "Cancelada",
  };

  const stateColors: Record<string, "default" | "primary" | "success" | "error"> = {
    planned: "default",
    in_progress: "primary",
    completed: "success",
    cancelled: "error",
  };

  const openEdit = (epic: Epic) => {
    setEditingId(epic.id);
    setForm({
      title: epic.title,
      description: epic.description,
      color: epic.color,
      state: epic.state,
      start_date: epic.start_date ?? "",
      end_date: epic.end_date ?? "",
      project_id: epic.project != null ? String(epic.project) : "",
    });
    setEditOpen(true);
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={700}>
          Épicas
        </Typography>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={() => {
            setForm({ ...emptyForm, project_id: ctxProject ? String(ctxProject.id) : "" });
            setDialogOpen(true);
          }}
        >
          Nueva épica
        </Button>
      </Stack>

      {isLoading && <LinearProgress />}

      {epics.length === 0 && !isLoading && (
        <Alert severity="info">
          No hay épicas. Las épicas agrupan tareas relacionadas para rastrear el progreso de iniciativas grandes.
        </Alert>
      )}

      <Stack spacing={2}>
        {epics.map((epic) => {
          const pct =
            epic.progress_total > 0
              ? Math.round((epic.progress_done / epic.progress_total) * 100)
              : 0;
          return (
            <Card key={epic.id} variant="outlined">
              <CardContent>
                <Stack direction="row" alignItems="flex-start" spacing={2}>
                  <Layers size={24} color={epic.color} />
                  <Box flex={1}>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <Typography variant="h6">{epic.title}</Typography>
                      <Chip
                        label={stateLabels[epic.state]}
                        color={stateColors[epic.state]}
                        size="small"
                      />
                    </Stack>
                    {epic.description && (
                      <Typography variant="body2" color="text.secondary" mb={1}>
                        {epic.description}
                      </Typography>
                    )}
                    <Stack direction="row" alignItems="center" spacing={1} mt={1}>
                      <Box flex={1}>
                        <LinearProgress
                          variant="determinate"
                          value={pct}
                          sx={{
                            height: 8,
                            borderRadius: 4,
                            "& .MuiLinearProgress-bar": { bgcolor: epic.color },
                          }}
                        />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {epic.progress_done}/{epic.progress_total} ({pct}%)
                      </Typography>
                      <Tooltip title="Ver tareas">
                        <IconButton size="small" onClick={() => setViewTasksEpic(epic)}>
                          <Eye size={16} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Editar">
                        <IconButton size="small" onClick={() => openEdit(epic)}>
                          <Pencil size={16} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Eliminar">
                        <IconButton size="small" onClick={() => deleteMut.mutate(epic.id)}>
                          <Trash2 size={16} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          );
        })}
      </Stack>

      {/* Create dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Nueva épica</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Título"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              fullWidth
            />
            <TextField
              label="Descripción"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <FormControl fullWidth>
              <InputLabel>Proyecto</InputLabel>
              <Select
                label="Proyecto"
                value={form.project_id}
                onChange={(e) =>
                  setForm({ ...form, project_id: e.target.value as string })
                }
              >
                <MenuItem value="">
                  <em>Sin proyecto</em>
                </MenuItem>
                {projects.map((p: any) => (
                  <MenuItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
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
            disabled={!form.title || createMut.isPending}
          >
            Crear
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Editar épica</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Título"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              fullWidth
            />
            <TextField
              label="Descripción"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <FormControl fullWidth>
              <InputLabel>Proyecto</InputLabel>
              <Select
                label="Proyecto"
                value={form.project_id}
                onChange={(e) =>
                  setForm({ ...form, project_id: e.target.value as string })
                }
              >
                <MenuItem value="">
                  <em>Sin proyecto</em>
                </MenuItem>
                {projects.map((p: any) => (
                  <MenuItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Estado</InputLabel>
              <Select
                label="Estado"
                value={form.state}
                onChange={(e) =>
                  setForm({ ...form, state: e.target.value as Epic["state"] })
                }
              >
                {EPIC_STATES.map((s) => (
                  <MenuItem key={s} value={s}>
                    {stateLabels[s]}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="body2">Color:</Typography>
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                style={{ width: 50, height: 30, border: "none", cursor: "pointer" }}
              />
            </Stack>
            <TextField
              label="Fecha de inicio"
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="Fecha de fin"
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() => updateMut.mutate()}
            disabled={!form.title || updateMut.isPending}
          >
            Guardar
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog ver tareas de la épica */}
      <Dialog
        open={!!viewTasksEpic}
        onClose={() => setViewTasksEpic(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Tareas de "{viewTasksEpic?.title}" ({epicTasks.length})
        </DialogTitle>
        <DialogContent>
          {isLoadingEpicTasks ? (
            <Stack alignItems="center" sx={{ py: 3 }}>
              <CircularProgress size={32} />
            </Stack>
          ) : epicTasks.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No hay tareas en esta épica.
            </Typography>
          ) : (
            <List dense>
              {epicTasks.map((task: Task) => (
                <ListItem
                  key={task.id}
                  sx={{ px: 0 }}
                  secondaryAction={
                    <Chip
                      label={PRIORITY_LABELS[task.priority]}
                      size="small"
                      variant="outlined"
                    />
                  }
                >
                  <ListItemText
                    primary={task.title}
                    secondary={
                      <Chip
                        label={STATE_LABELS[task.state]}
                        size="small"
                        sx={{ mt: 0.5 }}
                      />
                    }
                  />
                </ListItem>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewTasksEpic(null)}>Cerrar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
