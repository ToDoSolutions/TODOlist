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
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, Trash2 } from "lucide-react";
import { epicsApi, type Epic } from "../api/resources";
import { notify } from "../notify";

export default function EpicsPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", color: "#9c27b0" });

  const { data: epics = [], isLoading } = useQuery({
    queryKey: ["epics"],
    queryFn: epicsApi.list,
  });

  const createMut = useMutation({
    mutationFn: () => epicsApi.create(form),
    onSuccess: () => {
      notify.success("Épica creada");
      qc.invalidateQueries({ queryKey: ["epics"] });
      setDialogOpen(false);
      setForm({ title: "", description: "", color: "#9c27b0" });
    },
    onError: () => notify.error("Error al crear épica"),
  });

  const deleteMut = useMutation({
    mutationFn: epicsApi.remove,
    onSuccess: () => {
      notify.info("Épica eliminada");
      qc.invalidateQueries({ queryKey: ["epics"] });
    },
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

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight={700}>
          Épicas
        </Typography>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={() => setDialogOpen(true)}
        >
          Nueva épica
        </Button>
      </Stack>

      {isLoading && <LinearProgress />}

      {epics.length === 0 && !isLoading && (
        <Alert severity="info">
          No hay épicas. Las épicas agrupan tareas relacionadas para追踪ar el progreso de iniciativas grandes.
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
    </Box>
  );
}
