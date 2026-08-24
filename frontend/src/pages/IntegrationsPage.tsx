import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { chatIntegrationsApi } from "../api/resources";
import { Box, Typography, CircularProgress, Paper, Button, TextField, Dialog, DialogTitle, DialogContent, DialogActions, Chip, IconButton, Switch, FormControlLabel } from "@mui/material";
import { Trash2, Send, Pencil } from "lucide-react";
import { notify } from "../notify";

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [provider, setProvider] = useState("slack");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [events, setEvents] = useState("task_created,task_completed");

  const { data, isLoading } = useQuery({ queryKey: ["chat-integrations"], queryFn: chatIntegrationsApi.list });
  const integrations = data?.results || data || [];

  const createMutation = useMutation({
    mutationFn: chatIntegrationsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-integrations"] });
      setOpen(false);
      setWebhookUrl("");
      notify.success("Integración creada");
    },
    onError: () => notify.error("Error al crear integración"),
  });

  const deleteMutation = useMutation({
    mutationFn: chatIntegrationsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-integrations"] });
      notify.success("Integración eliminada");
    },
    onError: () => notify.error("Error al eliminar integración"),
  });

  const testMutation = useMutation({
    mutationFn: chatIntegrationsApi.test,
    onSuccess: (res: any) => {
      if (res?.success) notify.success("Test OK");
      else notify.error(`Test fallido: ${res?.error || ""}`);
    },
    onError: () => notify.error("Error al probar integración"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => chatIntegrationsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-integrations"] });
      notify.success("Integración actualizada");
    },
    onError: () => notify.error("Error al actualizar integración"),
  });

  if (isLoading) return <CircularProgress />;

  const openEdit = (int: any) => {
    setEditing(int);
    setProvider(int.provider || "slack");
    setWebhookUrl(int.webhook_url || "");
    setEvents(Array.isArray(int.events) ? int.events.join(", ") : "");
    setEditOpen(true);
  };

  const submitEdit = () => {
    if (!editing) return;
    updateMutation.mutate({
      id: editing.id,
      data: {
        provider,
        webhook_url: webhookUrl,
        events: events.split(",").map((e) => e.trim()).filter(Boolean),
      },
    });
    setEditOpen(false);
    setEditing(null);
  };

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h5">Integraciones (Slack/Discord)</Typography>
        <Button variant="contained" onClick={() => setOpen(true)}>Nueva integración</Button>
      </Box>

      {integrations.map((int: any) => (
        <Paper key={int.id} sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Chip label={int.provider} color="primary" size="small" />
            <Typography sx={{ flex: 1 }} variant="body2" noWrap>{int.webhook_url}</Typography>
            <FormControlLabel
              control={
                <Switch
                  checked={!!int.is_active}
                  size="small"
                  onChange={(e) => updateMutation.mutate({ id: int.id, data: { is_active: e.target.checked } })}
                />
              }
              label="Activa"
            />
            <IconButton onClick={() => openEdit(int)} title="Editar">
              <Pencil size={16} />
            </IconButton>
            <IconButton onClick={() => testMutation.mutate(int.id)} title="Probar">
              <Send size={16} />
            </IconButton>
            <IconButton onClick={() => deleteMutation.mutate(int.id)} title="Eliminar">
              <Trash2 size={16} />
            </IconButton>
          </Box>
          <Box sx={{ mt: 1, display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {int.events?.map((e: string) => <Chip key={e} label={e} size="small" variant="outlined" />)}
          </Box>
        </Paper>
      ))}

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>Nueva integración</DialogTitle>
        <DialogContent>
          <TextField fullWidth select label="Provider" value={provider} onChange={(e) => setProvider(e.target.value)} sx={{ mt: 1 }}
            SelectProps={{ native: true }}>
            <option value="slack">Slack</option>
            <option value="discord">Discord</option>
          </TextField>
          <TextField fullWidth label="Webhook URL" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} sx={{ mt: 2 }} />
          <TextField fullWidth label="Eventos (separados por coma)" value={events} onChange={(e) => setEvents(e.target.value)} sx={{ mt: 2 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={() => createMutation.mutate({
            provider, webhook_url: webhookUrl, events: events.split(",").map((e) => e.trim()),
          })}>Crear</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={editOpen} onClose={() => { setEditOpen(false); setEditing(null); }}>
        <DialogTitle>Editar integración</DialogTitle>
        <DialogContent>
          <TextField fullWidth select label="Provider" value={provider} onChange={(e) => setProvider(e.target.value)} sx={{ mt: 1 }}
            SelectProps={{ native: true }}>
            <option value="slack">Slack</option>
            <option value="discord">Discord</option>
          </TextField>
          <TextField fullWidth label="Webhook URL" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} sx={{ mt: 2 }} />
          <TextField fullWidth label="Eventos (separados por coma)" value={events} onChange={(e) => setEvents(e.target.value)} sx={{ mt: 2 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setEditOpen(false); setEditing(null); }}>Cancelar</Button>
          <Button variant="contained" onClick={submitEdit}>Guardar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
