import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { advancedMetricsApi } from "../api/resources";
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Chip,
  Stack,
  LinearProgress,
  Tooltip,
} from "@mui/material";
import { Flag } from "lucide-react";
import { useNavigate } from "react-router-dom";

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
  const t = new Date(s).getTime();
  return isNaN(t) ? null : t;
}

export default function RoadmapPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery<RoadmapData>({
    queryKey: ["roadmap"],
    queryFn: () => advancedMetricsApi.roadmap(),
  });

  if (isLoading) return <CircularProgress sx={{ m: 4 }} />;
  if (isError || !data)
    return <Typography sx={{ m: 4 }}>{t("p.plan.roadmap.loadError")}</Typography>;

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

  return (
    <Box p={3} overflow="auto">
      <Typography variant="h5" gutterBottom>
        {t("p.plan.roadmap.title")}
      </Typography>
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
        {/* milestones */}
        <Stack direction="row" spacing={1} mb={2} ml={`${LABEL_WIDTH}px`}>
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
                    left: x(s),
                    cursor: m.kind === "task" ? "pointer" : "default",
                  }}
                />
              </Tooltip>
            ) : null;
          })}
        </Stack>
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
              <Stack ml={LABEL_WIDTH} spacing={0.5}>
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
