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
  Switch,
  FormControlLabel,
} from "@mui/material";
import { Plus, Pencil, Trash2, Send } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { outgoingWebhooksApi } from "../api/resources";
import { notify } from "../notify";

interface WebhookForm {
  url: string;
  events: string;
  secret: string;
  is_active: boolean;
}

const EMPTY_FORM: WebhookForm = { url: "", events: "", secret: "", is_active: true };

export default function WebhooksPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<WebhookForm>(EMPTY_FORM);
  const [testResult, setTestResult] = useState<string | null>(null);

  const { data: webhooks, isLoading } = useQuery({
    queryKey: ["outgoing-webhooks"],
    queryFn: outgoingWebhooksApi.list,
  });

  const createMut = useMutation({
    mutationFn: outgoingWebhooksApi.create,
    onSuccess: () => {
      notify.success("Webhook creado");
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
      setDialogOpen(false);
    },
    onError: () => notify.error("Error al crear webhook"),
  });

  const updateMut = useMutation({
    mutationFn: (data: { id: number; payload: any }) =>
      outgoingWebhooksApi.update(data.id, data.payload),
    onSuccess: () => {
      notify.success("Webhook actualizado");
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
      setDialogOpen(false);
    },
    onError: () => notify.error("Error al actualizar webhook"),
  });

  const deleteMut = useMutation({
    mutationFn: outgoingWebhooksApi.delete,
    onSuccess: () => {
      notify.info("Webhook eliminado");
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
      setDeleteId(null);
    },
    onError: () => notify.error("Error al eliminar webhook"),
  });

  const testMut = useMutation({
    mutationFn: outgoingWebhooksApi.test,
    onSuccess: (data: any) => {
      notify.success("Test enviado");
      setTestResult(JSON.stringify(data, null, 2));
    },
    onError: () => notify.error("Error al probar webhook"),
  });

  const toggleMut = useMutation({
    mutationFn: (data: { id: number; is_active: boolean }) =>
      outgoingWebhooksApi.update(data.id, { is_active: data.is_active }),
    onSuccess: () => {
      notify.info("Estado actualizado");
      qc.invalidateQueries({ queryKey: ["outgoing-webhooks"] });
    },
    onError: () => notify.error("Error al cambiar estado"),
  });

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setDialogOpen(true);
  };

  const openEdit = (w: any) => {
    setForm({
      url: w.url || "",
      events: Array.isArray(w.events) ? w.events.join(", ") : (w.events || ""),
      secret: w.secret || "",
      is_active: w.is_active ?? true,
    });
    setEditingId(w.id);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const payload: any = {
      url: form.url,
      events: form.events
        .split(",")
        .map((e) => e.trim())
        .filter(Boolean),
      is_active: form.is_active,
    };
    if (form.secret) payload.secret = form.secret;
    if (editingId) {
      updateMut.mutate({ id: editingId, payload });
    } else {
      createMut.mutate(payload);
    }
  };

  const webhookList: any[] = Array.isArray(webhooks) ? webhooks : (webhooks as any)?.results || [];

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Send size={24} color="#1976d2" />
          <Typography variant="h5" fontWeight={700}>Webhooks salientes</Typography>
        </Stack>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openCreate}>
          Nuevo webhook
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : webhookList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Send size={48} color="#ccc" />
          <Typography color="text.secondary" mt={1}>
            No hay webhooks configurados. Crea uno para empezar.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {webhookList.map((w: any) => (
            <Paper key={w.id} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" alignItems="flex-start" justifyContent="space-between">
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="subtitle1" fontWeight={600} fontFamily="monospace" noWrap>
                    {w.url}
                  </Typography>
                  <Stack direction="row" spacing={0.5} mt={1} flexWrap="wrap" useFlexGap>
                    {(w.events || []).map((e: string) => (
                      <Chip key={e} size="small" label={e} sx={{ height: 20, fontSize: 10 }} variant="outlined" />
                    ))}
                  </Stack>
                  <Stack direction="row" spacing={2} mt={1} alignItems="center">
                    <Chip
                      size="small"
                      label={w.is_active ? "Activo" : "Inactivo"}
                      sx={{
                        height: 20, fontSize: 10,
                        bgcolor: w.is_active ? "success.main" : "grey.400",
                        color: "#fff",
                      }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Último disparo:{" "}
                      {w.last_triggered
                        ? new Date(w.last_triggered).toLocaleString("es-ES")
                        : "Nunca"}
                    </Typography>
                  </Stack>
                </Box>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <FormControlLabel
                    control={
                      <Switch
                        size="small"
                        checked={!!w.is_active}
                        onChange={(e) => toggleMut.mutate({ id: w.id, is_active: e.target.checked })}
                      />
                    }
                    label=""
                  />
                  <Tooltip title="Probar">
                    <IconButton size="small" color="primary" onClick={() => { setTestResult(null); testMut.mutate(w.id); }}>
                      <Send size={16} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Editar">
                    <IconButton size="small" onClick={() => openEdit(w)}>
                      <Pencil size={16} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Eliminar">
                    <IconButton size="small" color="error" onClick={() => setDeleteId(w.id)}>
                      <Trash2 size={16} />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {testResult && (
        <Paper variant="outlined" sx={{ p: 2, mt: 2, fontFamily: "monospace", whiteSpace: "pre-wrap", bgcolor: "action.hover" }}>
          <Typography variant="caption" color="text.secondary" mb={1} display="block">
            Resultado del test:
          </Typography>
          {testResult}
        </Paper>
      )}

      {/* Dialog de creación/edición */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingId ? "Editar webhook" : "Crear webhook"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="URL"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              fullWidth
              size="small"
              placeholder="https://example.com/webhook"
            />
            <TextField
              label="Eventos (separados por comas)"
              value={form.events}
              onChange={(e) => setForm({ ...form, events: e.target.value })}
              fullWidth
              size="small"
              helperText="Ej: task.created, task.completed"
            />
            <TextField
              label="Secret (opcional)"
              value={form.secret}
              onChange={(e) => setForm({ ...form, secret: e.target.value })}
              fullWidth
              size="small"
              type="password"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
              }
              label="Activo"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!form.url || createMut.isPending || updateMut.isPending}
          >
            {editingId ? "Guardar" : "Crear"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmación de borrado */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Eliminar webhook</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            ¿Seguro que deseas eliminar este webhook? Esta acción no se puede deshacer.
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
