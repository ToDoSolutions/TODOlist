import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from "@mui/material";
import { Plus, Pencil, Trash2, Copy, FileText } from "lucide-react";
import { taskTemplatesApi } from "../api/resources";
import { notify } from "../notify";

interface TaskTemplate {
  id: number;
  name: string;
  description?: string;
  default_priority?: number;
  default_project?: number;
  default_project_name?: string;
  default_state?: string;
}

interface TemplateForm {
  name: string;
  description: string;
  default_priority: string;
  default_project_id: string;
  default_state: string;
}

const emptyForm: TemplateForm = {
  name: "",
  description: "",
  default_priority: "3",
  default_project_id: "",
  default_state: "todo",
};

interface OverrideForm {
  title: string;
  project_id: string;
}

const emptyOverride: OverrideForm = {
  title: "",
  project_id: "",
};

export default function TaskTemplatesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TaskTemplate | null>(null);
  const [form, setForm] = useState<TemplateForm>(emptyForm);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [createTaskFor, setCreateTaskFor] = useState<TaskTemplate | null>(null);
  const [override, setOverride] = useState<OverrideForm>(emptyOverride);

  const { data: templatesData, isLoading } = useQuery({
    queryKey: ["task-templates"],
    queryFn: taskTemplatesApi.list,
  });
  const templates: TaskTemplate[] = Array.isArray(templatesData)
    ? templatesData
    : (templatesData as any)?.results ?? [];

  const createMut = useMutation({
    mutationFn: () =>
      taskTemplatesApi.create({
        name: form.name.trim(),
        description: form.description,
        default_priority: Number(form.default_priority),
        default_project_id: form.default_project_id ? Number(form.default_project_id) : undefined,
        default_state: form.default_state,
      }),
    onSuccess: () => {
      notify.success("Plantilla creada");
      qc.invalidateQueries({ queryKey: ["task-templates"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo crear la plantilla"),
  });

  const updateMut = useMutation({
    mutationFn: (id: number) =>
      taskTemplatesApi.update(id, {
        name: form.name.trim(),
        description: form.description,
        default_priority: Number(form.default_priority),
        default_project_id: form.default_project_id ? Number(form.default_project_id) : undefined,
        default_state: form.default_state,
      }),
    onSuccess: () => {
      notify.success("Plantilla actualizada");
      qc.invalidateQueries({ queryKey: ["task-templates"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo actualizar la plantilla"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => taskTemplatesApi.delete(id),
    onSuccess: () => {
      notify.success("Plantilla eliminada");
      qc.invalidateQueries({ queryKey: ["task-templates"] });
      setDeleteId(null);
    },
    onError: () => notify.error("No se pudo eliminar la plantilla"),
  });

  const createTaskMut = useMutation({
    mutationFn: () => {
      const overrides: any = {};
      if (override.title.trim()) overrides.title = override.title.trim();
      if (override.project_id) overrides.project_id = Number(override.project_id);
      return taskTemplatesApi.createTask(createTaskFor!.id, overrides);
    },
    onSuccess: () => {
      notify.success("Tarea creada desde plantilla");
      setCreateTaskFor(null);
      setOverride(emptyOverride);
    },
    onError: () => notify.error("No se pudo crear la tarea"),
  });

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (t: TaskTemplate) => {
    setEditing(t);
    setForm({
      name: t.name,
      description: t.description ?? "",
      default_priority: String(t.default_priority ?? 3),
      default_project_id: t.default_project ? String(t.default_project) : "",
      default_state: t.default_state ?? "todo",
    });
    setOpen(true);
  };

  const save = () => {
    if (!form.name.trim()) return;
    if (editing) {
      updateMut.mutate(editing.id);
    } else {
      createMut.mutate();
    }
  };

  const openCreateTask = (t: TaskTemplate) => {
    setCreateTaskFor(t);
    setOverride(emptyOverride);
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h5" fontWeight={700}>
          Plantillas de tareas
        </Typography>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          Nueva plantilla
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : templates.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <FileText size={32} style={{ color: "#bbb" }} />
          <Typography color="text.secondary" mt={1}>
            No hay plantillas. Crea la primera para generar tareas rápidamente.
          </Typography>
        </Paper>
      ) : (
        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Nombre</TableCell>
                <TableCell>Descripción</TableCell>
                <TableCell>Prioridad</TableCell>
                <TableCell>Proyecto</TableCell>
                <TableCell align="right">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {templates.map((t) => (
                <TableRow key={t.id} hover>
                  <TableCell>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <FileText size={14} style={{ color: "#888" }} />
                      <Typography variant="body2" fontWeight={600}>
                        {t.name}
                      </Typography>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary" noWrap maxWidth={220}>
                      {t.description || "—"}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={`P${t.default_priority ?? "—"}`} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {t.default_project_name ?? (t.default_project ? `#${t.default_project}` : "—")}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Crear tarea desde plantilla">
                      <IconButton size="small" onClick={() => openCreateTask(t)}>
                        <Copy size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Editar">
                      <IconButton size="small" onClick={() => openEdit(t)}>
                        <Pencil size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Eliminar">
                      <IconButton size="small" onClick={() => setDeleteId(t.id)}>
                        <Trash2 size={16} />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>
          {editing ? "Editar plantilla" : "Nueva plantilla"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              fullWidth
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              autoFocus
            />
            <TextField
              label="Descripción"
              fullWidth
              multiline
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <TextField
              label="Prioridad por defecto"
              fullWidth
              type="number"
              value={form.default_priority}
              onChange={(e) => setForm({ ...form, default_priority: e.target.value })}
            />
            <TextField
              label="ID de proyecto por defecto"
              fullWidth
              type="number"
              value={form.default_project_id}
              onChange={(e) => setForm({ ...form, default_project_id: e.target.value })}
            />
            <TextField
              label="Estado por defecto"
              fullWidth
              value={form.default_state}
              onChange={(e) => setForm({ ...form, default_state: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={save} disabled={!form.name.trim()}>
            {editing ? "Guardar" : "Crear"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create task from template dialog */}
      <Dialog
        open={createTaskFor !== null}
        onClose={() => setCreateTaskFor(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Crear tarea desde plantilla</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Plantilla: <strong>{createTaskFor?.name}</strong>. Los campos son opcionales; si los
            dejas vacíos se usarán los valores por defecto de la plantilla.
          </Typography>
          <Stack spacing={2}>
            <TextField
              label="Título (sobrescribir)"
              fullWidth
              value={override.title}
              onChange={(e) => setOverride({ ...override, title: e.target.value })}
              autoFocus
            />
            <TextField
              label="ID de proyecto (sobrescribir)"
              fullWidth
              type="number"
              value={override.project_id}
              onChange={(e) => setOverride({ ...override, project_id: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateTaskFor(null)}>Cancelar</Button>
          <Button variant="contained" onClick={() => createTaskMut.mutate()}>
            Crear tarea
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs">
        <DialogTitle>Eliminar plantilla</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            ¿Seguro que deseas eliminar esta plantilla? Esta acción no se puede deshacer.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>Cancelar</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
          >
            Eliminar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
