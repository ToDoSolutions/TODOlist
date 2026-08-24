import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { okrsApi } from "../api/resources";
import { Box, Typography, CircularProgress, Paper, Button, TextField, Dialog, DialogTitle, DialogContent, DialogActions, Chip, LinearProgress } from "@mui/material";

export default function OkrsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [quarter, setQuarter] = useState("Q1");
  const [year, setYear] = useState(new Date().getFullYear());

  const { data, isLoading } = useQuery({ queryKey: ["objectives"], queryFn: okrsApi.listObjectives });
  const objectives = data?.results || data || [];

  const createMutation = useMutation({
    mutationFn: okrsApi.createObjective,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setOpen(false);
      setTitle("");
    },
  });

  if (isLoading) return <CircularProgress />;

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h5">OKRs</Typography>
        <Button variant="contained" onClick={() => setOpen(true)}>Nuevo Objetivo</Button>
      </Box>

      {objectives.map((obj: any) => (
        <Paper key={obj.id} sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6">{obj.title}</Typography>
          <Typography variant="body2" color="textSecondary">{obj.description}</Typography>
          <Box sx={{ display: "flex", gap: 1, my: 1 }}>
            <Chip label={`${obj.quarter} ${obj.year}`} size="small" />
            <Chip label={obj.status} size="small" color={obj.status === "achieved" ? "success" : "default"} />
          </Box>
          <LinearProgress variant="determinate" value={obj.progress || 0} sx={{ height: 8, borderRadius: 4, mb: 1 }} />
          <Typography variant="caption">{obj.progress || 0}% completado</Typography>
          {obj.key_results?.map((kr: any) => (
            <Box key={kr.id} sx={{ mt: 1, pl: 2, borderLeft: "2px solid #1976d2" }}>
              <Typography variant="body2">{kr.title}: {kr.current_value}/{kr.target_value} {kr.unit}</Typography>
            </Box>
          ))}
        </Paper>
      ))}

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>Nuevo Objetivo</DialogTitle>
        <DialogContent>
          <TextField fullWidth label="Título" value={title} onChange={(e) => setTitle(e.target.value)} sx={{ mt: 1 }} />
          <TextField fullWidth select label="Quarter" value={quarter} onChange={(e) => setQuarter(e.target.value)} sx={{ mt: 2 }}
            SelectProps={{ native: true }}>
            {["Q1", "Q2", "Q3", "Q4"].map((q) => <option key={q} value={q}>{q}</option>)}
          </TextField>
          <TextField fullWidth type="number" label="Año" value={year} onChange={(e) => setYear(Number(e.target.value))} sx={{ mt: 2 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button variant="contained" onClick={() => createMutation.mutate({ title, quarter, year })}>Crear</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
