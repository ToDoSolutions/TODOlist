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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import { Key, Plus, Trash2, Copy, Check, Ban, ExternalLink } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiKeysApi } from "../api/resources";
import { notify } from "../notify";

export default function ApiKeysPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState({ name: "", scopes: ["read"] });

  const { data: keys, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: apiKeysApi.list,
  });

  const createMut = useMutation({
    mutationFn: apiKeysApi.create,
    onSuccess: (data) => {
      setNewKey(data.key);
      notify.success("API key creada");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const revokeMut = useMutation({
    mutationFn: apiKeysApi.revoke,
    onSuccess: () => {
      notify.info("API key revocada");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: apiKeysApi.delete,
    onSuccess: () => {
      notify.info("API key eliminada");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const handleCreate = () => {
    createMut.mutate({ name: form.name, scopes: form.scopes });
    setDialogOpen(false);
  };

  const copyKey = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const keyList = keys || [];

  return (
    <Box maxWidth={800} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Key size={24} color="#1976d2" />
          <Typography variant="h5" fontWeight={700}>API Keys</Typography>
        </Stack>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={() => { setForm({ name: "", scopes: ["read"] }); setNewKey(null); setDialogOpen(true); }}>
          Nueva key
        </Button>
      </Stack>

      <Alert severity="info" sx={{ mb: 2 }}>
        Usa las API keys para acceso programático a la API REST. Incluye el header
        <code>Authorization: ApiKey &lt;tu_key&gt;</code> en tus requests.
        Documentación: <a href="/api/docs/" target="_blank" rel="noopener">Swagger UI</a> ·
        <a href="/api/redoc/" target="_blank" rel="noopener">ReDoc</a>
      </Alert>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : keyList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Key size={48} color="text.disabled" />
          <Typography color="text.secondary" mt={1}>
            No tienes API keys. Crea una para empezar a usar la API.
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Nombre</TableCell>
                <TableCell>Prefix</TableCell>
                <TableCell>Scopes</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell>Último uso</TableCell>
                <TableCell>Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {keyList.map((k: any) => (
                <TableRow key={k.id}>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>{k.name}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">{k.key_prefix}...</Typography>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      {(k.scopes || []).map((s: string) => (
                        <Chip key={s} size="small" label={s} sx={{ height: 18, fontSize: 10 }} variant="outlined" />
                      ))}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={k.is_active ? "Activa" : "Revocada"}
                      sx={{
                        height: 18, fontSize: 10,
                        bgcolor: k.is_active ? "success.main" : "grey.400",
                        color: "#fff",
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {k.last_used_at ? new Date(k.last_used_at).toLocaleString("es-ES") : "Nunca"}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      {k.is_active && (
                        <Tooltip title="Revocar">
                          <IconButton size="small" onClick={() => revokeMut.mutate(k.id)}>
                            <Ban size={14} />
                          </IconButton>
                        </Tooltip>
                      )}
                      <Tooltip title="Eliminar">
                        <IconButton size="small" color="error" onClick={() => deleteMut.mutate(k.id)}>
                          <Trash2 size={14} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Dialog de creación */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Crear API key</DialogTitle>
        <DialogContent>
          {newKey ? (
            <Box>
              <Alert severity="warning" sx={{ mb: 2 }}>
                Guarda esta key en un lugar seguro. No se volverá a mostrar.
              </Alert>
              <Paper variant="outlined" sx={{ p: 2, fontFamily: "monospace", wordBreak: "break-all", bgcolor: "action.hover" }}>
                {newKey}
              </Paper>
              <Button
                startIcon={copied ? <Check size={16} /> : <Copy size={16} />}
                onClick={copyKey}
                sx={{ mt: 1 }}
                color={copied ? "success" : "primary"}
              >
                {copied ? "Copiada" : "Copiar"}
              </Button>
            </Box>
          ) : (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField
                label="Nombre"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                fullWidth
                size="small"
                helperText="Nombre descriptivo para identificar la key"
              />
              <FormControl fullWidth size="small">
                <InputLabel>Scopes</InputLabel>
                <Select
                  multiple
                  value={form.scopes}
                  label="Scopes"
                  onChange={(e) => setForm({ ...form, scopes: e.target.value as string[] })}
                >
                  <MenuItem value="read">Read (lectura)</MenuItem>
                  <MenuItem value="write">Write (escritura)</MenuItem>
                  <MenuItem value="admin">Admin (todo)</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setDialogOpen(false); setNewKey(null); }}>
            {newKey ? "Cerrar" : "Cancelar"}
          </Button>
          {!newKey && (
            <Button variant="contained" onClick={handleCreate} disabled={!form.name || createMut.isPending}>
              Crear
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
}

