import { useQuery } from "@tanstack/react-query";
import { advancedMetricsApi } from "../api/resources";
import { Box, Typography, CircularProgress, Paper, Chip } from "@mui/material";

export default function GanttPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["gantt"],
    queryFn: advancedMetricsApi.gantt,
  });

  if (isLoading) return <CircularProgress />;

  const tasks = data?.tasks || [];
  const sprints = data?.sprints || [];

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Gantt Chart</Typography>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Sprints</Typography>
        {sprints.map((s: any) => (
          <Box key={s.id} sx={{ my: 1, display: "flex", gap: 2, alignItems: "center" }}>
            <Chip label={s.name} size="small" color="primary" />
            <Typography variant="body2">{s.start_date} → {s.end_date}</Typography>
            <Chip label={s.state} size="small" variant="outlined" />
          </Box>
        ))}
      </Paper>
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6">Tareas ({tasks.length})</Typography>
        {tasks.map((t: any) => (
          <Box key={t.id} sx={{ my: 1, display: "flex", gap: 2, alignItems: "center", borderBottom: "1px solid #eee", pb: 1 }}>
            <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: t.project_color }} />
            <Typography sx={{ flex: 1 }}>{t.title}</Typography>
            <Chip label={t.state} size="small" variant="outlined" />
            <Typography variant="caption" color="textSecondary">
              {t.start_date || "—"} → {t.due_date || "—"}
            </Typography>
            {t.story_points && <Chip label={`${t.story_points}pt`} size="small" />}
          </Box>
        ))}
      </Paper>
    </Box>
  );
}
