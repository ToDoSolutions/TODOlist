import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { advancedMetricsApi, sprintsApi } from "../api/resources";
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Stack,
  Chip,
} from "@mui/material";

export default function BurndownPage() {
  const [sprintId, setSprintId] = useState<number | "">("");
  const { data: sprintsData } = useQuery({ queryKey: ["sprints"], queryFn: sprintsApi.list });
  const sprints: any[] = sprintsData || [];

  const { data, isLoading, isError } = useQuery({
    queryKey: ["burndown", sprintId],
    queryFn: () => advancedMetricsApi.burndown(Number(sprintId)),
    enabled: !!sprintId,
  });

  return (
    <Box maxWidth={1000} mx="auto">
      <Typography variant="h5" fontWeight={700} mb={2}>
        Burndown Chart
      </Typography>

      <FormControl sx={{ minWidth: 200, mb: 2 }}>
        <InputLabel>Sprint</InputLabel>
        <Select value={sprintId} onChange={(e) => setSprintId(e.target.value as number)} label="Sprint">
          {sprints.map((s: any) => (
            <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
          ))}
        </Select>
      </FormControl>

      {!sprintId && <Typography color="text.secondary">Selecciona un sprint</Typography>}
      {sprintId && isLoading && <CircularProgress />}
      {sprintId && isError && (
        <Alert severity="error" sx={{ mt: 2 }}>No se pudieron cargar los datos del burndown.</Alert>
      )}
      {sprintId && data && <BurndownChart data={data} />}
    </Box>
  );
}

function BurndownChart({ data }: { data: any }) {
  const ideal: { date: string; ideal: number }[] = data.ideal || [];
  const actual: { date: string; remaining: number }[] = data.actual || [];
  const totalPoints = data.total_points || 0;

  if (!ideal.length) {
    return (
      <Paper sx={{ p: 2 }}>
        <Typography color="text.secondary">Sin datos para este sprint</Typography>
      </Paper>
    );
  }

  const n = ideal.length;
  const maxY = Math.max(totalPoints, ...actual.map((a) => a.remaining), 1);
  const W = 800;
  const H = 320;
  const padL = 40;
  const padR = 10;
  const padT = 10;
  const padB = 30;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const xFor = (i: number) => padL + (i / (n - 1 || 1)) * plotW;
  const yFor = (v: number) => padT + plotH - (v / maxY) * plotH;

  // Build polyline points
  const idealPts = ideal.map((d, i) => `${xFor(i)},${yFor(d.ideal)}`).join(" ");
  const actualPts = actual
    .map((d, i) => `${xFor(i)},${yFor(d.remaining)}`)
    .join(" ");

  // Y-axis ticks
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(maxY * f));

  // X-axis labels (first, middle, last)
  const xLabels = [0, Math.floor(n / 2), n - 1].map((i) => ({ i, label: ideal[i]?.date?.slice(5) || "" }));

  return (
    <Paper sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="h6">{data.sprint?.name}</Typography>
        <Stack direction="row" spacing={1}>
          <Chip label={`${data.total_points} pts`} size="small" color="primary" />
          <Chip label={`${data.total_tasks} tareas`} size="small" variant="outlined" />
        </Stack>
      </Stack>
      <Typography variant="body2" color="text.secondary" mb={2}>
        {data.sprint?.start_date} → {data.sprint?.end_date}
      </Typography>

      {/* Legend */}
      <Stack direction="row" spacing={2} mb={1}>
        <Stack direction="row" alignItems="center" spacing={0.5}>
          <Box sx={{ width: 18, height: 3, bgcolor: "#9e9e9e" }} />
          <Typography variant="caption">Ideal</Typography>
        </Stack>
        <Stack direction="row" alignItems="center" spacing={0.5}>
          <Box sx={{ width: 18, height: 3, bgcolor: "#1976d2" }} />
          <Typography variant="caption">Actual</Typography>
        </Stack>
      </Stack>

      <Box sx={{ width: "100%", overflowX: "auto" }}>
        <svg width={W} height={H} style={{ display: "block" }}>
          {/* Grid lines + Y labels */}
          {yTicks.map((v, idx) => {
            const y = yFor(v);
            return (
              <g key={idx}>
                <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#e0e0e0" strokeWidth={1} />
                <text x={padL - 6} y={y + 3} textAnchor="end" fontSize={10} fill="#666">{v}</text>
              </g>
            );
          })}

          {/* X-axis labels */}
          {xLabels.map((xl, idx) => (
            <text key={idx} x={xFor(xl.i)} y={H - padB + 14} textAnchor="middle" fontSize={10} fill="#666">
              {xl.label}
            </text>
          ))}

          {/* Axes */}
          <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#999" strokeWidth={1} />
          <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="#999" strokeWidth={1} />

          {/* Ideal line (dashed grey) */}
          <polyline points={idealPts} fill="none" stroke="#9e9e9e" strokeWidth={2} strokeDasharray="5,3" />

          {/* Actual line (solid blue) */}
          <polyline points={actualPts} fill="none" stroke="#1976d2" strokeWidth={2.5} />

          {/* Actual data points */}
          {actual.map((d, i) => (
            <circle key={i} cx={xFor(i)} cy={yFor(d.remaining)} r={3} fill="#1976d2" />
          ))}
        </svg>
      </Box>

      <Typography variant="caption" color="text.secondary" mt={1} display="block">
        Eje X: días del sprint · Eje Y: puntos restantes
      </Typography>
    </Paper>
  );
}
