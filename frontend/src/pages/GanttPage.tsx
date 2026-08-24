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
  Tooltip,
} from "@mui/material";

const STATE_COLORS: Record<string, string> = {
  backlog: "#9e9e9e",
  pending: "#7986cb",
  in_progress: "#1976d2",
  review: "#fbc02d",
  completed: "#43a047",
  blocked: "#d32f2f",
  cancelled: "#757575",
  archived: "#bdbdbd",
};

const STATE_LABELS: Record<string, string> = {
  backlog: "Backlog",
  pending: "Pendiente",
  in_progress: "En progreso",
  review: "En revisión",
  completed: "Completada",
  blocked: "Bloqueada",
  cancelled: "Cancelada",
  archived: "Archivada",
};

const DAY_MS = 24 * 3600 * 1000;
const LABEL_WIDTH = 180;
const DAY_WIDTH = 38; // px per day in the timeline
const ROW_HEIGHT = 28;
const BAR_HEIGHT = 24;

function parseDate(s: string | null | undefined): number | null {
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d.getTime();
}

/** Normalize a timestamp to the start of its day (local time). */
function startOfDay(ts: number): number {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** Format a timestamp as dd/MM. */
function fmtDayMonth(ts: number): string {
  const d = new Date(ts);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}`;
}

interface ResolvedRange {
  start: number;
  end: number;
}

/**
 * Resolve a task's start/end timestamps handling edge cases:
 * - no start_date but due_date  -> start = due - 1 day
 * - no due_date but start_date  -> end = start + 1 day
 * - start_date > due_date       -> swap
 * Returns null only when both dates are missing.
 */
function resolveRange(
  startRaw: number | null,
  endRaw: number | null,
): ResolvedRange | null {
  if (!startRaw && !endRaw) return null;
  let start = startRaw;
  let end = endRaw;
  if (!start && end) start = end - DAY_MS;
  if (!end && start) end = start + DAY_MS;
  if (start! > end!) [start, end] = [end, start];
  return { start: startOfDay(start!), end: startOfDay(end!) };
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
        <Alert severity="error">
          No se pudieron cargar los datos del Gantt.
        </Alert>
      </Box>
    );
  }

  const tasks: any[] = data?.tasks || [];
  const sprints: any[] = data?.sprints || [];

  // Resolve date ranges per task (handles edge cases).
  const taskRanges: Record<number, ResolvedRange | null> = {};
  const allStarts: number[] = [];
  const allEnds: number[] = [];
  for (const t of tasks) {
    const range = resolveRange(parseDate(t.start_date), parseDate(t.due_date));
    taskRanges[t.id] = range;
    if (range) {
      allStarts.push(range.start);
      allEnds.push(range.end + DAY_MS); // end-of-day inclusive
    }
  }
  for (const sp of sprints) {
    const s = parseDate(sp.start_date);
    const e = parseDate(sp.end_date);
    if (s) allStarts.push(startOfDay(s));
    if (e) allEnds.push(startOfDay(e) + DAY_MS);
  }

  const hasData = tasks.length > 0 || sprints.length > 0;

  const minDate = allStarts.length ? Math.min(...allStarts) : Date.now();
  const maxDate = allEnds.length ? Math.max(...allEnds) : minDate + 7 * DAY_MS;
  const spanMs = Math.max(maxDate - minDate, DAY_MS);
  const numDays = Math.ceil(spanMs / DAY_MS);
  const timelineWidth = Math.max(numDays * DAY_WIDTH, 200);

  const dayLeft = (ts: number) => ((ts - minDate) / DAY_MS) * DAY_WIDTH;
  const dayWidth = (start: number, end: number) =>
    Math.max(((end - start) / DAY_MS + 1) * DAY_WIDTH, DAY_WIDTH * 0.5);

  // Today line
  const todayTs = startOfDay(Date.now());
  const todayInRange = todayTs >= minDate && todayTs <= maxDate;
  const todayLeft = dayLeft(todayTs);

  // Weekend days for shading
  const weekends: { left: number }[] = [];
  for (let i = 0; i < numDays; i++) {
    const ts = minDate + i * DAY_MS;
    const dow = new Date(ts).getDay();
    if (dow === 0 || dow === 6) weekends.push({ left: i * DAY_WIDTH });
  }

  // Timeline header ticks: one label per day, but thin out if too many.
  const labelEvery = Math.max(1, Math.ceil(numDays / Math.floor(timelineWidth / 50)));
  const dayTicks: { label: string; left: number; isWeekend: boolean }[] = [];
  for (let i = 0; i < numDays; i++) {
    const ts = minDate + i * DAY_MS;
    const dow = new Date(ts).getDay();
    dayTicks.push({
      label: fmtDayMonth(ts),
      left: i * DAY_WIDTH,
      isWeekend: dow === 0 || dow === 6,
    });
  }

  // Group tasks by project
  const byProject: Record<string, any[]> = {};
  for (const t of tasks) {
    const key = t.project || "Sin proyecto";
    (byProject[key] ||= []).push(t);
  }
  const projects = Object.keys(byProject);

  return (
    <Box maxWidth={1280} mx="auto">
      <Typography variant="h5" fontWeight={700} mb={2}>
        Gantt Chart
      </Typography>

      {/* Legend */}
      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {Object.keys(STATE_COLORS).map((k) => (
            <Stack
              key={k}
              direction="row"
              spacing={0.5}
              alignItems="center"
            >
              <Box
                sx={{
                  width: 14,
                  height: 14,
                  borderRadius: 0.5,
                  bgcolor: STATE_COLORS[k],
                  border: "1px solid rgba(0,0,0,0.15)",
                }}
              />
              <Typography variant="caption">{STATE_LABELS[k]}</Typography>
            </Stack>
          ))}
        </Stack>
      </Paper>

      {/* Sprints overview */}
      {sprints.length > 0 && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6" mb={1}>Sprints</Typography>
          <Box sx={{ overflowX: "auto" }}>
            <Box sx={{ width: LABEL_WIDTH + timelineWidth, minWidth: "100%" }}>
              <Stack spacing={0.75}>
                {sprints.map((s) => {
                  const sStart = parseDate(s.start_date);
                  const sEnd = parseDate(s.end_date);
                  if (!sStart || !sEnd) return null;
                  const left = dayLeft(startOfDay(sStart));
                  const width = Math.max(
                    ((startOfDay(sEnd) - startOfDay(sStart)) / DAY_MS + 1) * DAY_WIDTH,
                    DAY_WIDTH,
                  );
                  return (
                    <Box
                      key={s.id}
                      sx={{ position: "relative", height: 24, display: "flex" }}
                    >
                      <Box
                        sx={{
                          width: LABEL_WIDTH,
                          flexShrink: 0,
                          pr: 1,
                          overflow: "hidden",
                          display: "flex",
                          alignItems: "center",
                        }}
                      >
                        <Typography variant="caption" fontWeight={600} noWrap>
                          {s.name}
                        </Typography>
                      </Box>
                      <Box
                        sx={{
                          position: "relative",
                          height: "100%",
                          width: timelineWidth,
                          flexShrink: 0,
                        }}
                      >
                        <Box
                          sx={{
                            position: "absolute",
                            left,
                            width,
                            top: 2,
                            bottom: 2,
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
                            left: left + 4,
                            top: 0,
                            height: "100%",
                            display: "flex",
                            alignItems: "center",
                            pointerEvents: "none",
                          }}
                        >
                          <Typography variant="caption" fontWeight={600} noWrap>
                            {s.name}
                          </Typography>
                        </Box>
                        <Box
                          sx={{
                            position: "absolute",
                            right: 0,
                            top: 0,
                            height: "100%",
                            display: "flex",
                            alignItems: "center",
                          }}
                        >
                          <Chip
                            label={s.state}
                            size="small"
                            variant="outlined"
                            sx={{ height: 18, fontSize: 10 }}
                          />
                        </Box>
                      </Box>
                    </Box>
                  );
                })}
              </Stack>
            </Box>
          </Box>
        </Paper>
      )}

      {/* Gantt chart */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" mb={2}>
          Tareas ({tasks.length})
        </Typography>

        {!hasData && (
          <Alert severity="info" sx={{ mt: 1 }}>
            No hay tareas ni sprints con fechas para mostrar en el Gantt. Asigna
            fechas de inicio o entrega a tus tareas para verlas aquí.
          </Alert>
        )}

        {hasData && (
          <Box sx={{ overflowX: "auto", border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
            <Box sx={{ width: LABEL_WIDTH + timelineWidth, minWidth: "100%" }}>
              {/* Timeline header */}
              <Box sx={{ display: "flex", height: 26, borderBottom: "1px solid", borderColor: "divider", bgcolor: "grey.50" }}>
                <Box
                  sx={{
                    width: LABEL_WIDTH,
                    flexShrink: 0,
                    position: "sticky",
                    left: 0,
                    zIndex: 3,
                    bgcolor: "grey.50",
                    borderRight: "1px solid",
                    borderColor: "divider",
                    display: "flex",
                    alignItems: "center",
                    pl: 1,
                  }}
                >
                  <Typography variant="caption" fontWeight={700} color="text.secondary">
                    Tarea
                  </Typography>
                </Box>
                <Box sx={{ position: "relative", width: timelineWidth, flexShrink: 0, height: "100%" }}>
                  {/* weekend shading in header */}
                  {weekends.map((w, i) => (
                    <Box
                      key={`hw-${i}`}
                      sx={{
                        position: "absolute",
                        left: w.left,
                        top: 0,
                        bottom: 0,
                        width: DAY_WIDTH,
                        bgcolor: "grey.200",
                      }}
                    />
                  ))}
                  {dayTicks.map((tk, i) =>
                    i % labelEvery === 0 ? (
                      <Box
                        key={i}
                        sx={{
                          position: "absolute",
                          left: tk.left,
                          top: 0,
                          height: "100%",
                          display: "flex",
                          alignItems: "center",
                          pl: 0.5,
                          fontSize: 11,
                          color: tk.isWeekend ? "text.disabled" : "text.secondary",
                          whiteSpace: "nowrap",
                          borderLeft: "1px solid",
                          borderColor: "divider",
                        }}
                      >
                        {tk.label}
                      </Box>
                    ) : null,
                  )}
                  {todayInRange && (
                    <Box
                      sx={{
                        position: "absolute",
                        left: todayLeft,
                        top: 0,
                        bottom: 0,
                        width: 2,
                        bgcolor: "error.main",
                        zIndex: 2,
                      }}
                    />
                  )}
                </Box>
              </Box>

              {/* Rows grouped by project */}
              <Stack spacing={0}>
                {projects.map((proj, projIdx) => {
                  const projTasks = byProject[proj];
                  const projColor =
                    projTasks[0]?.project_color || "#1976d2";
                  return (
                    <Box key={proj}>
                      {/* Project group header */}
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          height: 30,
                          pl: 1,
                          pr: 1,
                          bgcolor: "grey.100",
                          borderLeft: `4px solid ${projColor}`,
                          borderBottom: "1px solid",
                          borderColor: "divider",
                        }}
                      >
                        <Typography variant="subtitle2" fontWeight={700}>
                          {proj}
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ ml: 1 }}
                        >
                          ({projTasks.length})
                        </Typography>
                      </Box>

                      {projTasks.map((t) => {
                        const range = taskRanges[t.id];
                        const barColor =
                          STATE_COLORS[t.state] || t.project_color || "#1976d2";
                        return (
                          <Box
                            key={t.id}
                            sx={{
                              display: "flex",
                              height: ROW_HEIGHT,
                              borderBottom: "1px solid",
                              borderColor: "divider",
                              "&:hover": { bgcolor: "action.hover" },
                            }}
                          >
                            {/* sticky label */}
                            <Box
                              sx={{
                                width: LABEL_WIDTH,
                                flexShrink: 0,
                                position: "sticky",
                                left: 0,
                                zIndex: 2,
                                bgcolor: "background.paper",
                                borderRight: "1px solid",
                                borderColor: "divider",
                                pr: 1,
                                pl: 1,
                                overflow: "hidden",
                                display: "flex",
                                alignItems: "center",
                              }}
                            >
                              <Typography variant="caption" noWrap title={t.title}>
                                {t.title}
                              </Typography>
                            </Box>

                            {/* timeline cell */}
                            <Box
                              sx={{
                                position: "relative",
                                width: timelineWidth,
                                flexShrink: 0,
                                height: "100%",
                              }}
                            >
                              {/* weekend shading */}
                              {weekends.map((w, i) => (
                                <Box
                                  key={`rw-${t.id}-${i}`}
                                  sx={{
                                    position: "absolute",
                                    left: w.left,
                                    top: 0,
                                    bottom: 0,
                                    width: DAY_WIDTH,
                                    bgcolor: "grey.100",
                                  }}
                                />
                              ))}
                              {/* vertical day gridlines */}
                              {dayTicks.map((tk, i) =>
                                i % labelEvery === 0 ? (
                                  <Box
                                    key={`gl-${t.id}-${i}`}
                                    sx={{
                                      position: "absolute",
                                      left: tk.left,
                                      top: 0,
                                      bottom: 0,
                                      width: 1,
                                      bgcolor: "divider",
                                      opacity: 0.6,
                                    }}
                                  />
                                ) : null,
                              )}
                              {/* today line */}
                              {todayInRange && (
                                <Box
                                  sx={{
                                    position: "absolute",
                                    left: todayLeft,
                                    top: 0,
                                    bottom: 0,
                                    width: 2,
                                    bgcolor: "error.main",
                                    opacity: 0.85,
                                    zIndex: 1,
                                  }}
                                />
                              )}

                              {range ? (
                                (() => {
                                  const left = dayLeft(range.start);
                                  const width = dayWidth(range.start, range.end);
                                  const showText = width > 60;
                                  const tooltipTitle = `${t.title} — ${t.start_date || "(implícita)"} → ${t.due_date || "(implícita)"} · ${STATE_LABELS[t.state] || t.state}`;
                                  return (
                                    <Tooltip title={tooltipTitle} arrow placement="top">
                                      <Box
                                        sx={{
                                          position: "absolute",
                                          left,
                                          width,
                                          top: (ROW_HEIGHT - BAR_HEIGHT) / 2,
                                          height: BAR_HEIGHT,
                                          bgcolor: barColor,
                                          borderRadius: 1,
                                          display: "flex",
                                          alignItems: "center",
                                          px: 0.75,
                                          overflow: "hidden",
                                          color: "#fff",
                                          boxShadow: 1,
                                          minWidth: 6,
                                        }}
                                      >
                                        {showText && (
                                          <Typography
                                            variant="caption"
                                            noWrap
                                            sx={{ fontSize: 10, lineHeight: 1, fontWeight: 600 }}
                                          >
                                            {t.story_points ? `${t.story_points}pt · ` : ""}
                                            {STATE_LABELS[t.state] || t.state}
                                          </Typography>
                                        )}
                                      </Box>
                                    </Tooltip>
                                  );
                                })()
                              ) : (
                                <Box
                                  sx={{
                                    position: "absolute",
                                    left: 4,
                                    top: (ROW_HEIGHT - BAR_HEIGHT) / 2,
                                    height: BAR_HEIGHT,
                                    display: "flex",
                                    alignItems: "center",
                                  }}
                                >
                                  <Typography variant="caption" color="text.disabled">
                                    Sin fechas
                                  </Typography>
                                </Box>
                              )}
                            </Box>
                          </Box>
                        );
                      })}
                      {projIdx < projects.length - 1 && (
                        <Divider sx={{ borderColor: "divider" }} />
                      )}
                    </Box>
                  );
                })}
              </Stack>
            </Box>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
