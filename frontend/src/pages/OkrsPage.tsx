import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { okrsApi } from "../api/resources";
import { notify } from "../notify";
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  LinearProgress,
  IconButton,
  Stack,
  MenuItem,
  Tooltip,
  Alert,
  Divider,
  InputAdornment,
} from "@mui/material";
import {
  Plus,
  Pencil,
  Trash2,
  Target,
  TrendingUp,
  X,
  Check,
} from "lucide-react";

interface Objective {
  id: number;
  title: string;
  description?: string;
  quarter: string;
  year: number;
  status: string;
  progress: number;
  key_results?: KeyResult[];
}

interface KeyResult {
  id: number;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  owner?: number;
  progress: number;
}

const STATUSES = ["on_track", "at_risk", "behind", "achieved"];
const STATUS_COLORS: Record<string, "default" | "warning" | "error" | "success"> = {
  on_track: "default",
  at_risk: "warning",
  behind: "error",
  achieved: "success",
};

export default function OkrsPage() {
  const queryClient = useQueryClient();
  const [objDialog, setObjDialog] = useState(false);
  const [editingObj, setEditingObj] = useState<Objective | null>(null);
  const [objForm, setObjForm] = useState({ title: "", description: "", quarter: "Q1", year: new Date().getFullYear(), status: "on_track" });

  const [krDialogForObj, setKrDialogForObj] = useState<number | null>(null);
  const [krForm, setKrForm] = useState({ title: "", target_value: 100, current_value: 0, unit: "%" });

  const [updateDialogKr, setUpdateDialogKr] = useState<KeyResult | null>(null);
  const [updateForm, setUpdateForm] = useState({ new_value: 0, note: "" });

  const { data, isLoading } = useQuery({ queryKey: ["objectives"], queryFn: okrsApi.listObjectives });
  const objectives: Objective[] = data?.results || data || [];

  const createObj = useMutation({
    mutationFn: (d: any) => okrsApi.createObjective(d),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["objectives"] }); setObjDialog(false); resetObjForm(); notify.success("Objetivo creado"); },
    onError: () => notify.error("No se pudo crear el objetivo"),
  });

  const updateObj = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => okrsApi.updateObjective(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["objectives"] }); setObjDialog(false); resetObjForm(); notify.success("Objetivo actualizado"); },
    onError: () => notify.error("No se pudo actualizar"),
  });

  const deleteObj = useMutation({
    mutationFn: (id: number) => okrsApi.deleteObjective(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["objectives"] }); notify.success("Objetivo eliminado"); },
    onError: () => notify.error("No se pudo eliminar"),
  });

  const createKr = useMutation({
    mutationFn: (d: any) => okrsApi.createKeyResult(d),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["objectives"] }); setKrDialogForObj(null); resetKrForm(); notify.success("Key result creado"); },
    onError: () => notify.error("No se pudo crear el key result"),
  });

  const deleteKr = useMutation({
    mutationFn: (id: number) => okrsApi.deleteKeyResult(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["objectives"] }); notify.success("Key result eliminado"); },
    onError: () => notify.error("No se pudo eliminar"),
  });

  const updateValue = useMutation({
    mutationFn: ({ id, newValue, note }: { id: number; newValue: number; note: string }) =>
      okrsApi.updateValue(id, newValue, note),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["objectives"] }); setUpdateDialogKr(null); notify.success("Valor actualizado"); },
    onError: () => notify.error("No se pudo actualizar el valor"),
  });

  const [editKrDialog, setEditKrDialog] = useState<any>(null);
  const [editKrForm, setEditKrForm] = useState({ title: "", target_value: 100, current_value: 0, unit: "%" });
  const updateKr = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => okrsApi.updateKeyResult(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["objectives"] }); setEditKrDialog(null); notify.success("Key result actualizado"); },
    onError: () => notify.error("No se pudo actualizar el key result"),
  });

  const openEditKr = (kr: any) => {
    setEditKrForm({ title: kr.title, target_value: kr.target_value, current_value: kr.current_value, unit: kr.unit || "%" });
    setEditKrDialog(kr);
  };

  const resetObjForm = () => { setObjForm({ title: "", description: "", quarter: "Q1", year: new Date().getFullYear(), status: "on_track" }); setEditingObj(null); };
  const resetKrForm = () => { setKrForm({ title: "", target_value: 100, current_value: 0, unit: "%" }); };

  const openEditObj = (obj: Objective) => {
    setEditingObj(obj);
    setObjForm({ title: obj.title, description: obj.description || "", quarter: obj.quarter, year: obj.year, status: obj.status });
    setObjDialog(true);
  };

  const openCreateObj = () => { resetObjForm(); setObjDialog(true); };

  const submitObj = () => {
    if (!objForm.title.trim()) return;
    if (editingObj) updateObj.mutate({ id: editingObj.id, data: objForm });
    else createObj.mutate(objForm);
  };

  const submitKr = () => {
    if (!krForm.title.trim() || krDialogForObj === null) return;
    createKr.mutate({ ...krForm, objective: krDialogForObj });
  };

  const submitUpdate = () => {
    if (!updateDialogKr) return;
    updateValue.mutate({ id: updateDialogKr.id, newValue: updateForm.new_value, note: updateForm.note });
  };

  if (isLoading) return <CircularProgress />;

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>OKRs</Typography>
          <Typography variant="body2" color="text.secondary">Objetivos y resultados clave</Typography>
        </Box>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openCreateObj}>
          Nuevo Objetivo
        </Button>
      </Box>

      {objectives.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No hay objetivos creados. Crea tu primer OKR con el botón "Nuevo Objetivo".
        </Alert>
      )}

      {objectives.map((obj) => (
        <Paper key={obj.id} sx={{ p: 3, mb: 2 }}>
          {/* Header del objetivo */}
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="h6" fontWeight={600}>{obj.title}</Typography>
              {obj.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{obj.description}</Typography>
              )}
            </Box>
            <Stack direction="row" spacing={0.5}>
              <Tooltip title="Editar">
                <IconButton size="small" onClick={() => openEditObj(obj)}><Pencil size={16} /></IconButton>
              </Tooltip>
              <Tooltip title="Eliminar">
                <IconButton size="small" color="error" onClick={() => { if (confirm("¿Eliminar este objetivo?")) deleteObj.mutate(obj.id); }}><Trash2 size={16} /></IconButton>
              </Tooltip>
            </Stack>
          </Box>

          {/* Chips y progreso */}
          <Box sx={{ display: "flex", gap: 1, mb: 1.5, alignItems: "center" }}>
            <Chip label={`${obj.quarter} ${obj.year}`} size="small" variant="outlined" />
            <Chip
              label={obj.status.replace("_", " ")}
              size="small"
              color={STATUS_COLORS[obj.status] || "default"}
            />
            <Typography variant="caption" color="text.secondary" sx={{ ml: "auto" }}>
              {obj.progress || 0}% completado
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={obj.progress || 0}
            sx={{ height: 8, borderRadius: 4, mb: 2 }}
            color={obj.progress >= 100 ? "success" : "primary"}
          />

          <Divider sx={{ mb: 2 }} />

          {/* Key results */}
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Resultados clave
          </Typography>
          {obj.key_results && obj.key_results.length > 0 ? (
            <Stack spacing={1.5}>
              {obj.key_results.map((kr) => {
                const pct = kr.target_value > 0 ? Math.min(100, (kr.current_value / kr.target_value) * 100) : 0;
                return (
                  <Box key={kr.id} sx={{ pl: 2, borderLeft: "3px solid", borderColor: "primary.main" }}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <Typography variant="body2" fontWeight={500}>{kr.title}</Typography>
                      <Stack direction="row" spacing={0.5}>
                        <Tooltip title="Actualizar valor">
                          <IconButton size="small" onClick={() => { setUpdateDialogKr(kr); setUpdateForm({ new_value: kr.current_value, note: "" }); }}>
                            <TrendingUp size={14} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Editar KR">
                          <IconButton size="small" onClick={() => openEditKr(kr)}>
                            <Pencil size={14} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Eliminar KR">
                          <IconButton size="small" color="error" onClick={() => { if (confirm("¿Eliminar este key result?")) deleteKr.mutate(kr.id); }}>
                            <X size={14} />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </Box>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}>
                      <Typography variant="caption" color="text.secondary">
                        {kr.current_value} / {kr.target_value} {kr.unit}
                      </Typography>
                      <Box sx={{ flex: 1 }}>
                        <LinearProgress variant="determinate" value={pct} sx={{ height: 6, borderRadius: 3 }} color={pct >= 100 ? "success" : "primary"} />
                      </Box>
                      <Typography variant="caption" fontWeight={600}>{Math.round(pct)}%</Typography>
                    </Box>
                  </Box>
                );
              })}
            </Stack>
          ) : (
            <Typography variant="caption" color="text.secondary">Sin key results todavía.</Typography>
          )}

          <Button
            size="small"
            startIcon={<Plus size={14} />}
            sx={{ mt: 2 }}
            onClick={() => { setKrDialogForObj(obj.id); resetKrForm(); }}
          >
            Añadir key result
          </Button>
        </Paper>
      ))}

      {/* Dialog: Crear/Editar Objetivo */}
      <Dialog open={objDialog} onClose={() => setObjDialog(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingObj ? "Editar Objetivo" : "Nuevo Objetivo"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Título" fullWidth autoFocus value={objForm.title} onChange={(e) => setObjForm({ ...objForm, title: e.target.value })} />
            <TextField label="Descripción" fullWidth multiline rows={2} value={objForm.description} onChange={(e) => setObjForm({ ...objForm, description: e.target.value })} />
            <Stack direction="row" spacing={2}>
              <TextField fullWidth select label="Quarter" value={objForm.quarter} onChange={(e) => setObjForm({ ...objForm, quarter: e.target.value })} SelectProps={{ native: true }}>
                {["Q1", "Q2", "Q3", "Q4"].map((q) => <option key={q} value={q}>{q}</option>)}
              </TextField>
              <TextField fullWidth type="number" label="Año" value={objForm.year} onChange={(e) => setObjForm({ ...objForm, year: Number(e.target.value) })} />
            </Stack>
            <TextField fullWidth select label="Estado" value={objForm.status} onChange={(e) => setObjForm({ ...objForm, status: e.target.value })}>
              {STATUSES.map((s) => <MenuItem key={s} value={s}>{s.replace("_", " ")}</MenuItem>)}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setObjDialog(false)}>Cancelar</Button>
          <Button variant="contained" disabled={!objForm.title.trim()} onClick={submitObj}>
            {editingObj ? "Guardar" : "Crear"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Crear Key Result */}
      <Dialog open={krDialogForObj !== null} onClose={() => setKrDialogForObj(null)} fullWidth maxWidth="sm">
        <DialogTitle>Nuevo Key Result</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Título" fullWidth autoFocus value={krForm.title} onChange={(e) => setKrForm({ ...krForm, title: e.target.value })} />
            <Stack direction="row" spacing={2}>
              <TextField fullWidth type="number" label="Valor objetivo" value={krForm.target_value} onChange={(e) => setKrForm({ ...krForm, target_value: Number(e.target.value) })} />
              <TextField fullWidth type="number" label="Valor actual" value={krForm.current_value} onChange={(e) => setKrForm({ ...krForm, current_value: Number(e.target.value) })} />
            </Stack>
            <TextField label="Unidad" fullWidth placeholder="%, €, usuarios, tickets..." value={krForm.unit} onChange={(e) => setKrForm({ ...krForm, unit: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setKrDialogForObj(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!krForm.title.trim()} onClick={submitKr}>Crear</Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Actualizar valor de KR */}
      <Dialog open={!!updateDialogKr} onClose={() => setUpdateDialogKr(null)} fullWidth maxWidth="xs">
        <DialogTitle>Actualizar progreso</DialogTitle>
        <DialogContent>
          {updateDialogKr && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {updateDialogKr.title} — actual: {updateDialogKr.current_value} {updateDialogKr.unit}
            </Typography>
          )}
          <Stack spacing={2}>
            <TextField
              label="Nuevo valor"
              type="number"
              fullWidth
              autoFocus
              value={updateForm.new_value}
              onChange={(e) => setUpdateForm({ ...updateForm, new_value: Number(e.target.value) })}
              InputProps={{ endAdornment: <InputAdornment position="end">{updateDialogKr?.unit}</InputAdornment> }}
            />
            <TextField label="Nota (opcional)" fullWidth multiline rows={2} value={updateForm.note} onChange={(e) => setUpdateForm({ ...updateForm, note: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUpdateDialogKr(null)}>Cancelar</Button>
          <Button variant="contained" startIcon={<Check size={16} />} onClick={submitUpdate}>Actualizar</Button>
        </DialogActions>
      </Dialog>

      {/* Edit KR dialog */}
      <Dialog open={!!editKrDialog} onClose={() => setEditKrDialog(null)} fullWidth maxWidth="xs">
        <DialogTitle>Editar key result</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Título" fullWidth value={editKrForm.title} onChange={(e) => setEditKrForm({ ...editKrForm, title: e.target.value })} />
            <TextField label="Valor objetivo" type="number" fullWidth value={editKrForm.target_value} onChange={(e) => setEditKrForm({ ...editKrForm, target_value: Number(e.target.value) })} />
            <TextField label="Valor actual" type="number" fullWidth value={editKrForm.current_value} onChange={(e) => setEditKrForm({ ...editKrForm, current_value: Number(e.target.value) })} />
            <TextField label="Unidad" fullWidth value={editKrForm.unit} onChange={(e) => setEditKrForm({ ...editKrForm, unit: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditKrDialog(null)}>Cancelar</Button>
          <Button variant="contained" startIcon={<Check size={16} />} disabled={updateKr.isPending} onClick={() => editKrDialog && updateKr.mutate({ id: editKrDialog.id, data: editKrForm })}>Guardar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
