import { useQuery } from "@tanstack/react-query";
import { advancedMetricsApi } from "../api/resources";
import { Box, Typography, CircularProgress, Paper, Chip, LinearProgress } from "@mui/material";

export default function CapacityPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["capacity"],
    queryFn: advancedMetricsApi.capacity,
  });

  if (isLoading) return <CircularProgress />;

  const capacity = data?.capacity || [];
  const maxPoints = Math.max(...capacity.map((c: any) => c.total_points), 1);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Capacity Planning</Typography>
      <Paper sx={{ p: 2 }}>
        {capacity.length === 0 && <Typography color="textSecondary">Sin datos</Typography>}
        {capacity.map((c: any, i: number) => (
          <Box key={i} sx={{ mb: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: c.project_color }} />
              <Typography sx={{ flex: 1 }}>{c.project}</Typography>
              <Chip label={`${c.total_points}pt`} size="small" color="primary" />
              <Chip label={`${c.open_tasks} abiertas`} size="small" variant="outlined" />
              {c.in_progress > 0 && <Chip label={`${c.in_progress} en progreso`} size="small" color="info" />}
              {c.blocked > 0 && <Chip label={`${c.blocked} bloqueadas`} size="small" color="error" />}
            </Box>
            <LinearProgress
              variant="determinate"
              value={(c.total_points / maxPoints) * 100}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        ))}
      </Paper>
    </Box>
  );
}
