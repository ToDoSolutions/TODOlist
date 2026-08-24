import { useQuery } from "@tanstack/react-query";
import { advancedMetricsApi } from "../api/resources";
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Chip,
  Alert,
  Stack,
  Divider,
} from "@mui/material";

const STATE_COLORS: Record<string, string> = {
  todo: "#9e9e9e",
  in_progress: "#1976d2",
  in_review: "#fbc02d",
  completed: "#43a047",
  blocked: "#d32f2f",
  cancelled: "#757575",
  archived: "#bdbdbd",
};

function parseDate(s: string | null | undefined): number | null {
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d.getTime();
}

export default function GanttPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["gantt"],
    queryFn: advancedMetricsApi.gantt,
  });

  if (isLoading) return <CircularProgress />;

  if (isError) {
    return (
      <Box maxWidth={1200} mx="auto" mt={4}>
        <Alert severity="error">No se pudieron cargar los datos del Gantt.</Alert>
      </Box>
    );
  }

  const tasks: any[] = data?.tasks || [];
  const sprints: any[] = data?.sprints || [];

  // Compute global date range across tasks + sprints
  const allStarts: number[] = [];
  const allEnds: number[] = [];
  for (const t of tasks) {
    const s = parseDate(t.start_date);
    const e = parseDate(t.due_date);
    if (s) allStarts.push(s);
    if (e) allEnds.push(e);
    else if (s) allEnds.push(s + 24 * 3600 * 1000);
  }
  for (const sp of sprints) {
    const s = parseDate(sp.start_date);
    const e = parseDate(sp.end_date);
    if (s) allStarts.push(s);
    if (e) allEnds.push(e);
  }

  const minDate = allStarts.length ? Math.min(...allStarts) : Date.now();
  const maxDate = allEnds.length ? Math.max(...allEnds) : minDate + 7 * 24 * 3600 * 1000;
  const span = Math.max(maxDate - minDate, 24 * 3600 * 1000);

  const pct = (ts: number) => ((ts - minDate) / span) * 100;

  // Build timeline header ticks (up to ~10 labels)
  const tickCount = Math.min(10, Math.ceil(span / (24 * 3600 * 1000)));
  const ticks: { label: string; pct: number }[] = [];
  for (let i = 0; i <= tickCount; i++) {
    const ts = minDate + (span * i) / tickCount;
    ticks.push({ label: new Date(ts).toISOString().slice(0, 10), pct: (i / tickCount) * 100 });
  }

  // Group tasks by project
  const byProject: Record<string, any[]> = {};
  for (const t of tasks) {
    const key = t.project || "Sin proyecto";
    (byProject[key] ||= []).push(t);
  }
  const projects = Object.keys(byProject);

  return (
    <Box maxWidth={1200} mx="auto">
      <Typography variant="h5" fontWeight={700} mb={2}>
        Gantt Chart
      </Typography>

      {/* Sprints overview */}
      {sprints.length > 0 && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6" mb={1}>Sprints</Typography>
          <Stack spacing={0.75}>
            {sprints.map((s) => {
              const sStart = parseDate(s.start_date);
              const sEnd = parseDate(s.end_date);
              if (!sStart || !sEnd) return null;
              const left = pct(sStart);
              const width = Math.max(pct(sEnd) - left, 1);
              return (
                <Box key={s.id} sx={{ position: "relative", height: 22 }}>
                  <Box
                    sx={{
                      position: "absolute",
                      left: `${left}%`,
                      width: `${width}%`,
                      height: "100%",
                      bgcolor: "primary.light",
                      opacity: 0.25,
                      borderRadius: 1,
                      border: "1px solid",
                      borderColor: "primary.main",
                    }}
                  />
                  <Box
                    sx={{
                      position: "absolute",
                      left: `${left}%`,
                      top: 0,
                      height: "100%",
                      display: "flex",
                      alignItems: "center",
                      pl: 0.5,
                      pointerEvents: "none",
                    }}
                  >
                    <Typography variant="caption" fontWeight={600} noWrap>
                      {s.name}
                    </Typography>
                  </Box>
                  <Box sx={{ position: "absolute", right: 0, top: 0, height: "100%", display: "flex", alignItems: "center" }}>
                    <Chip label={s.state} size="small" variant="outlined" sx={{ height: 18, fontSize: 10 }} />
                  </Box>
                </Box>
              );
            })}
          </Stack>
        </Paper>
      )}

      {/* Gantt chart */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" mb={2}>Tareas ({tasks.length})</Typography>

        {tasks.length === 0 && <Typography color="text.secondary">Sin tareas con fechas</Typography>}

        {/* Timeline header */}
        <Box sx={{ position: "relative", height: 20, mb: 1, ml: "160px" }}>
          {ticks.map((tk, i) => (
            <Box
              key={i}
              sx={{
                position: "absolute",
                left: `${tk.pct}%`,
                top: 0,
                transform: "translateX(-50%)",
                fontSize: 10,
                color: "text.secondary",
                whiteSpace: "nowrap",
              }}
            >
              {tk.label}
            </Box>
          ))}
        </Box>

        {/* Rows grouped by project */}
        <Stack spacing={1.5}>
          {projects.map((proj) => (
            <Box key={proj}>
              <Typography variant="subtitle2" mb={0.5}>{proj}</Typography>
              <Stack spacing={0.5}>
                {byProject[proj].map((t) => {
                  const sStart = parseDate(t.start_date);
                  const sEnd = parseDate(t.due_date);
                  if (!sStart || !sEnd) {
                    return (
                      <Box key={t.id} sx={{ display: "flex", alignItems: "center", height: 24 }}>
                        <Box sx={{ width: 150, pr: 1, overflow: "hidden" }}>
                          <Typography variant="caption" noWrap>{t.title}</Typography>
                        </Box>
                        <Box sx={{ flex: 1, color: "text.disabled" }}>
                          <Typography variant="caption">Sin fechas</Typography>
                        </Box>
                      </Box>
                    );
                  }
                  const left = pct(sStart);
                  const width = Math.max(pct(sEnd) - left, 0.5);
                  const color = t.project_color || STATE_COLORS[t.state] || "#1976d2";
                  return (
                    <Box key={t.id} sx={{ display: "flex", alignItems: "center", height: 24 }}>
                      <Box sx={{ width: 150, pr: 1, overflow: "hidden" }}>
                        <Typography variant="caption" noWrap title={t.title}>{t.title}</Typography>
                      </Box>
                      <Box sx={{ flex: 1, position: "relative", height: "100%" }}>
                        {/* gridlines */}
                        {ticks.map((tk, i) => (
                          <Box
                            key={i}
                            sx={{
                              position: "absolute",
                              left: `${tk.pct}%`,
                              top: 0,
                              bottom: 0,
                              width: 1,
                              bgcolor: "divider",
                              opacity: 0.5,
                            }}
                          />
                        ))}
                        <Box
                          sx={{
                            position: "absolute",
                            left: `${left}%`,
                            width: `${width}%`,
                            top: 2,
                            bottom: 2,
                            bgcolor: color,
                            borderRadius: 1,
                            display: "flex",
                            alignItems: "center",
                            px: 0.5,
                            overflow: "hidden",
                            color: "#fff",
                            boxShadow: 1,
                          }}
                          title={`${t.title} — ${t.start_date} → ${t.due_date}`}
                        >
                          <Typography variant="caption" noWrap sx={{ fontSize: 10, lineHeight: 1 }}>
                            {t.story_points ? `${t.story_points}pt ` : ""}
                            {t.state}
                          </Typography>
                        </Box>
                      </Box>
                    </Box>
                  );
                })}
              </Stack>
              <Divider sx={{ mt: 1 }} />
            </Box>
          ))}
        </Stack>
      </Paper>
    </Box>
  );
}
