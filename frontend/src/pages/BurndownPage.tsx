import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { advancedMetricsApi, sprintsApi, type Sprint } from "../api/resources";
import { formatDate } from "../lib/dates";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";
import { TableSkeleton } from "../components/ui/skeletons";
import {
  Box,
  Typography,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Stack,
  Chip,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

type ChartMode = "burndown" | "burnup";

export default function BurndownPage() {
  const { t } = useTranslation();
  const [sprintId, setSprintId] = useState<number | "">("");
  const [mode, setMode] = useState<ChartMode>("burndown");
  const { data: sprintsData } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
  });
  const sprints: Sprint[] = sprintsData || [];

  // Preselecciona el sprint activo (o el último) — la página vacía con
  // "Selecciona un sprint" obligaba a un clic extra siempre.
  useEffect(() => {
    if (sprintId || sprints.length === 0) return;
    const active = sprints.find((s) => s.state === "active");
    const fallback = sprints[sprints.length - 1];
    const chosen = active ?? fallback;
    if (chosen) setSprintId(chosen.id);
  }, [sprints, sprintId]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["burndown", mode, sprintId],
    queryFn: () =>
      mode === "burnup"
        ? advancedMetricsApi.burnup(Number(sprintId))
        : advancedMetricsApi.burndown(Number(sprintId)),
    enabled: !!sprintId,
  });

  return (
    <Box maxWidth={1000} mx="auto">
      <PageHeader
        title={
          mode === "burnup"
            ? t("p.plan.burndown.titleBurnup")
            : t("p.plan.burndown.title")
        }
      />

      <Stack
        direction="row"
        spacing={2}
        alignItems="center"
        mb={2}
        flexWrap="wrap"
        useFlexGap
      >
        <FormControl sx={{ minWidth: 200 }} size="small">
          <InputLabel>{t("p.plan.burndown.sprintLabel")}</InputLabel>
          <Select
            value={sprintId}
            onChange={(e) => setSprintId(e.target.value as number)}
            label={t("p.plan.burndown.sprintLabel")}
          >
            {sprints.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <ToggleButtonGroup
          size="small"
          value={mode}
          exclusive
          onChange={(_, v) => v && setMode(v as ChartMode)}
        >
          <ToggleButton value="burndown">
            {t("p.plan.burndown.modeBurndown")}
          </ToggleButton>
          <ToggleButton value="burnup">{t("p.plan.burndown.modeBurnup")}</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {!sprintId && (
        <Typography color="text.secondary">
          {t("p.plan.burndown.selectSprint")}
        </Typography>
      )}
      {sprintId && isLoading && <TableSkeleton rows={6} cols={3} />}
      {sprintId && isError && (
        <ErrorState
          title={t("p.plan.burndown.loadError")}
          onRetry={() => void refetch()}
        />
      )}
      {sprintId &&
        data &&
        (mode === "burnup" ? <BurnupChart data={data} /> : <BurndownChart data={data} />)}
    </Box>
  );
}

interface BurndownData {
  ideal?: { date: string; ideal: number }[];
  actual?: { date: string; remaining: number }[];
  total_points?: number;
  total_tasks?: number;
  sprint?: { name?: string; start_date?: string; end_date?: string };
}
function BurndownChart({ data }: { data: BurndownData }) {
  const { t } = useTranslation();
  const ideal: { date: string; ideal: number }[] = data.ideal || [];
  const actual: { date: string; remaining: number }[] = data.actual || [];
  const totalPoints = data.total_points || 0;

  if (!ideal.length) {
    return (
      <Paper sx={{ p: 2 }}>
        <Typography color="text.secondary">{t("p.plan.burndown.noData")}</Typography>
      </Paper>
    );
  }

  const idealByDate = new Map(ideal.map((d) => [d.date, d.ideal]));
  const actualByDate = new Map(actual.map((a) => [a.date, a.remaining]));
  const dates = [...new Set([...idealByDate.keys(), ...actualByDate.keys()])].sort();
  const chartData = dates.map((date) => ({
    date: date.slice(5),
    ideal: idealByDate.get(date) ?? null,
    actual: actualByDate.get(date) ?? null,
  }));

  return (
    <Paper sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="h6">{data.sprint?.name}</Typography>
        <Stack direction="row" spacing={1}>
          <Chip
            label={t("p.plan.burndown.pointsChip", { count: totalPoints })}
            size="small"
            color="primary"
          />
          <Chip
            label={t("p.plan.burndown.tasksChip", {
              count: data.total_tasks ?? 0,
            })}
            size="small"
            variant="outlined"
          />
        </Stack>
      </Stack>
      <Typography variant="body2" color="text.secondary" mb={2}>
        {formatDate(data.sprint?.start_date)} → {formatDate(data.sprint?.end_date)}
      </Typography>

      <Box sx={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 10, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.4} />
            <XAxis dataKey="date" fontSize={11} tickLine={false} />
            <YAxis
              fontSize={11}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip />
            <Legend />
            <Line
              type="linear"
              dataKey="ideal"
              name={t("p.plan.burndown.ideal")}
              stroke="#9e9e9e"
              strokeWidth={2}
              strokeDasharray="5 3"
              dot={false}
            />
            <Line
              type="linear"
              dataKey="actual"
              name={t("p.plan.burndown.actual")}
              stroke="#1976d2"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Box>

      <Typography variant="caption" color="text.secondary" mt={1} display="block">
        {t("p.plan.burndown.axesHint")}
      </Typography>
    </Paper>
  );
}

interface BurnupData {
  series?: { date: string; completed: number; scope: number }[];
  total_points?: number;
  sprint?: { name?: string; start_date?: string; end_date?: string };
}
function BurnupChart({ data }: { data: BurnupData }) {
  const { t } = useTranslation();
  const series: { date: string; completed: number; scope: number }[] = data.series || [];
  const totalPoints = data.total_points || 0;

  if (!series.length) {
    return (
      <Paper sx={{ p: 2 }}>
        <Typography color="text.secondary">{t("p.plan.burndown.noData")}</Typography>
      </Paper>
    );
  }

  const chartData = series.map((p) => ({
    date: p.date.slice(5),
    completed: p.completed,
    scope: p.scope,
  }));

  return (
    <Paper sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="h6">{data.sprint?.name}</Typography>
        <Chip
          label={t("p.plan.burndown.pointsChip", { count: totalPoints })}
          size="small"
          color="primary"
        />
      </Stack>
      <Typography variant="body2" color="text.secondary" mb={2}>
        {formatDate(data.sprint?.start_date)} → {formatDate(data.sprint?.end_date)}
      </Typography>

      <Box sx={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 10, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.4} />
            <XAxis dataKey="date" fontSize={11} tickLine={false} />
            <YAxis
              fontSize={11}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip />
            <Legend />
            <Line
              type="stepAfter"
              dataKey="scope"
              name={t("p.plan.burndown.scope")}
              stroke="#9e9e9e"
              strokeWidth={2}
              strokeDasharray="5 3"
              dot={false}
            />
            <Line
              type="linear"
              dataKey="completed"
              name={t("p.plan.burndown.completed")}
              stroke="#2e7d32"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Box>

      <Typography variant="caption" color="text.secondary" mt={1} display="block">
        {t("p.plan.burndown.axesHintBurnup")}
      </Typography>
    </Paper>
  );
}
