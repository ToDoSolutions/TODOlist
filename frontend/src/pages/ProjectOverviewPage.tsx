import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Grid,
  Stack,
  Paper,
  Chip,
  Button,
  LinearProgress,
  Skeleton,
  Divider,
  Avatar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
} from "@mui/material";
import {
  AlertTriangle,
  Ban,
  CheckSquare,
  Flag,
  Folder,
  Plus,
  Settings,
  Activity as ActivityIcon,
  Users,
} from "lucide-react";
import { format, isPast, isToday, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import PageHeader from "../components/ui/PageHeader";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState } from "../components/ui/states";
import {
  projectsApi,
  tasksApi,
  sprintsApi,
  epicsApi,
  activityFeedApi,
  risksApi,
  collaborationApi,
  type Sprint,
  type Epic,
} from "../api/resources";
import {
  projectStatusUpdatesApi,
  PROJECT_HEALTHS,
  HEALTH_CHIP_COLORS,
  HEALTH_SX_COLORS,
  type ProjectHealth,
  type ProjectHealthFields,
} from "../api/featComp";
import type { Project } from "../types";
import { formatDateTime } from "../lib/dates";
import { notify } from "../notify";
import { useProject } from "../auth/ProjectContext";
import { useEffect, useState } from "react";

/**
 * Resumen de proyecto: identidad + salud + contexto.
 * El proyecto deja de ser "solo un filtro" y pasa a ser una entidad.
 */
export default function ProjectOverviewPage() {
  const { t } = useTranslation();
  const { projectId } = useParams();
  const id = Number(projectId);
  const navigate = useNavigate();
  const projectCtx = useProject();

  const [healthOpen, setHealthOpen] = useState(false);
  const qc = useQueryClient();

  // Actualización manual de estado (salud reportada)
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [statusForm, setStatusForm] = useState<{
    health: ProjectHealth;
    note: string;
  }>({ health: "on_track", note: "" });

  const { data: projectsData, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const project = (Array.isArray(projectsData) ? projectsData : []).find(
    (p) => p.id === id,
  ) as (Project & Partial<ProjectHealthFields>) | undefined;

  // Sincronizar el contexto de proyecto al entrar por URL directa
  useEffect(() => {
    if (project && projectCtx.project?.id !== project.id) {
      projectCtx.setProject({ id: project.id, name: project.name, color: project.color });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  const { data: tasksData } = useQuery({
    queryKey: ["tasks", { project: id }],
    queryFn: () => tasksApi.list({ project: id }),
    enabled: !!project,
  });
  const tasks = Array.isArray(tasksData) ? tasksData : [];

  const { data: sprintsData } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
  });
  const sprints: Sprint[] = (Array.isArray(sprintsData) ? sprintsData : []).filter(
    (s) => s.project === id,
  );
  const activeSprint = sprints.find((s) => s.state === "active");

  const { data: epicsData } = useQuery({ queryKey: ["epics"], queryFn: epicsApi.list });
  const epics: Epic[] = Array.isArray(epicsData) ? epicsData : [];

  const { data: members } = useQuery({
    queryKey: ["project-members", id],
    queryFn: () => collaborationApi.projectMembers.list(id),
    enabled: !!project,
  });

  const { data: risks } = useQuery({
    queryKey: ["project-risks", id],
    queryFn: () => risksApi.list(id),
    enabled: !!project,
  });

  const { data: activity } = useQuery({
    queryKey: ["activity-feed", 10],
    queryFn: () => activityFeedApi.list(10),
  });

  const { data: statusUpdates } = useQuery({
    queryKey: ["project-status-updates", id],
    queryFn: () => projectStatusUpdatesApi.list(id),
    enabled: !!project,
  });

  const createStatus = useMutation({
    mutationFn: () =>
      projectStatusUpdatesApi.create({
        project: id,
        health: statusForm.health,
        note: statusForm.note,
      }),
    onSuccess: () => {
      notify.success(t("p.org.health.saved"));
      // El POST sincroniza project.health → refrescar lista y historial.
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["project-status-updates", id] });
      setStatusDialogOpen(false);
    },
    onError: () => notify.error(t("p.org.health.saveError")),
  });

  if (isLoading) {
    return (
      <Box>
        <Skeleton height={80} />
        <Skeleton height={200} sx={{ mt: 2 }} />
      </Box>
    );
  }
  if (!project) {
    return (
      <EmptyState
        title={t("p.misc.projectNotFound")}
        description={t("p.misc.projectNotFoundDesc")}
        action={
          <Button onClick={() => navigate("/app/projects")}>
            {t("p.misc.viewProjects")}
          </Button>
        }
      />
    );
  }

  const open = tasks.filter(
    (task) => !["completed", "cancelled", "archived"].includes(task.state),
  );
  const overdue = open.filter(
    (task) =>
      task.due_date &&
      isPast(parseISO(task.due_date)) &&
      !isToday(parseISO(task.due_date)),
  );
  const blocked = tasks.filter((task) => task.state === "blocked");
  const done = tasks.filter((task) => task.state === "completed");
  const progress = tasks.length ? Math.round((done.length / tasks.length) * 100) : 0;
  const openRisks = (risks ?? []).filter((r) => r.status === "open");

  // Salud simple: vencidas/bloqueadas/riesgos ponderan.
  // factors explica el cálculo al usuario (se muestra al pulsar la salud).
  const healthFactors: string[] = [];
  if (overdue.length > 0)
    healthFactors.push(
      t("p.misc.projectOverview.factorOverdue", { count: overdue.length }) +
        (overdue.length > 3 ? t("p.misc.projectOverview.riskOver3") : ""),
    );
  if (blocked.length > 0)
    healthFactors.push(
      t("p.misc.projectOverview.factorBlocked", { count: blocked.length }) +
        (blocked.length > 3 ? t("p.misc.projectOverview.riskOver3") : ""),
    );
  if (openRisks.length > 0)
    healthFactors.push(
      t("p.misc.projectOverview.factorRisks", { count: openRisks.length }) +
        (openRisks.length > 2 ? t("p.misc.projectOverview.riskOver2") : ""),
    );
  if (healthFactors.length === 0)
    healthFactors.push(t("p.misc.projectOverview.factorHealthy"));

  const health =
    overdue.length > 3 || blocked.length > 3 || openRisks.length > 2
      ? {
          label: t("p.misc.projectOverview.healthRisk"),
          color: "error.main" as const,
        }
      : overdue.length > 0 || blocked.length > 0
        ? {
            label: t("p.misc.projectOverview.healthAttention"),
            color: "warning.main" as const,
          }
        : {
            label: t("p.misc.projectOverview.healthOnTime"),
            color: "success.main" as const,
          };

  return (
    <Box>
      <PageHeader
        title={project.name}
        description={project.description || t("p.misc.noDescription")}
        breadcrumbs={[
          { label: t("nav.projects"), to: "/app/projects" },
          { label: project.name },
          { label: t("p.misc.projectOverview.summary") },
        ]}
        actions={
          <>
            {project.health ? (
              <Chip
                size="small"
                color={HEALTH_CHIP_COLORS[project.health]}
                label={t(`p.org.health.${project.health}`)}
              />
            ) : (
              <Chip size="small" variant="outlined" label={t("p.org.health.unset")} />
            )}
            <Button
              variant="outlined"
              startIcon={<Settings size={15} />}
              onClick={() => navigate("/app/projects")}
            >
              {t("p.misc.projectOverview.configure")}
            </Button>
            <Button
              variant="contained"
              startIcon={<Plus size={15} />}
              onClick={() => navigate(`/app/project/${id}/tasks?new=1`)}
            >
              {t("p.misc.projectOverview.newTask")}
            </Button>
          </>
        }
      />

      {/* Identidad + salud */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
          <Avatar sx={{ bgcolor: project.color, width: 48, height: 48 }}>
            <Folder size={22} />
          </Avatar>
          <Box flex={1} minWidth={200}>
            <Typography variant="subtitle1" fontWeight={700}>
              {t("p.misc.projectOverview.health")}{" "}
              <Button
                size="small"
                variant="text"
                onClick={() => setHealthOpen(true)}
                sx={{
                  color: health.color,
                  fontWeight: 700,
                  p: 0,
                  minWidth: 0,
                  textTransform: "none",
                  fontSize: "inherit",
                  textDecoration: "underline dotted",
                }}
              >
                {health.label}
              </Button>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("p.misc.projectOverview.membersCount", {
                count: Array.isArray(members) ? members.length : 0,
              })}{" "}
              · {format(parseISO(project.created_at), "MMMM yyyy", { locale: es })}
            </Typography>
          </Box>
          <Box minWidth={200}>
            <Stack direction="row" justifyContent="space-between" mb={0.5}>
              <Typography variant="caption" color="text.secondary">
                {t("p.misc.projectOverview.progress")}
              </Typography>
              <Typography variant="caption" fontWeight={700}>
                {progress}%
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        </Stack>
      </Paper>

      <Grid container spacing={2} mb={3}>
        <Grid item xs={6} md={3}>
          <MetricCard
            title={t("p.misc.projectOverview.open")}
            value={open.length}
            icon={<CheckSquare size={18} />}
            onClick={() => navigate(`/app/project/${id}/tasks`)}
          />
        </Grid>
        <Grid item xs={6} md={3}>
          <MetricCard
            title={t("p.misc.projectOverview.overdue")}
            value={overdue.length}
            icon={<AlertTriangle size={18} />}
            color="error.main"
            onClick={() => navigate(`/app/project/${id}/tasks?view=list&state=pending`)}
          />
        </Grid>
        <Grid item xs={6} md={3}>
          <MetricCard
            title={t("p.misc.projectOverview.blocked")}
            value={blocked.length}
            icon={<Ban size={18} />}
            color="warning.main"
            onClick={() => navigate(`/app/project/${id}/tasks?view=list&state=blocked`)}
          />
        </Grid>
        <Grid item xs={6} md={3}>
          <MetricCard
            title={t("p.misc.projectOverview.openRisks")}
            value={openRisks.length}
            icon={<Flag size={18} />}
            onClick={() => navigate("/app/risks")}
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Stack spacing={3}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                {t("p.misc.projectOverview.activeSprint")}
              </Typography>
              {activeSprint ? (
                <Box>
                  <Typography variant="body2" fontWeight={600}>
                    {activeSprint.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {format(parseISO(activeSprint.start_date), "d MMM", { locale: es })} –{" "}
                    {format(parseISO(activeSprint.end_date), "d MMM", { locale: es })} ·{" "}
                    {t("p.misc.tasksCount", { count: activeSprint.task_count })}
                  </Typography>
                  {activeSprint.goal && (
                    <Typography variant="body2" color="text.secondary" mt={1}>
                      {t("p.misc.projectOverview.goal")}: {activeSprint.goal}
                    </Typography>
                  )}
                  <Button
                    size="small"
                    sx={{ mt: 1, textTransform: "none" }}
                    onClick={() => navigate("/app/backlog")}
                  >
                    {t("p.misc.projectOverview.goToPlanning")}
                  </Button>
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  {t("p.misc.projectOverview.noActiveSprint")}{" "}
                  <Button size="small" onClick={() => navigate("/app/sprints")}>
                    {t("p.misc.projectOverview.plan")}
                  </Button>
                </Typography>
              )}
            </Paper>

            {/* Estado reportado manualmente + historial */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                mb={1}
              >
                <Typography variant="subtitle1" fontWeight={700}>
                  {t("p.org.health.lastUpdate")}
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    setStatusForm({
                      health: project.health ?? "on_track",
                      note: "",
                    });
                    setStatusDialogOpen(true);
                  }}
                >
                  {t("p.org.health.update")}
                </Button>
              </Stack>
              {project.latest_status_update ? (
                <Box>
                  <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                    <Chip
                      size="small"
                      color={HEALTH_CHIP_COLORS[project.latest_status_update.health]}
                      label={t(`p.org.health.${project.latest_status_update.health}`)}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {project.latest_status_update.author_email} ·{" "}
                      {formatDateTime(project.latest_status_update.created_at)}
                    </Typography>
                  </Stack>
                  {project.latest_status_update.note && (
                    <Typography variant="body2">
                      {project.latest_status_update.note}
                    </Typography>
                  )}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  {t("p.org.health.noUpdates")}
                </Typography>
              )}
              {statusUpdates && statusUpdates.length > 0 && (
                <>
                  <Divider sx={{ my: 1.5 }} />
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    fontWeight={600}
                    display="block"
                    mb={0.5}
                  >
                    {t("p.org.health.history")}
                  </Typography>
                  <Stack spacing={0.75}>
                    {statusUpdates.slice(0, 5).map((u) => (
                      <Stack key={u.id} direction="row" spacing={1} alignItems="center">
                        <Box
                          sx={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            bgcolor: HEALTH_SX_COLORS[u.health],
                            flexShrink: 0,
                          }}
                        />
                        <Typography
                          variant="caption"
                          fontWeight={600}
                          sx={{ whiteSpace: "nowrap" }}
                        >
                          {t(`p.org.health.${u.health}`)}
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ whiteSpace: "nowrap" }}
                        >
                          {formatDateTime(u.created_at)}
                        </Typography>
                        {u.note && (
                          <Typography variant="caption" color="text.secondary" noWrap>
                            {u.note}
                          </Typography>
                        )}
                      </Stack>
                    ))}
                  </Stack>
                </>
              )}
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                {t("nav.epics")}
              </Typography>
              {epics.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  {t("p.misc.projectOverview.noEpics")}
                </Typography>
              ) : (
                <Stack spacing={1.5}>
                  {epics.slice(0, 5).map((e) => {
                    const pct = e.progress_total
                      ? Math.round((e.progress_done / e.progress_total) * 100)
                      : 0;
                    return (
                      <Box key={e.id}>
                        <Stack direction="row" justifyContent="space-between" mb={0.25}>
                          <Typography variant="body2" fontWeight={600}>
                            {e.title}
                          </Typography>
                          <Typography variant="caption">{pct}%</Typography>
                        </Stack>
                        <LinearProgress
                          variant="determinate"
                          value={pct}
                          sx={{ height: 6, borderRadius: 3 }}
                        />
                      </Box>
                    );
                  })}
                </Stack>
              )}
            </Paper>
          </Stack>
        </Grid>

        <Grid item xs={12} md={6}>
          <Stack spacing={3}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                <Users size={14} style={{ verticalAlign: -2 }} />{" "}
                {t("p.misc.projectOverview.members")}
              </Typography>
              {!Array.isArray(members) || members.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  {t("p.misc.projectOverview.noMembers")}
                </Typography>
              ) : (
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {(members as { id: number; user_email: string; role: string }[]).map(
                    (m) => (
                      <Chip
                        key={m.id}
                        size="small"
                        variant="outlined"
                        avatar={
                          <Avatar sx={{ bgcolor: "primary.main" }}>
                            {m.user_email[0]?.toUpperCase()}
                          </Avatar>
                        }
                        label={`${m.user_email} · ${m.role}`}
                      />
                    ),
                  )}
                </Stack>
              )}
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                <ActivityIcon size={14} style={{ verticalAlign: -2 }} />{" "}
                {t("p.misc.projectOverview.recentActivity")}
              </Typography>
              {!activity || activity.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  {t("p.misc.projectOverview.noActivity")}
                </Typography>
              ) : (
                <Stack spacing={1} divider={<Divider />}>
                  {activity.slice(0, 5).map((a, i) => (
                    <Box key={i}>
                      <Typography variant="caption" color="text.secondary">
                        {a.actor ?? t("p.misc.projectOverview.system")} ·{" "}
                        {format(parseISO(a.created_at), "d MMM HH:mm", { locale: es })}
                      </Typography>
                      <Typography variant="body2">{a.summary}</Typography>
                    </Box>
                  ))}
                </Stack>
              )}
            </Paper>
          </Stack>
        </Grid>
      </Grid>

      {/* Desglose de la salud calculada */}
      <Dialog
        open={healthOpen}
        onClose={() => setHealthOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>
          {t("p.misc.projectOverview.healthTitle")}{" "}
          <Box component="span" color={health.color}>
            {health.label}
          </Box>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={1.5}>
            {t("p.misc.projectOverview.healthDesc")}
          </Typography>
          <Stack component="ul" spacing={0.75} sx={{ pl: 2, m: 0 }}>
            {healthFactors.map((f) => (
              <Typography component="li" variant="body2" key={f}>
                {f}
              </Typography>
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary" display="block" mt={2}>
            {t("p.misc.projectOverview.healthCaption")}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHealthOpen(false)}>{t("common.close")}</Button>
        </DialogActions>
      </Dialog>

      {/* Actualizar estado (registro histórico → project-status-updates) */}
      <Dialog
        open={statusDialogOpen}
        onClose={() => setStatusDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.org.health.dialogTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              select
              fullWidth
              label={t("p.org.health.status")}
              value={statusForm.health}
              onChange={(e) =>
                setStatusForm({
                  ...statusForm,
                  health: e.target.value as ProjectHealth,
                })
              }
            >
              {PROJECT_HEALTHS.map((h) => (
                <MenuItem key={h} value={h}>
                  {t(`p.org.health.${h}`)}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              fullWidth
              multiline
              rows={3}
              label={t("p.org.health.note")}
              value={statusForm.note}
              onChange={(e) => setStatusForm({ ...statusForm, note: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStatusDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={createStatus.isPending}
            onClick={() => createStatus.mutate()}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
