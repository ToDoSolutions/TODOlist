import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { advancedMetricsApi } from "../api/resources";
import {
  Box,
  Typography,
  Paper,
  Chip,
  Stack,
  LinearProgress,
  Tooltip,
} from "@mui/material";
import { Flag } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/ui/PageHeader";
import { PageSkeleton } from "../components/ui/skeletons";
import { ErrorState } from "../components/ui/states";

interface RoadmapTask {
  id: number;
  title: string;
  state: string;
  start: string | null;
  due: string | null;
}
interface RoadmapEpic {
  id: number;
  title: string;
  color: string;
  state: string;
  start: string | null;
  end: string | null;
  total: number;
  done: number;
  progress: number;
  tasks: RoadmapTask[];
}
interface Milestone {
  id: number;
  name: string;
  kind?: "sprint" | "task";
  start: string;
  end: string;
  state: string;
}
interface RoadmapData {
  epics: RoadmapEpic[];
  milestones: Milestone[];
}

const DAY_MS = 24 * 3600 * 1000;
const LABEL_WIDTH = 200;

function ts(s: string | null | undefined): number | null {
  if (!s) return null;
  // "YYYY-MM-DD" = fecha calendario, no instante UTC (mismo
  // off-by-one que Gantt en husos detrás de UTC).
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  const t = (m
    ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
    : new Date(s)
  ).getTime();
  return isNaN(t) ? null : t;
}

export default function RoadmapPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useQuery<RoadmapData>({
    queryKey: ["roadmap"],
    queryFn: () => advancedMetricsApi.roadmap(),
  });

  if (isLoading) return <PageSkeleton kind="table" />;
  if (isError || !data)
    return (
      <Box maxWidth={1200} mx="auto" mt={4}>
        <ErrorState
          title={t("p.plan.roadmap.loadError")}
          onRetry={() => void refetch()}
        />
      </Box>
    );

  // Rango global: min start → max end de epics y milestones
  const starts: number[] = [];
  const ends: number[] = [];
  for (const e of data.epics) {
    const s = ts(e.start);
    const en = ts(e.end);
    if (s) starts.push(s);
    if (en) ends.push(en);
  }
  for (const m of data.milestones) {
    const s = ts(m.start);
    const e = ts(m.end);
    if (s) starts.push(s);
    if (e) ends.push(e);
  }
  if (!starts.length)
    return <Typography sx={{ m: 4 }}>{t("p.plan.roadmap.empty")}</Typography>;

  const t0 = Math.min(...starts) - 3 * DAY_MS;
  const t1 = Math.max(...ends) + 7 * DAY_MS;
  const span = Math.max(t1 - t0, DAY_MS);
  const todayX = LABEL_WIDTH + ((Date.now() - t0) / span) * 800;

  const x = (t: number) => LABEL_WIDTH + ((t - t0) / span) * 800;

  // Reparto de milestones en filas: cada chip ocupa ~160px; si choca con
  // el borde derecho del chip previo de la misma fila, baja a la siguiente.
  const milestoneRow = new Map<string, number>();
  const rowEdges: number[] = [];
  for (const m of data.milestones) {
    const s = ts(m.start);
    if (!s) continue;
    const left = x(s);
    const est = Math.min(m.name.length * 7 + 32, 220);
    let r = rowEdges.findIndex((edge) => edge <= left);
    if (r < 0) {
      r = rowEdges.length;
      rowEdges.push(0);
    }
    rowEdges[r] = left + est;
    milestoneRow.set(`${m.kind ?? "sprint"}-${m.id}`, r);
  }
  const milestoneRows = Math.max(rowEdges.length, 1);

  return (
    <Box p={3} overflow="auto">
      <PageHeader title={t("p.plan.roadmap.title")} />
      <Paper sx={{ position: "relative", p: 2, minWidth: LABEL_WIDTH + 800 }}>
        {/* línea de hoy */}
        <Box
          sx={{
            position: "absolute",
            left: todayX,
            top: 16,
            bottom: 16,
            width: 2,
            bgcolor: "error.main",
            opacity: 0.5,
          }}
        />
        {/* milestones — chips absolutos por fecha; se reparten en filas
             para que los labels no se solapen cuando dos sprints están
             cerca en el tiempo */}
        <Box mb={2} ml={`${LABEL_WIDTH}px`} sx={{ position: "relative", height: milestoneRows * 28 }}>
          {data.milestones.map((m) => {
            const s = ts(m.start);
            return s ? (
              <Tooltip
                key={`${m.kind ?? "sprint"}-${m.id}`}
                title={`${m.name} (${m.state})`}
              >
                <Chip
                  size="small"
                  label={m.name}
                  icon={m.kind === "task" ? <Flag size={12} /> : undefined}
                  color={
                    m.kind === "task"
                      ? "secondary"
                      : m.state === "active"
                        ? "primary"
                        : "default"
                  }
                  variant={m.kind === "task" ? "outlined" : "filled"}
                  clickable={m.kind === "task"}
                  onClick={
                    m.kind === "task" ? () => navigate(`/app/tasks/${m.id}`) : undefined
                  }
                  sx={{
                    position: "absolute",
                    left: x(s) - LABEL_WIDTH,
                    top: (milestoneRow.get(`${m.kind ?? "sprint"}-${m.id}`) ?? 0) * 28,
                    maxWidth: 220,
                    cursor: m.kind === "task" ? "pointer" : "default",
                  }}
                />
              </Tooltip>
            ) : null;
          })}
        </Box>
        {/* épica lanes */}
        {data.epics.map((epic) => {
          const s = ts(epic.start);
          const e = ts(epic.end);
          return (
            <Box key={epic.id} mb={2}>
              <Stack direction="row" alignItems="center" spacing={2}>
                <Box width={LABEL_WIDTH - 20}>
                  <Typography variant="subtitle2" noWrap>
                    {epic.title}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={epic.progress}
                    sx={{ height: 4, borderRadius: 2 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {epic.done}/{epic.total} · {epic.progress}%
                  </Typography>
                </Box>
                <Box sx={{ position: "relative", width: 800, height: 26 }}>
                  {s && e ? (
                    <Tooltip title={`${epic.start} → ${epic.end}`}>
                      <Box
                        sx={{
                          position: "absolute",
                          left: x(s) - LABEL_WIDTH,
                          width: Math.max(((e - s) / span) * 800, 8),
                          height: 22,
                          borderRadius: 1,
                          bgcolor: epic.color || "#9c27b0",
                          opacity: 0.85,
                        }}
                      />
                    </Tooltip>
                  ) : (
                    <Typography variant="caption" color="text.disabled">
                      {t("p.plan.roadmap.noDates")}
                    </Typography>
                  )}
                </Box>
              </Stack>
              {/* tareas de la épica */}
              <Stack ml={`${LABEL_WIDTH}px`} spacing={0.5}>
                {epic.tasks.slice(0, 8).map((t) => (
                  <Typography
                    key={t.id}
                    variant="caption"
                    color={t.state === "completed" ? "success.main" : "text.secondary"}
                  >
                    · {t.title}
                  </Typography>
                ))}
                {epic.tasks.length > 8 && (
                  <Typography variant="caption" color="text.disabled">
                    {t("p.plan.roadmap.moreTasks", {
                      count: epic.tasks.length - 8,
                    })}
                  </Typography>
                )}
              </Stack>
            </Box>
          );
        })}
      </Paper>
    </Box>
  );
}
