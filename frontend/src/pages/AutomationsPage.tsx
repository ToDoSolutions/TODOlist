import { useState } from "react";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Switch,
  FormControlLabel,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Collapse,
} from "@mui/material";
import { Plus, Zap, Play, History, ChevronDown, ChevronRight, Trash2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { automationsApi } from "../api/resources";
import { notify } from "../notify";

const TRIGGER_LABELS: Record<string, string> = {
  task_created: "Tarea creada",
  task_state_changed: "Estado cambiado",
  task_completed: "Tarea completada",
  task_blocked: "Tarea bloqueada",
  task_overdue: "Tarea vencida",
  comment_added: "Comentario añadido",
  sprint_started: "Sprint iniciado",
  sprint_closed: "Sprint cerrado",
  daily_check: "Chequeo diario",
};

const ACTION_LABELS: Record<string, string> = {
  set_priority: "Cambiar prioridad",
  set_state: "Cambiar estado",
  set_assignee: "Asignar responsable",
  add_tag: "Añadir etiqueta",
  set_due_date: "Establecer fecha límite",
  move_to_sprint: "Mover a sprint",
  subtasks_in_progress: "Subtareas a in_progress",
  create_notification: "Crear notificación",
  create_task: "Crear tarea",
};

export default function AutomationsPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    trigger: "task_blocked",
    action: "set_priority",
    action_params: '{"priority": 0}',
    conditions: "[]",
    enabled: true,
  });

  const { data: rules, isLoading } = useQuery({
    queryKey: ["automation-rules"],
    queryFn: automationsApi.list,
  });

  const { data: logs } = useQuery({
    queryKey: ["automation-logs", expandedId],
    queryFn: () => automationsApi.logs(expandedId!),
    enabled: expandedId !== null,
  });

  const createMut = useMutation({
    mutationFn: automationsApi.create,
    onSuccess: () => {
      notify.success("Regla creada");
      qc.invalidateQueries({ queryKey: ["automation-rules"] });
      setDialogOpen(false);
    },
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      automationsApi.update(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automation-rules"] }),
  });

  const testMut = useMutation({
    mutationFn: automationsApi.test,
    onSuccess: (data) => {
      notify.info(`Ejecutada: ${JSON.stringify(data.results)}`);
    },
  });

  const deleteMut = useMutation({
    mutationFn: automationsApi.delete,
    onSuccess: () => {
      notify.info("Regla eliminada");
      qc.invalidateQueries({ queryKey: ["automation-rules"] });
    },
  });

  const handleCreate = () => {
    try {
      const action_params = JSON.parse(form.action_params);
      const conditions = JSON.parse(form.conditions);
      createMut.mutate({
        name: form.name,
        description: form.description,
        trigger: form.trigger,
        action: form.action,
        action_params,
        conditions,
        enabled: form.enabled,
      });
    } catch {
      notify.error("JSON inválido en action_params o conditions");
    }
  };

  const ruleList = rules?.results || rules || [];

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Zap size={24} color="#7c4dff" />
          <Typography variant="h5" fontWeight={700}>Automatizaciones</Typography>
        </Stack>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={() => setDialogOpen(true)}>
          Nueva regla
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : ruleList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Zap size={48} color="#ccc" />
          <Typography color="text.secondary" mt={1}>
            No hay automatizaciones. Crea tu primera regla para automatizar tu flujo.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={1.5}>
          {ruleList.map((rule: any) => (
            <Paper key={rule.id} variant="outlined">
              <Stack
                direction="row"
                alignItems="center"
                spacing={1.5}
                sx={{ p: 2, cursor: "pointer" }}
                onClick={() => setExpandedId(expandedId === rule.id ? null : rule.id)}
              >
                {expandedId === rule.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                <Box flex={1}>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {rule.name}
                  </Typography>
                  <Stack direction="row" spacing={0.5} mt={0.5} flexWrap="wrap" useFlexGap>
                    <Chip
                      size="small"
                      label={`Trigger: ${TRIGGER_LABELS[rule.trigger] || rule.trigger}`}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                    />
                    <Chip
                      size="small"
                      label={`Acción: ${ACTION_LABELS[rule.action] || rule.action}`}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                      color="secondary"
                    />
                    <Chip
                      size="small"
                      label={`${rule.trigger_count} ejecuciones`}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                    />
                  </Stack>
                </Box>
                <FormControlLabel
                  control={
                    <Switch
                      size="small"
                      checked={rule.enabled}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleMut.mutate({ id: rule.id, enabled: e.target.checked });
                      }}
                    />
                  }
                  label=""
                  onClick={(e) => e.stopPropagation()}
                />
                <Tooltip title="Probar">
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      testMut.mutate(rule.id);
                    }}
                  >
                    <Play size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Eliminar">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteMut.mutate(rule.id);
                    }}
                  >
                    <Trash2 size={16} />
                  </IconButton>
                </Tooltip>
              </Stack>
              <Collapse in={expandedId === rule.id}>
                <Box sx={{ p: 2, pt: 0 }}>
                  {rule.description && (
                    <Typography variant="body2" color="text.secondary" mb={1}>
                      {rule.description}
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary">
                    Condiciones: {JSON.stringify(rule.conditions)}
                  </Typography>
                  <br />
                  <Typography variant="caption" color="text.secondary">
                    Parámetros: {JSON.stringify(rule.action_params)}
                  </Typography>
                  {rule.last_triggered_at && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      Última ejecución: {new Date(rule.last_triggered_at).toLocaleString("es-ES")}
                    </Typography>
                  )}
                  {/* Logs */}
                  <Box mt={2}>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <History size={14} />
                      <Typography variant="subtitle2">Historial</Typography>
                    </Stack>
                    {(logs?.results || logs || []).slice(0, 5).map((log: any) => (
                      <Box key={log.id} sx={{ py: 0.5 }}>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Chip
                            size="small"
                            label={log.status}
                            sx={{
                              height: 16,
                              fontSize: 9,
                              bgcolor: log.status === "success" ? "success.main" : log.status === "failed" ? "error.main" : "grey.400",
                              color: "#fff",
                            }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {new Date(log.created_at).toLocaleString("es-ES")}
                          </Typography>
                          {log.error_message && (
                            <Typography variant="caption" color="error.main">
                              {log.error_message}
                            </Typography>
                          )}
                        </Stack>
                      </Box>
                    ))}
                    {(!logs || (logs?.results || logs || []).length === 0) && (
                      <Typography variant="caption" color="text.secondary">
                        Sin ejecuciones registradas
                      </Typography>
                    )}
                  </Box>
                </Box>
              </Collapse>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Dialog de creación */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Nueva regla de automatización</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nombre"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              size="small"
            />
            <TextField
              label="Descripción"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              size="small"
              multiline
              rows={2}
            />
            <FormControl fullWidth size="small">
              <InputLabel>Trigger (cuándo ejecutar)</InputLabel>
              <Select
                value={form.trigger}
                label="Trigger (cuándo ejecutar)"
                onChange={(e) => setForm({ ...form, trigger: e.target.value })}
              >
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => (
                  <MenuItem key={k} value={k}>{v}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth size="small">
              <InputLabel>Acción (qué hacer)</InputLabel>
              <Select
                value={form.action}
                label="Acción (qué hacer)"
                onChange={(e) => setForm({ ...form, action: e.target.value })}
              >
                {Object.entries(ACTION_LABELS).map(([k, v]) => (
                  <MenuItem key={k} value={k}>{v}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Parámetros de acción (JSON)"
              value={form.action_params}
              onChange={(e) => setForm({ ...form, action_params: e.target.value })}
              fullWidth
              size="small"
              helperText='Ej: {"priority": 0} o {"title": "Notificación", "body": "Texto"}'
            />
            <TextField
              label="Condiciones (JSON array)"
              value={form.conditions}
              onChange={(e) => setForm({ ...form, conditions: e.target.value })}
              fullWidth
              size="small"
              helperText='Ej: [{"field":"state","operator":"equals","value":"blocked"}]'
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
              }
              label="Habilitada"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={handleCreate} disabled={createMut.isPending}>
            Crear
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
