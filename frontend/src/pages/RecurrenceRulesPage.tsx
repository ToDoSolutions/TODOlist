import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import { Trash2, Plus, Repeat } from "lucide-react";
import { recurrenceRulesApi } from "../api/resources";
import { notify } from "../notify";

const FREQ_LABELS: Record<string, string> = {
  daily: "Diaria",
  weekly: "Semanal",
  monthly: "Mensual",
  yearly: "Anual",
};

export default function RecurrenceRulesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [frequency, setFrequency] = useState("weekly");
  const [interval, setInterval] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["recurrence-rules"],
    queryFn: recurrenceRulesApi.list,
  });
  const rules = data || [];

  const createMutation = useMutation({
    mutationFn: () =>
      recurrenceRulesApi.create({ frequency, interval }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurrence-rules"] });
      setOpen(false);
      notify.success("Regla de recurrencia creada");
    },
    onError: () => notify.error("Error al crear regla"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => recurrenceRulesApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurrence-rules"] });
      notify.success("Regla eliminada");
    },
  });

  if (isLoading) return <CircularProgress />;

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h5">Reglas de recurrencia</Typography>
        <Button variant="contained" startIcon={<Plus size={16} />} onClick={() => setOpen(true)}>
          Nueva regla
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Frecuencia</TableCell>
              <TableCell>Intervalo</TableCell>
              <TableCell>Ocurrencias generadas</TableCell>
              <TableCell>Fecha creación</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {rules.map((r: any) => (
              <TableRow key={r.id}>
                <TableCell>{r.id}</TableCell>
                <TableCell>
                  <Chip size="small" label={FREQ_LABELS[r.frequency] || r.frequency} icon={<Repeat size={14} />} />
                </TableCell>
                <TableCell>Cada {r.interval}</TableCell>
                <TableCell>{r.occurrences_generated}</TableCell>
                <TableCell>{new Date(r.created_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  <IconButton size="small" onClick={() => deleteMutation.mutate(r.id)} title="Eliminar">
                    <Trash2 size={16} />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
            {rules.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography color="text.secondary">No hay reglas de recurrencia</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>Nueva regla de recurrencia</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            select
            label="Frecuencia"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            sx={{ mt: 1 }}
            SelectProps={{ native: true }}
          >
            <option value="daily">Diaria</option>
            <option value="weekly">Semanal</option>
            <option value="monthly">Mensual</option>
            <option value="yearly">Anual</option>
          </TextField>
          <TextField
            fullWidth
            label="Intervalo (cada cuántos períodos)"
            type="number"
            value={interval}
            onChange={(e) => setInterval(Number(e.target.value))}
            sx={{ mt: 2 }}
            inputProps={{ min: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
            Crear
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
