import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Stack,
  LinearProgress,
  Alert,
  Divider,
  useTheme,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle,
  AlertCircle,
  Clock,
  Ban,
  TrendingUp,
  Activity,
  Gauge,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { tasksApi } from "../api/resources";
import { STATE_COLORS, TYPE_COLORS } from "../types";
import { DashboardSkeleton } from "../components/ui/skeletons";
import OnboardingChecklist from "../components/OnboardingChecklist";

export default function DashboardPage() {
  const theme = useTheme();
  const { t } = useTranslation();
  const stateLabel = (s: string) =>
    t(`task.state.${s === "review" ? "in_review" : s}`, { defaultValue: s });
  const typeLabel = (s: string) => t(`p.collab.type.${s}`, { defaultValue: s });
  const {
    data: dashboard,
    isLoading: loadingDash,
    isError: errorDash,
  } = useQuery({
    queryKey: ["metrics-dashboard"],
    queryFn: tasksApi.metricsDashboard,
  });

  const { data: flow } = useQuery({
    queryKey: ["metrics-flow"],
    queryFn: () => tasksApi.metricsFlow(30),
  });

  const { data: backlog } = useQuery({
    queryKey: ["metrics-backlog"],
    queryFn: tasksApi.metricsBacklog,
  });

  const { data: prs } = useQuery({
    queryKey: ["metrics-prs"],
    queryFn: tasksApi.metricsPRs,
  });

  if (loadingDash) {
    return (
      <Box maxWidth={1000} mx="auto">
        <DashboardSkeleton />
      </Box>
    );
  }

  if (errorDash) {
    return (
      <Box maxWidth={1000} mx="auto" mt={4}>
        <Alert severity="error">{t("p.collab.dashboard.errorLoad")}</Alert>
      </Box>
    );
  }

  const statCard = (
    label: string,
    value: number | string,
    color: string,
    icon: React.ReactNode,
  ) => (
    <Card variant="outlined">
      <CardContent sx={{ py: 2 }}>
        <Stack direction="row" alignItems="center" spacing={1.5}>
          <Box sx={{ color }}>{icon}</Box>
          <Box>
            <Typography variant="h5" fontWeight={700}>
              {value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {label}
            </Typography>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );

  return (
    <Box maxWidth={1000} mx="auto">
      <Typography variant="h5" fontWeight={700} mb={3}>
        {t("p.collab.dashboard.title")}
      </Typography>

      {/* Checklist de primeros pasos (auto-ocultable) */}
      <OnboardingChecklist />

      {/* KPIs principales */}
      <Grid container spacing={2} mb={3}>
        <Grid item xs={6} sm={3}>
          {statCard(
            t("p.collab.dashboard.open"),
            dashboard?.open ?? 0,
            "#1976d2",
            <Clock size={28} />,
          )}
        </Grid>
        <Grid item xs={6} sm={3}>
          {statCard(
            t("p.collab.dashboard.completed"),
            dashboard?.completed ?? 0,
            "#43a047",
            <CheckCircle size={28} />,
          )}
        </Grid>
        <Grid item xs={6} sm={3}>
          {statCard(
            t("p.collab.dashboard.overdue"),
            dashboard?.overdue ?? 0,
            "#d32f2f",
            <AlertCircle size={28} />,
          )}
        </Grid>
        <Grid item xs={6} sm={3}>
          {statCard(
            t("p.collab.dashboard.blocked"),
            dashboard?.blocked ?? 0,
            "#e65100",
            <Ban size={28} />,
          )}
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Métricas de flujo */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={2}>
                <TrendingUp size={20} style={{ color: theme.palette.primary.main }} />
                <Typography variant="h6">
                  {t("p.collab.dashboard.flowMetrics", { days: 30 })}
                </Typography>
              </Stack>
              {flow && (
                <Stack spacing={1.5}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.throughput")}
                    </Typography>
                    <Chip
                      label={t("p.collab.dashboard.throughputCompleted", {
                        count: flow.throughput,
                      })}
                      size="small"
                      color="success"
                    />
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.created")}
                    </Typography>
                    <Chip label={flow.created} size="small" />
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">{t("p.collab.dashboard.wip")}</Typography>
                    <Chip label={flow.wip} size="small" color="primary" />
                  </Stack>
                  <Divider />
                  <Typography variant="subtitle2">
                    {t("p.collab.dashboard.leadTime")}
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Chip
                      label={t("p.collab.dashboard.mean", {
                        value: flow.lead_time.mean,
                      })}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={t("p.collab.dashboard.median", {
                        value: flow.lead_time.median,
                      })}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={`P90: ${flow.lead_time.p90}`}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={`P95: ${flow.lead_time.p95}`}
                      size="small"
                      variant="outlined"
                    />
                  </Stack>
                  <Typography variant="subtitle2">
                    {t("p.collab.dashboard.cycleTime")}
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Chip
                      label={t("p.collab.dashboard.mean", {
                        value: flow.cycle_time.mean,
                      })}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={t("p.collab.dashboard.median", {
                        value: flow.cycle_time.median,
                      })}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={`P90: ${flow.cycle_time.p90}`}
                      size="small"
                      variant="outlined"
                    />
                  </Stack>
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Salud del backlog */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={2}>
                <Gauge size={20} style={{ color: theme.palette.secondary.main }} />
                <Typography variant="h6">
                  {t("p.collab.dashboard.backlogHealth")}
                </Typography>
              </Stack>
              {backlog && (
                <Stack spacing={1.5}>
                  <Box>
                    <Stack direction="row" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2">
                        {t("p.collab.dashboard.healthScore")}
                      </Typography>
                      <Typography
                        variant="body2"
                        fontWeight={700}
                        color={
                          backlog.health_score > 70
                            ? "success.main"
                            : backlog.health_score > 40
                              ? "warning.main"
                              : "error.main"
                        }
                      >
                        {backlog.health_score}/100
                      </Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={backlog.health_score}
                      color={
                        backlog.health_score > 70
                          ? "success"
                          : backlog.health_score > 40
                            ? "warning"
                            : "error"
                      }
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>
                  <Divider />
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.openTasks")}
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {backlog.total_open}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">Antiguas ({">"}30d)</Typography>
                    <Typography
                      variant="body2"
                      color={backlog.old_tasks_30d > 0 ? "error.main" : "text.secondary"}
                    >
                      {backlog.old_tasks_30d}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.noEstimate")}
                    </Typography>
                    <Typography
                      variant="body2"
                      color={backlog.no_estimate > 0 ? "warning.main" : "text.secondary"}
                    >
                      {backlog.no_estimate}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.noDueDate")}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {backlog.no_due_date}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.reopened")}
                    </Typography>
                    <Typography
                      variant="body2"
                      color={backlog.reopened_30d > 0 ? "warning.main" : "text.secondary"}
                    >
                      {backlog.reopened_30d}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.avgAge")}
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {backlog.avg_age_days} días
                    </Typography>
                  </Stack>
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Distribución por estado */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={2}>
                <Activity size={20} style={{ color: theme.palette.success.main }} />
                <Typography variant="h6">{t("p.collab.dashboard.byState")}</Typography>
              </Stack>
              {dashboard?.by_state && (
                <Stack spacing={1}>
                  {Object.entries(dashboard.by_state).map(([state, count]) => (
                    <Stack key={state} direction="row" alignItems="center" spacing={1}>
                      <Box
                        sx={{
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          bgcolor:
                            STATE_COLORS[state as keyof typeof STATE_COLORS] || "#999",
                        }}
                      />
                      <Typography variant="body2" sx={{ flex: 1 }}>
                        {stateLabel(state)}
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {String(count)}
                      </Typography>
                    </Stack>
                  ))}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Distribución por tipo */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={2}>
                <Activity size={20} style={{ color: theme.palette.info.main }} />
                <Typography variant="h6">{t("p.collab.dashboard.byType")}</Typography>
              </Stack>
              {dashboard?.by_type && (
                <Stack spacing={1}>
                  {Object.entries(dashboard.by_type).map(
                    ([type, count]) =>
                      Number(count) > 0 && (
                        <Stack key={type} direction="row" alignItems="center" spacing={1}>
                          <Chip
                            size="small"
                            label={typeLabel(type)}
                            sx={{
                              bgcolor:
                                TYPE_COLORS[type as keyof typeof TYPE_COLORS] || "#999",
                              color: "common.white",
                              height: 18,
                              fontSize: 10,
                            }}
                          />
                          <Typography variant="body2" sx={{ flex: 1 }} />
                          <Typography variant="body2" fontWeight={600}>
                            {String(count)}
                          </Typography>
                        </Stack>
                      ),
                  )}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Sprint activo */}
        {dashboard?.active_sprint && (
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" mb={2}>
                  Sprint activo: {dashboard.active_sprint.sprint_name}
                </Typography>
                <Box mb={1}>
                  <LinearProgress
                    variant="determinate"
                    value={dashboard.active_sprint.progress_pct}
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                </Box>
                <Stack direction="row" justifyContent="space-between" mb={1}>
                  <Typography variant="caption">
                    {dashboard.active_sprint.done}/{dashboard.active_sprint.total_tasks}{" "}
                    tareas
                  </Typography>
                  <Typography variant="caption" fontWeight={700}>
                    {dashboard.active_sprint.progress_pct}%
                  </Typography>
                </Stack>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Chip
                    label={`SP: ${dashboard.active_sprint.story_points_done}/${dashboard.active_sprint.story_points_total}`}
                    size="small"
                    variant="outlined"
                  />
                  <Chip
                    label={`Bloqueadas: ${dashboard.active_sprint.blocked}`}
                    size="small"
                    color={dashboard.active_sprint.blocked > 0 ? "error" : "default"}
                  />
                  <Chip
                    label={`Scope creep: ${dashboard.active_sprint.scope_creep_pct}%`}
                    size="small"
                    color={
                      dashboard.active_sprint.scope_creep_pct > 20 ? "warning" : "default"
                    }
                  />
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* PRs */}
        {prs && prs.total > 0 && (
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" mb={2}>
                  Pull requests
                </Typography>
                <Stack spacing={1}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.open")}
                    </Typography>
                    <Chip label={prs.open} size="small" color="primary" />
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      {t("p.collab.dashboard.prsMerged")}
                    </Typography>
                    <Chip label={prs.merged} size="small" color="success" />
                  </Stack>
                  {prs.stale_7d > 0 && (
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2">
                        {t("p.collab.dashboard.prsStale")}
                      </Typography>
                      <Chip label={prs.stale_7d} size="small" color="warning" />
                    </Stack>
                  )}
                  {prs.ci_failed > 0 && (
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2">
                        {t("p.collab.dashboard.ciFailed")}
                      </Typography>
                      <Chip label={prs.ci_failed} size="small" color="error" />
                    </Stack>
                  )}
                  {prs.merge_time.count > 0 && (
                    <>
                      <Divider />
                      <Typography variant="caption" color="text.secondary">
                        Tiempo hasta fusión (días)
                      </Typography>
                      <Stack direction="row" spacing={1}>
                        <Chip
                          label={`Media: ${prs.merge_time.mean}`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={`Mediana: ${prs.merge_time.median}`}
                          size="small"
                          variant="outlined"
                        />
                      </Stack>
                    </>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Tendencia del backlog */}
        {dashboard?.backlog_trend && (
          <Grid item xs={12}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" mb={2}>
                  Tendencia del backlog (últimos 7 días)
                </Typography>
                <BacklogTrendChart data={dashboard.backlog_trend} />
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

function BacklogTrendChart({ data }: { data: { date: string; backlog: number }[] }) {
  if (!data || data.length === 0) return null;
  const maxVal = Math.max(...data.map((d) => d.backlog), 1);
  return (
    <Stack
      direction="row"
      spacing={1}
      alignItems="flex-end"
      sx={{ height: 120, overflowX: "auto" }}
    >
      {data.map((d) => (
        <Box key={d.date} sx={{ textAlign: "center", minWidth: 60 }}>
          <Box
            sx={{
              height: `${(d.backlog / maxVal) * 100}%`,
              minHeight: 4,
              bgcolor: "primary.main",
              borderRadius: "4px 4px 0 0",
              mb: 0.5,
            }}
          />
          <Typography variant="caption" color="text.secondary">
            {d.backlog}
          </Typography>
          <Typography
            variant="caption"
            display="block"
            color="text.secondary"
            sx={{ fontSize: 9 }}
          >
            {d.date.slice(5)}
          </Typography>
        </Box>
      ))}
    </Stack>
  );
}
