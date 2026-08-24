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
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from "@mui/material";
import { Plus, Trash2, Settings } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { customFieldsApi, projectsApi } from "../api/resources";
import { notify } from "../notify";

const FIELD_TYPES = ["text", "number", "select", "multiselect", "date"] as const;
type FieldType = (typeof FIELD_TYPES)[number];

export default function CustomFieldsPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<{ project_id: string; name: string; type: FieldType; options: string }>({
    project_id: "",
    name: "",
    type: "text",
    options: "",
  });

  // Task values section
  const [taskIdInput, setTaskIdInput] = useState("");
  const [taskId, setTaskId] = useState<number | null>(null);
  const [valueForm, setValueForm] = useState<{ fieldId: number; value: string }>({
    fieldId: 0,
    value: "",
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : (projectsData as any)?.results || [];
  const projectMap = new Map(projects.map((p: any) => [p.id, p.name]));

  const { data: fields, isLoading } = useQuery({
    queryKey: ["custom-fields"],
    queryFn: customFieldsApi.list,
  });

  const { data: valuesData, isLoading: valuesLoading } = useQuery({
    queryKey: ["custom-field-values", taskId],
    queryFn: () => customFieldsApi.values(),
    enabled: !!taskId,
  });

  const createMut = useMutation({
    mutationFn: customFieldsApi.create,
    onSuccess: () => {
      notify.success("Campo personalizado creado");
      qc.invalidateQueries({ queryKey: ["custom-fields"] });
      setDialogOpen(false);
    },
    onError: () => notify.error("Error al crear campo"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => customFieldsApi.remove(id),
    onSuccess: () => {
      notify.info("Campo eliminado");
      qc.invalidateQueries({ queryKey: ["custom-fields"] });
      setDeleteId(null);
    },
    onError: () => notify.error("Error al eliminar campo"),
  });

  const setValueMut = useMutation({
    mutationFn: (data: { task: number; field: number; value: string }) =>
      customFieldsApi.setValue(data),
    onSuccess: () => {
      notify.success("Valor actualizado");
      qc.invalidateQueries({ queryKey: ["custom-field-values", taskId] });
      setValueForm({ fieldId: 0, value: "" });
    },
    onError: () => notify.error("Error al actualizar valor"),
  });

  const handleCreate = () => {
    const payload: any = { name: form.name, type: form.type, project: Number(form.project_id) };
    if (form.type === "select" || form.type === "multiselect") {
      payload.options = form.options
        .split(",")
        .map((o) => o.trim())
        .filter(Boolean);
    }
    createMut.mutate(payload);
  };

  const fieldList: any[] = Array.isArray(fields) ? fields : (fields as any)?.results || [];
  const allValues: any[] = valuesData || [];
  const taskValues = taskId
    ? allValues.filter((v) => v.task === taskId)
    : [];

  const loadTaskValues = () => {
    const id = Number(taskIdInput);
    if (!id) {
      notify.warning("Ingresa un ID de tarea válido");
      return;
    }
    setTaskId(id);
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Alert severity="info" sx={{ mb: 3 }}>
        Los campos personalizados permiten añadir información extra a tus tareas más allá de los campos estándar. Por ejemplo: Cliente, Tipo de bug, Severidad, Sprint objetivo, etc.
      </Alert>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Settings size={24} color="#1976d2" />
          <Typography variant="h5" fontWeight={700}>Campos personalizados</Typography>
        </Stack>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={() => { setForm({ project_id: "", name: "", type: "text", options: "" }); setDialogOpen(true); }}
        >
          Nuevo campo
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : fieldList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Settings size={48} color="#ccc" />
          <Typography color="text.secondary" mt={1}>
            No hay campos personalizados. Crea uno para empezar.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {fieldList.map((f: any) => (
            <Paper key={f.id} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between">
                <Box>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography variant="subtitle1" fontWeight={600}>{f.name}</Typography>
                    <Chip
                      size="small"
                      label={f.type}
                      sx={{ height: 20, fontSize: 11 }}
                      color="primary"
                      variant="outlined"
                    />
                    {f.project && (
                      <Chip
                        size="small"
                        label={String(projectMap.get(f.project) || `Proyecto #${f.project}`)}
                        sx={{ height: 20, fontSize: 11 }}
                        variant="outlined"
                      />
                    )}
                  </Stack>
                  {(f.type === "select" || f.type === "multiselect") && (
                    <Stack direction="row" spacing={0.5} mt={1} flexWrap="wrap" useFlexGap>
                      {(f.options || []).map((o: string) => (
                        <Chip key={o} size="small" label={o} sx={{ height: 20, fontSize: 10 }} variant="outlined" />
                      ))}
                    </Stack>
                  )}
                </Box>
                <Tooltip title="Eliminar">
                  <IconButton size="small" color="error" onClick={() => setDeleteId(f.id)}>
                    <Trash2 size={16} />
                  </IconButton>
                </Tooltip>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Sección de valores por tarea */}
      <Paper variant="outlined" sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" fontWeight={700} mb={2}>
          Valores por tarea
        </Typography>
        <Stack direction="row" spacing={1} mb={2}>
          <TextField
            label="ID de tarea"
            value={taskIdInput}
            onChange={(e) => setTaskIdInput(e.target.value)}
            size="small"
            type="number"
          />
          <Button variant="outlined" onClick={loadTaskValues}>
            Cargar valores
          </Button>
        </Stack>

        {taskId && (
          valuesLoading ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : taskValues.length === 0 ? (
            <Alert severity="info">
              Esta tarea no tiene valores asignados para campos personalizados.
            </Alert>
          ) : (
            <Stack spacing={1} mb={3}>
              {taskValues.map((v: any) => {
                const field = fieldList.find((f) => f.id === v.field);
                return (
                  <Stack
                    key={v.id ?? `${v.field}-${v.value}`}
                    direction="row"
                    alignItems="center"
                    justifyContent="space-between"
                    sx={{ py: 0.5 }}
                  >
                    <Typography variant="body2">
                      <strong>{field?.name ?? `Campo ${v.field}`}:</strong>{" "}
                      {String(v.value_text ?? v.value ?? "")}
                    </Typography>
                  </Stack>
                );
              })}
            </Stack>
          )
        )}

        {taskId && fieldList.length > 0 && (
          <Stack direction="row" spacing={1} alignItems="center">
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Campo</InputLabel>
              <Select
                value={valueForm.fieldId}
                label="Campo"
                onChange={(e) => setValueForm({ ...valueForm, fieldId: e.target.value as number })}
              >
                <MenuItem value={0} disabled>Selecciona un campo</MenuItem>
                {fieldList.map((f: any) => (
                  <MenuItem key={f.id} value={f.id}>{f.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Valor"
              value={valueForm.value}
              onChange={(e) => setValueForm({ ...valueForm, value: e.target.value })}
              size="small"
            />
            <Button
              variant="contained"
              disabled={!valueForm.fieldId || setValueMut.isPending}
              onClick={() =>
                setValueMut.mutate({
                  task: taskId,
                  field: valueForm.fieldId,
                  value: valueForm.value,
                })
              }
            >
              Guardar
            </Button>
          </Stack>
        )}
      </Paper>

      {/* Dialog de creación */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Crear campo personalizado</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl fullWidth size="small" required>
              <InputLabel>Proyecto</InputLabel>
              <Select
                value={form.project_id}
                label="Proyecto *"
                onChange={(e) => setForm({ ...form, project_id: e.target.value as string })}
              >
                <MenuItem value="" disabled>Selecciona un proyecto</MenuItem>
                {projects.map((p: any) => (
                  <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Alert severity="info">
              Los campos personalizados se definen por proyecto y permiten añadir metadata extra a las tareas (ej: Cliente, Tipo de bug, Severidad)
            </Alert>
            <TextField
              label="Nombre"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              size="small"
            />
            <FormControl fullWidth size="small">
              <InputLabel>Tipo</InputLabel>
              <Select
                value={form.type}
                label="Tipo"
                onChange={(e) => setForm({ ...form, type: e.target.value as FieldType, options: "" })}
              >
                {FIELD_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>{t}</MenuItem>
                ))}
              </Select>
            </FormControl>
            {(form.type === "select" || form.type === "multiselect") && (
              <TextField
                label="Opciones (separadas por comas)"
                value={form.options}
                onChange={(e) => setForm({ ...form, options: e.target.value })}
                fullWidth
                size="small"
                helperText="Ej: Alta, Media, Baja"
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!form.name || !form.project_id || createMut.isPending}
          >
            Crear
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmación de borrado */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Eliminar campo</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            ¿Seguro que deseas eliminar este campo personalizado? Esta acción no se puede deshacer.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>Cancelar</Button>
          <Button
            variant="contained"
            color="error"
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
