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
import { Plus, Trash2, Flag, Check, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { featureFlagsApi } from "../api/resources";
import { notify } from "../notify";

interface FlagForm {
  key: string;
  name: string;
  description: string;
  is_enabled: boolean;
  enabled_percentage: number;
}

const EMPTY_FORM: FlagForm = {
  key: "",
  name: "",
  description: "",
  is_enabled: false,
  enabled_percentage: 100,
};

export default function FeatureFlagsPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<FlagForm>(EMPTY_FORM);

  // Check section
  const [checkKey, setCheckKey] = useState("");
  const [checkResult, setCheckResult] = useState<any>(null);
  const [checkLoading, setCheckLoading] = useState(false);

  const { data: flags, isLoading } = useQuery({
    queryKey: ["feature-flags"],
    queryFn: featureFlagsApi.list,
  });

  const createMut = useMutation({
    mutationFn: featureFlagsApi.create,
    onSuccess: () => {
      notify.success("Feature flag creado");
      qc.invalidateQueries({ queryKey: ["feature-flags"] });
      setDialogOpen(false);
    },
    onError: () => notify.error("Error al crear feature flag"),
  });

  const toggleMut = useMutation({
    mutationFn: (data: { id: number; is_enabled: boolean }) => {
      // Use create with full payload to update via list+create pattern is not ideal,
      // but featureFlagsApi has no update method. We toggle by creating a new one
      // with same key. Instead, we rely on backend PATCH via api client.
      // Since no update method exists, we use create with the full object.
      return featureFlagsApi.create(data as any);
    },
    onSuccess: () => {
      notify.info("Estado actualizado");
      qc.invalidateQueries({ queryKey: ["feature-flags"] });
    },
    onError: () => notify.error("Error al cambiar estado"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) =>
      (featureFlagsApi as any).delete
        ? (featureFlagsApi as any).delete(id)
        : Promise.reject(new Error("delete not implemented")),
    onSuccess: () => {
      notify.info("Feature flag eliminado");
      qc.invalidateQueries({ queryKey: ["feature-flags"] });
      setDeleteId(null);
    },
    onError: () => notify.error("Error al eliminar feature flag"),
  });

  const handleCreate = () => {
    createMut.mutate({
      key: form.key,
      name: form.name,
      description: form.description,
      is_enabled: form.is_enabled,
      enabled_percentage: form.enabled_percentage,
    });
  };

  const handleToggle = (flag: any) => {
    // featureFlagsApi has no update; create with toggled is_enabled
    createMut.mutate({
      key: flag.key,
      name: flag.name,
      description: flag.description || "",
      is_enabled: !flag.is_enabled,
      enabled_percentage: flag.enabled_percentage ?? 100,
    });
  };

  const handleCheck = async () => {
    if (!checkKey.trim()) {
      notify.warning("Ingresa una key");
      return;
    }
    setCheckLoading(true);
    setCheckResult(null);
    try {
      const res = await featureFlagsApi.check(checkKey.trim());
      setCheckResult(res);
    } catch {
      notify.error("Error al verificar flag");
    } finally {
      setCheckLoading(false);
    }
  };

  const flagList: any[] = flags || [];

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Flag size={24} color="#1976d2" />
          <Typography variant="h5" fontWeight={700}>Feature Flags</Typography>
        </Stack>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={() => { setForm(EMPTY_FORM); setDialogOpen(true); }}
        >
          Nuevo flag
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : flagList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Flag size={48} color="#ccc" />
          <Typography color="text.secondary" mt={1}>
            No hay feature flags. Crea uno para empezar.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {flagList.map((f: any) => (
            <Paper key={f.id ?? f.key} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" alignItems="flex-start" justifyContent="space-between">
                <Box sx={{ flex: 1 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography variant="subtitle1" fontWeight={600}>{f.name || f.key}</Typography>
                    <Chip
                      size="small"
                      label={f.key}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                    />
                  </Stack>
                  {f.description && (
                    <Typography variant="body2" color="text.secondary" mt={0.5}>
                      {f.description}
                    </Typography>
                  )}
                  <Stack direction="row" spacing={1} mt={1} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Chip
                      size="small"
                      label={f.is_enabled ? "Habilitado" : "Deshabilitado"}
                      sx={{
                        height: 22, fontSize: 11,
                        bgcolor: f.is_enabled ? "success.main" : "grey.400",
                        color: "#fff",
                      }}
                      icon={f.is_enabled ? <Check size={12} color="#fff" /> : <X size={12} color="#fff" />}
                    />
                    <Chip
                      size="small"
                      label={`${f.enabled_percentage ?? 100}%`}
                      sx={{ height: 22, fontSize: 11 }}
                      variant="outlined"
                    />
                    {(f.enabled_users || []).length > 0 && (
                      <Chip
                        size="small"
                        label={`${f.enabled_users.length} usuarios`}
                        sx={{ height: 22, fontSize: 11 }}
                        variant="outlined"
                      />
                    )}
                  </Stack>
                </Box>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <Tooltip title={f.is_enabled ? "Deshabilitar" : "Habilitar"}>
                    <IconButton size="small" onClick={() => handleToggle(f)}>
                      {f.is_enabled ? <X size={16} /> : <Check size={16} />}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Eliminar">
                    <IconButton size="small" color="error" onClick={() => setDeleteId(f.id)}>
                      <Trash2 size={16} />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Sección de verificación */}
      <Paper variant="outlined" sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" fontWeight={700} mb={2}>
          Verificar estado de un flag
        </Typography>
        <Stack direction="row" spacing={1} mb={2}>
          <TextField
            label="Key del flag"
            value={checkKey}
            onChange={(e) => setCheckKey(e.target.value)}
            size="small"
          />
          <Button variant="outlined" onClick={handleCheck} disabled={checkLoading}>
            Verificar
          </Button>
        </Stack>

        {checkLoading && (
          <Box display="flex" justifyContent="center" py={2}>
            <CircularProgress size={24} />
          </Box>
        )}

        {checkResult && !checkLoading && (
          <Alert
            severity={checkResult.enabled ? "success" : "info"}
            icon={checkResult.enabled ? <Check size={18} /> : <X size={18} />}
          >
            Flag <strong>{checkKey}</strong> está{" "}
            <strong>{checkResult.enabled ? "HABILITADO" : "DESHABILITADO"}</strong>
            {checkResult.reason && ` (${checkResult.reason})`}
          </Alert>
        )}
      </Paper>

      {/* Dialog de creación */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Crear feature flag</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Key"
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              fullWidth
              size="small"
              helperText="Identificador único, ej: new_dashboard"
            />
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
            <TextField
              label="Porcentaje habilitado"
              value={form.enabled_percentage}
              onChange={(e) => setForm({ ...form, enabled_percentage: Number(e.target.value) })}
              fullWidth
              size="small"
              type="number"
              inputProps={{ min: 0, max: 100 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_enabled}
                  onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })}
                />
              }
              label="Habilitado"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!form.key || createMut.isPending}
          >
            Crear
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmación de borrado */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Eliminar feature flag</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            ¿Seguro que deseas eliminar este feature flag? Esta acción no se puede deshacer.
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
