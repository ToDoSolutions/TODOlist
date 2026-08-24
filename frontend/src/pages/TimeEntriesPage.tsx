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
import { Plus, Pencil, Trash2, Clock, Timer } from "lucide-react";
import { timeEntriesApi } from "../api/resources";
import { notify } from "../notify";

interface TimeEntry {
  id: number;
  task: number;
  task_title?: string;
  duration: number; // minutes
  date: string;
  description?: string;
}

interface EntryForm {
  task: string;
  duration: string;
  description: string;
  date: string;
}

const emptyForm: EntryForm = {
  task: "",
  duration: "",
  description: "",
  date: new Date().toISOString().slice(0, 10),
};

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

export default function TimeEntriesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TimeEntry | null>(null);
  const [form, setForm] = useState<EntryForm>(emptyForm);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const { data: entriesData, isLoading } = useQuery({
    queryKey: ["time-entries"],
    queryFn: timeEntriesApi.list,
  });
  const entries: TimeEntry[] = Array.isArray(entriesData)
    ? entriesData
    : (entriesData as any)?.results ?? [];

  const totalMinutes = entries.reduce((sum, e) => sum + (e.duration || 0), 0);

  const createMut = useMutation({
    mutationFn: () =>
      timeEntriesApi.create({
        task: Number(form.task),
        duration: Number(form.duration),
        description: form.description,
        date: form.date,
      }),
    onSuccess: () => {
      notify.success("Registro de tiempo creado");
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo crear el registro"),
  });

  const updateMut = useMutation({
    mutationFn: () =>
      timeEntriesApi.update(editing!.id, {
        task: Number(form.task),
        duration: Number(form.duration),
        description: form.description,
        date: form.date,
      }),
    onSuccess: () => {
      notify.success("Registro de tiempo actualizado");
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo actualizar"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => timeEntriesApi.delete(id),
    onSuccess: () => {
      notify.success("Registro de tiempo eliminado");
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setDeleteId(null);
    },
    onError: () => notify.error("No se pudo eliminar"),
  });

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (e: TimeEntry) => {
    setEditing(e);
    setForm({
      task: String(e.task),
      duration: String(e.duration),
      description: e.description ?? "",
      date: e.date ?? "",
    });
    setOpen(true);
  };

  const save = () => {
    if (!form.task || !form.duration || !form.date) return;
    if (editing) updateMut.mutate();
    else createMut.mutate();
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h5" fontWeight={700}>
          Registros de tiempo
        </Typography>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          Nuevo registro
        </Button>
      </Stack>

      <Paper variant="outlined" sx={{ p: 2, mb: 2, display: "flex", alignItems: "center", gap: 1 }}>
        <Timer size={20} />
        <Typography variant="subtitle1" fontWeight={600}>
          Tiempo total: {formatDuration(totalMinutes)}
        </Typography>
      </Paper>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : entries.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Clock size={32} style={{ color: "#bbb" }} />
          <Typography color="text.secondary" mt={1}>
            No hay registros de tiempo. Crea el primero para empezar a追踪ar tu tiempo.
          </Typography>
        </Paper>
      ) : (
        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Tarea</TableCell>
                <TableCell>Duración</TableCell>
                <TableCell>Fecha</TableCell>
                <TableCell>Descripción</TableCell>
                <TableCell align="right">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entries.map((e) => (
                <TableRow key={e.id} hover>
                  <TableCell>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Clock size={14} style={{ color: "#888" }} />
                      <Typography variant="body2">
                        {e.task_title ?? `Tarea #${e.task}`}
                      </Typography>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      icon={<Timer size={14} />}
                      label={formatDuration(e.duration)}
                    />
                  </TableCell>
                  <TableCell>{e.date}</TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary" noWrap maxWidth={220}>
                      {e.description || "—"}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Editar">
                      <IconButton size="small" onClick={() => openEdit(e)}>
                        <Pencil size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Eliminar">
                      <IconButton size="small" onClick={() => setDeleteId(e.id)}>
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
          {editing ? "Editar registro de tiempo" : "Nuevo registro de tiempo"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="ID de tarea"
              fullWidth
              type="number"
              value={form.task}
              onChange={(e) => setForm({ ...form, task: e.target.value })}
              autoFocus
            />
            <TextField
              label="Duración (minutos)"
              fullWidth
              type="number"
              value={form.duration}
              onChange={(e) => setForm({ ...form, duration: e.target.value })}
            />
            <TextField
              label="Fecha"
              type="date"
              fullWidth
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="Descripción"
              fullWidth
              multiline
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={save}
            disabled={!form.task || !form.duration || !form.date}
          >
            {editing ? "Guardar" : "Crear"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs">
        <DialogTitle>Eliminar registro</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            ¿Seguro que deseas eliminar este registro de tiempo? Esta acción no se puede deshacer.
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
