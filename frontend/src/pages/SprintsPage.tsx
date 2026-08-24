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
  IconButton,
  Tooltip,
  Alert,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Divider,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Flag,
  Plus,
  Trash2,
  Play,
  CheckCircle,
  Calendar,
  Target,
  ArrowRight,
  Pencil,
} from "lucide-react";
import { sprintsApi, type Sprint } from "../api/resources";
import { notify } from "../notify";

function formatDate(d: Date) {
  return d.toISOString().split("T")[0];
}

export default function SprintsPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [closeDialog, setCloseDialog] = useState<Sprint | null>(null);
  const [editDialog, setEditDialog] = useState<Sprint | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    goal: "",
    start_date: formatDate(new Date()),
    end_date: formatDate(new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)),
  });
  const [form, setForm] = useState({
    name: "",
    goal: "",
    start_date: formatDate(new Date()),
    end_date: formatDate(new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)),
  });

  const { data: sprints = [], isLoading } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
  });

  const createMut = useMutation({
    mutationFn: () => sprintsApi.create(form),
    onSuccess: () => {
      notify.success("Sprint creado");
      qc.invalidateQueries({ queryKey: ["sprints"] });
      setDialogOpen(false);
      setForm({
        name: "",
        goal: "",
        start_date: formatDate(new Date()),
        end_date: formatDate(new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)),
      });
    },
    onError: () => notify.error("Error al crear sprint"),
  });

  const activateMut = useMutation({
    mutationFn: (id: number) => sprintsApi.update(id, { state: "active" }),
    onSuccess: () => {
      notify.success("Sprint activado");
      qc.invalidateQueries({ queryKey: ["sprints"] });
    },
  });

  const closeMut = useMutation({
    mutationFn: ({ id, nextId }: { id: number; nextId?: number }) =>
      sprintsApi.close(id, nextId),
    onSuccess: (data) => {
      notify.success(data.message);
      qc.invalidateQueries({ queryKey: ["sprints"] });
      setCloseDialog(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: sprintsApi.remove,
    onSuccess: () => {
      notify.info("Sprint eliminado");
      qc.invalidateQueries({ queryKey: ["sprints"] });
    },
  });

  const editMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Sprint> }) =>
      sprintsApi.update(id, data),
    onSuccess: () => {
      notify.success("Sprint actualizado");
      qc.invalidateQueries({ queryKey: ["sprints"] });
      setEditDialog(null);
    },
    onError: () => notify.error("Error al actualizar sprint"),
  });

  const openEdit = (sprint: Sprint) => {
    setEditDialog(sprint);
    setEditForm({
      name: sprint.name,
      goal: sprint.goal,
      start_date: sprint.start_date,
      end_date: sprint.end_date,
    });
  };

  const stateColors: Record<string, "default" | "primary" | "success"> = {
    planned: "default",
    active: "primary",
    closed: "success",
  };

  const stateLabels: Record<string, string> = {
    planned: "Planificado",
    active: "Activo",
    closed: "Cerrado",
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={700}>
          Sprints
        </Typography>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={() => setDialogOpen(true)}
        >
          Nuevo sprint
        </Button>
      </Stack>

      {isLoading && <LinearProgress />}

      {sprints.length === 0 && !isLoading && (
        <Alert severity="info">
          No hay sprints. Crea tu primer sprint para empezar a planificar.
        </Alert>
      )}

      <Stack spacing={2}>
        {sprints.map((sprint) => (
          <Card key={sprint.id} variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="flex-start" spacing={2}>
                <Flag size={24} color="#1976d2" />
                <Box flex={1}>
                  <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                    <Typography variant="h6">{sprint.name}</Typography>
                    <Chip
                      label={stateLabels[sprint.state]}
                      color={stateColors[sprint.state]}
                      size="small"
                    />
                    <Chip
                      icon={<Calendar size={14} />}
                      label={`${sprint.start_date} → ${sprint.end_date}`}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={`${sprint.task_count} tareas`}
                      size="small"
                      variant="outlined"
                    />
                  </Stack>
                  {sprint.goal && (
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <Target size={16} color="#666" />
                      <Typography variant="body2" color="text.secondary">
                        {sprint.goal}
                      </Typography>
                    </Stack>
                  )}
                  <Stack direction="row" spacing={1} mt={1}>
                    {sprint.state === "planned" && (
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Play size={16} />}
                        onClick={() => activateMut.mutate(sprint.id)}
                      >
                        Activar
                      </Button>
                    )}
                    {sprint.state === "active" && (
                      <Button
                        size="small"
                        variant="outlined"
                        color="success"
                        startIcon={<CheckCircle size={16} />}
                        onClick={() => setCloseDialog(sprint)}
                      >
                        Cerrar
                      </Button>
                    )}
                    <Tooltip title="Editar">
                      <IconButton
                        size="small"
                        onClick={() => openEdit(sprint)}
                      >
                        <Pencil size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Eliminar">
                      <IconButton
                        size="small"
                        onClick={() => deleteMut.mutate(sprint.id)}
                      >
                        <Trash2 size={16} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>

      {/* Dialog crear sprint */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Nuevo sprint</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
            />
            <TextField
              label="Objetivo"
              value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })}
              fullWidth
              multiline
              rows={2}
            />
            <TextField
              label="Fecha de inicio"
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="Fecha de fin"
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
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

      {/* Dialog editar sprint */}
      <Dialog
        open={!!editDialog}
        onClose={() => setEditDialog(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Editar sprint</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              value={editForm.name}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              fullWidth
            />
            <TextField
              label="Objetivo"
              value={editForm.goal}
              onChange={(e) => setEditForm({ ...editForm, goal: e.target.value })}
              fullWidth
              multiline
              rows={2}
            />
            <TextField
              label="Fecha de inicio"
              type="date"
              value={editForm.start_date}
              onChange={(e) => setEditForm({ ...editForm, start_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="Fecha de fin"
              type="date"
              value={editForm.end_date}
              onChange={(e) => setEditForm({ ...editForm, end_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog(null)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={() =>
              editDialog &&
              editMut.mutate({ id: editDialog.id, data: editForm })
            }
            disabled={!editForm.name || editMut.isPending}
          >
            Guardar
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog cerrar sprint */}
      <Dialog open={!!closeDialog} onClose={() => setCloseDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Cerrar sprint "{closeDialog?.name}"</DialogTitle>
        <DialogContent>
          <Typography variant="body2" mb={2}>
            Las tareas no completadas pueden moverse al siguiente sprint.
          </Typography>
          <List dense>
            {sprints
              .filter((s) => s.state === "planned" && s.id !== closeDialog?.id)
              .map((s) => (
                <ListItemButton
                  key={s.id}
                  onClick={() =>
                    closeDialog &&
                    closeMut.mutate({ id: closeDialog.id, nextId: s.id })
                  }
                >
                  <ListItemIcon>
                    <ArrowRight size={20} />
                  </ListItemIcon>
                  <ListItemText
                    primary={s.name}
                    secondary={`Mover tareas incompletas a este sprint (${s.start_date} → ${s.end_date})`}
                  />
                </ListItemButton>
              ))}
            {sprints.filter((s) => s.state === "planned").length === 0 && (
              <ListItemButton>
                <ListItemText
                  primary="No hay sprints planificados"
                  secondary="Las tareas incompletas quedarán sin sprint asignado"
                />
              </ListItemButton>
            )}
          </List>
          <Divider sx={{ my: 1 }} />
          <Button
            fullWidth
            onClick={() => closeDialog && closeMut.mutate({ id: closeDialog.id })}
          >
            Cerrar sin mover tareas
          </Button>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
