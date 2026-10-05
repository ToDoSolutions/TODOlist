import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Tooltip,
  Alert,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  useTheme,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Flag,
  Plus,
  Trash2,
  Play,
  CheckCircle,
  Calendar,
  Target,
  Pencil,
  Eye,
  Folder,
  BarChart3,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { sprintsApi, projectsApi, type Sprint, type SprintMetrics } from "../api/resources";
import { sprintCloseApi, type MoveIncompleteTo } from "../api/featSect";
import { DateField } from "../components/DateField";
import { EmptyState, ErrorState } from "../components/ui/states";
import { formatDate as fmtDate } from "../lib/dates";
import type { Task, Project } from "../types";
import { PRIORITY_LABELS, TaskState } from "../types";
import { TASK_STATE_I18N_KEYS } from "../i18n/batchTaskUi";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import PageHeader from "../components/ui/PageHeader";
import { useProject } from "../auth/ProjectContext";

function formatDate(d: Date) {
  return d.toISOString().split("T")[0];
}

export default function SprintsPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const projectCtx = useProject();
  const { project } = projectCtx;
  const [dialogOpen, setDialogOpen] = useState(false);
  const [closeDialog, setCloseDialog] = useState<Sprint | null>(null);
  // Destino de las tareas incompletas al cerrar: otro sprint | backlog | quedarse
  const [closeChoice, setCloseChoice] = useState<"next" | "backlog" | "keep">("keep");
  const [nextSprintId, setNextSprintId] = useState<number | "">("");
  const [editDialog, setEditDialog] = useState<Sprint | null>(null);
  const [viewTasksSprint, setViewTasksSprint] = useState<Sprint | null>(null);
  const [metricsSprint, setMetricsSprint] = useState<Sprint | null>(null);
  const [editForm, setEditForm] = useState(() => ({
    name: "",
    goal: "",
    start_date: formatDate(new Date()),
    end_date: formatDate(new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)),
  }));
  const [form, setForm] = useState(() => ({
    name: "",
    goal: "",
    start_date: formatDate(new Date()),
    end_date: formatDate(new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)),
  }));

  const { data: sprints = [], isLoading } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData)
    ? projectsData
    : (projectsData as { results?: Project[] } | undefined)?.results || [];
  const projectMap: Map<number, string> = new Map(
    projects.map((p) => [p.id, p.name] as [number, string]),
  );

  const { data: sprintTasks = [], isLoading: isLoadingSprintTasks } = useQuery({
    queryKey: ["sprint-tasks", viewTasksSprint?.id],
    queryFn: () => sprintsApi.getTasks(viewTasksSprint!.id),
    enabled: !!viewTasksSprint,
  });

  // Tareas del sprint que se está cerrando → nº de incompletas (rollover)
  const { data: closingTasks = [], isLoading: isLoadingClosingTasks } = useQuery({
    queryKey: ["sprint-tasks", closeDialog?.id],
    queryFn: () => sprintsApi.getTasks(closeDialog!.id),
    enabled: !!closeDialog,
  });
  const {
    data: sprintMetrics,
    isLoading: isLoadingMetrics,
    refetch: refetchMetrics,
  } = useQuery({
    queryKey: ["sprint-metrics", metricsSprint?.id],
    queryFn: () => sprintsApi.getMetrics(metricsSprint!.id),
    enabled: !!metricsSprint,
  });

  const incompleteCount = closingTasks.filter(
    (task: Task) =>
      task.state !== "completed" &&
      task.state !== "cancelled" &&
      task.state !== "archived",
  ).length;
  // Sprints destino del rollover: no cerrados del mismo proyecto
  const closeTargets = sprints.filter(
    (s) =>
      s.id !== closeDialog?.id &&
      s.state !== "closed" &&
      (!closeDialog?.project || s.project === closeDialog.project),
  );

  const createMut = useMutation({
    mutationFn: () =>
      sprintsApi.create({ ...form, project: project?.id || null } as Partial<Sprint>),
    onSuccess: () => {
      notify.success(t("p.plan.sprints.created"));
      qc.invalidateQueries({ queryKey: ["sprints"] });
      setDialogOpen(false);
      setForm({
        name: "",
        goal: "",
        start_date: formatDate(new Date()),
        end_date: formatDate(new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)),
      });
    },
    onError: () => notify.error(t("p.plan.sprints.createError")),
  });

  const activateMut = useMutation({
    mutationFn: (id: number) => sprintsApi.update(id, { state: "active" }),
    onSuccess: () => {
      notify.success(t("p.plan.sprints.activated"));
      qc.invalidateQueries({ queryKey: ["sprints"] });
    },
  });

  // Cierre con rollover: POST /sprints/{id}/close/ {move_incomplete_to}
  const closeMut = useMutation({
    mutationFn: ({ id, moveTo }: { id: number; moveTo: MoveIncompleteTo }) =>
      sprintCloseApi.close(id, moveTo),
    onSuccess: (data) => {
      const moved = data.moved_incomplete ?? 0;
      notify.success(
        moved > 0
          ? `${data.message} — ${t("p.taskx.sprint.close.moved", { count: moved })}`
          : data.message,
      );
      qc.invalidateQueries({ queryKey: ["sprints"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setCloseDialog(null);
    },
    onError: () => notify.error(t("p.taskx.sprint.close.error")),
  });

  const openCloseDialog = (sprint: Sprint) => {
    setCloseDialog(sprint);
    setCloseChoice("keep");
    setNextSprintId("");
  };

  const handleCloseSprint = () => {
    if (!closeDialog) return;
    const moveTo: MoveIncompleteTo =
      closeChoice === "next"
        ? nextSprintId === ""
          ? null
          : Number(nextSprintId)
        : closeChoice === "backlog"
          ? "backlog"
          : null;
    closeMut.mutate({ id: closeDialog.id, moveTo });
  };

  const deleteMut = useMutation({
    mutationFn: sprintsApi.remove,
    onSuccess: () => {
      notify.info(t("p.plan.sprints.deleted"));
      qc.invalidateQueries({ queryKey: ["sprints"] });
    },
  });

  const editMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Sprint> }) =>
      sprintsApi.update(id, data),
    onSuccess: () => {
      notify.success(t("p.plan.sprints.updated"));
      qc.invalidateQueries({ queryKey: ["sprints"] });
      setEditDialog(null);
    },
    onError: () => notify.error(t("p.plan.sprints.updateError")),
  });

  const openEdit = (sprint: Sprint) => {
    setEditDialog(sprint);
    setEditForm({
      name: sprint.name,
      goal: sprint.goal,
      start_date: sprint.start_date,
      end_date: sprint.end_date,
    });
  };

  const stateColors: Record<string, "default" | "primary" | "success"> = {
    planned: "default",
    active: "primary",
    closed: "success",
  };

  const stateLabels: Record<string, string> = {
    planned: t("p.plan.sprints.state.planned"),
    active: t("p.plan.sprints.state.active"),
    closed: t("p.plan.sprints.state.closed"),
  };

  return (
    <Box maxWidth={900} mx="auto">
      <PageHeader
        title={t("nav.sprints")}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={18} />}
            onClick={() => setDialogOpen(true)}
          >
            {t("p.shell.newSprint")}
          </Button>
        }
      />

      {isLoading && <LinearProgress />}

      {sprints.length === 0 && !isLoading && (
        <EmptyState
          title={t("p.plan.sprints.emptyTitle")}
          description={t("p.plan.sprints.empty")}
          action={
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              onClick={() => setDialogOpen(true)}
            >
              {t("p.shell.newSprint")}
            </Button>
          }
        />
      )}

      <Stack spacing={2}>
        {sprints.map((sprint) => (
          <Card key={sprint.id} variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="flex-start" spacing={2}>
                <Flag size={24} style={{ color: theme.palette.primary.main }} />
                <Box flex={1}>
                  <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                    <Typography variant="h6">{sprint.name}</Typography>
                    {sprint.project && projectMap.get(sprint.project) && (
                      <Chip
                        icon={<Folder size={14} />}
                        label={String(projectMap.get(sprint.project))}
                        size="small"
                        variant="outlined"
                      />
                    )}
                    <Chip
                      label={stateLabels[sprint.state]}
                      color={stateColors[sprint.state]}
                      size="small"
                    />
                    <Chip
                      icon={<Calendar size={14} />}
                      label={`${fmtDate(sprint.start_date)} → ${fmtDate(sprint.end_date)}`}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={t("p.plan.burndown.tasksChip", { count: sprint.task_count })}
                      size="small"
                      variant="outlined"
                    />
                  </Stack>
                  {sprint.goal && (
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <Target size={16} color="#666" />
                      <Typography variant="body2" color="text.secondary">
                        {sprint.goal}
                      </Typography>
                    </Stack>
                  )}
                  <Stack direction="row" spacing={1} mt={1}>
                    {sprint.state === "planned" && (
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Play size={16} />}
                        onClick={() => activateMut.mutate(sprint.id)}
                      >
                        {t("p.plan.sprints.activate")}
                      </Button>
                    )}
                    {sprint.state === "active" && (
                      <Button
                        size="small"
                        variant="outlined"
                        color="success"
                        startIcon={<CheckCircle size={16} />}
                        onClick={() => openCloseDialog(sprint)}
                      >
                        {t("common.close")}
                      </Button>
                    )}
                    <Tooltip title={t("p.plan.epics.viewTasks")}>
                      <IconButton size="small" onClick={() => setViewTasksSprint(sprint)}>
                        <Eye size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t("p.plan.sprints.metrics")}>
                      <IconButton size="small" onClick={() => setMetricsSprint(sprint)}>
                        <BarChart3 size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t("common.edit")}>
                      <IconButton size="small" onClick={() => openEdit(sprint)}>
                        <Pencil size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t("common.delete")}>
                      <IconButton
                        size="small"
                        onClick={async () => {
                          if (
                            await confirm(
                              t("p.plan.sprints.confirmDelete", { name: sprint.name }),
                              { confirmLabel: t("p.plan.sprints.confirmDeleteLabel") },
                            )
                          )
                            deleteMut.mutate(sprint.id);
                        }}
                      >
                        <Trash2 size={16} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>

      {/* Dialog crear sprint */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.shell.newSprint")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
            />
            <TextField
              label={t("p.plan.sprints.fieldGoal")}
              value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })}
              fullWidth
              multiline
              rows={2}
            />
            <DateField
              label={t("p.plan.epics.startDate")}
              value={form.start_date}
              onChange={(v) => setForm({ ...form, start_date: v })}
            />
            <DateField
              label={t("p.plan.epics.endDate")}
              value={form.end_date}
              onChange={(v) => setForm({ ...form, end_date: v })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => createMut.mutate()}
            disabled={!form.name || createMut.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog editar sprint */}
      <Dialog
        open={!!editDialog}
        onClose={() => setEditDialog(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.plan.sprints.editTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              value={editForm.name}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              fullWidth
            />
            <TextField
              label={t("p.plan.sprints.fieldGoal")}
              value={editForm.goal}
              onChange={(e) => setEditForm({ ...editForm, goal: e.target.value })}
              fullWidth
              multiline
              rows={2}
            />
            <DateField
              label={t("p.plan.epics.startDate")}
              value={editForm.start_date}
              onChange={(v) => setEditForm({ ...editForm, start_date: v })}
            />
            <DateField
              label={t("p.plan.epics.endDate")}
              value={editForm.end_date}
              onChange={(v) => setEditForm({ ...editForm, end_date: v })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() =>
              editDialog && editMut.mutate({ id: editDialog.id, data: editForm })
            }
            disabled={!editForm.name || editMut.isPending}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog cerrar sprint: rollover de tareas incompletas
          (move_incomplete_to: sprint_id | "backlog" | null) */}
      <Dialog
        open={!!closeDialog}
        onClose={() => setCloseDialog(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {t("p.taskx.sprint.close.title", { name: closeDialog?.name })}
        </DialogTitle>
        <DialogContent>
          {isLoadingClosingTasks ? (
            <LinearProgress />
          ) : incompleteCount > 0 ? (
            <>
              <Typography variant="body2" mb={2}>
                {t("p.taskx.sprint.close.incomplete", { count: incompleteCount })}
              </Typography>
              <RadioGroup
                value={closeChoice}
                onChange={(e) =>
                  setCloseChoice(e.target.value as "next" | "backlog" | "keep")
                }
              >
                <FormControlLabel
                  value="next"
                  control={<Radio size="small" />}
                  label={t("p.taskx.sprint.close.moveNext")}
                  disabled={closeTargets.length === 0}
                />
                {closeChoice === "next" && (
                  <FormControl size="small" fullWidth sx={{ ml: 4, mb: 1 }}>
                    <InputLabel>{t("p.taskx.sprint.close.target")}</InputLabel>
                    <Select
                      value={nextSprintId}
                      label={t("p.taskx.sprint.close.target")}
                      onChange={(e) => setNextSprintId(Number(e.target.value))}
                    >
                      {closeTargets.map((s) => (
                        <MenuItem key={s.id} value={s.id}>
                          {s.name} ({fmtDate(s.start_date)} → {fmtDate(s.end_date)})
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
                <FormControlLabel
                  value="backlog"
                  control={<Radio size="small" />}
                  label={t("p.taskx.sprint.close.moveBacklog")}
                />
                <FormControlLabel
                  value="keep"
                  control={<Radio size="small" />}
                  label={t("p.taskx.sprint.close.keep")}
                />
              </RadioGroup>
            </>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("p.taskx.sprint.close.noIncomplete")}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloseDialog(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleCloseSprint}
            disabled={
              closeMut.isPending ||
              isLoadingClosingTasks ||
              (incompleteCount > 0 && closeChoice === "next" && nextSprintId === "")
            }
          >
            {t("p.taskx.sprint.close.confirm")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog ver tareas del sprint */}
      <Dialog
        open={!!viewTasksSprint}
        onClose={() => setViewTasksSprint(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {t("p.plan.epics.tasksOf", {
            title: viewTasksSprint?.name,
            count: sprintTasks.length,
          })}
        </DialogTitle>
        <DialogContent>
          <Button
            variant="outlined"
            fullWidth
            sx={{ mb: 2 }}
            onClick={() => {
              if (viewTasksSprint?.project) {
                projectCtx.setProject({
                  id: viewTasksSprint.project,
                  name: String(projectMap.get(viewTasksSprint.project) || ""),
                  color: "#1976d2",
                });
                navigate(`/app/project/${viewTasksSprint.project}`);
              } else {
                navigate("/app");
              }
            }}
          >
            {t("p.plan.epics.viewInTasks")}
          </Button>
          {isLoadingSprintTasks ? (
            <Stack alignItems="center" sx={{ py: 3 }}>
              <CircularProgress size={32} />
            </Stack>
          ) : sprintTasks.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t("p.plan.sprints.noTasks")}
            </Typography>
          ) : (
            <List dense>
              {sprintTasks.map((task: Task) => (
                <ListItem
                  key={task.id}
                  sx={{ px: 0 }}
                  secondaryAction={
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip
                        label={PRIORITY_LABELS[task.priority]}
                        size="small"
                        variant="outlined"
                      />
                    </Stack>
                  }
                >
                  <ListItemText
                    primary={task.title}
                    secondary={
                      <Chip
                        label={t(TASK_STATE_I18N_KEYS[task.state as TaskState])}
                        size="small"
                        sx={{ mt: 0.5 }}
                      />
                    }
                  />
                </ListItem>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewTasksSprint(null)}>{t("common.close")}</Button>
        </DialogActions>
      </Dialog>

      {/* Dialog métricas del sprint (GET /sprints/{id}/metrics/):
          conteos por estado, story points y scope creep */}
      <Dialog
        open={!!metricsSprint}
        onClose={() => setMetricsSprint(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {t("p.plan.sprints.metricsTitle", { name: metricsSprint?.name })}
        </DialogTitle>
        <DialogContent>
          {isLoadingMetrics ? (
            <Stack alignItems="center" sx={{ py: 3 }}>
              <CircularProgress size={32} />
            </Stack>
          ) : !sprintMetrics ? (
            <ErrorState
              title={t("p.plan.sprints.metricsError")}
              onRetry={() => void refetchMetrics()}
            />
          ) : (
            <MetricsBody m={sprintMetrics} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMetricsSprint(null)}>{t("common.close")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function MetricsBody({ m }: { m: SprintMetrics }) {
  const { t } = useTranslation();
  return (
    <Stack spacing={2} sx={{ mt: 0.5 }}>
      <Box>
        <Stack direction="row" justifyContent="space-between" mb={0.5}>
          <Typography variant="body2" color="text.secondary">
            {t("p.plan.sprints.metricsProgress")}
          </Typography>
          <Typography variant="body2" fontWeight={700}>
            {m.done}/{m.total_tasks} · {m.progress_pct}%
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={m.progress_pct}
          sx={{ height: 8, borderRadius: 1 }}
        />
      </Box>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Chip
          size="small"
          color="success"
          variant="outlined"
          label={t("p.plan.sprints.metricsDone", { count: m.done })}
        />
        <Chip
          size="small"
          color="primary"
          variant="outlined"
          label={t("p.plan.sprints.metricsInProgress", { count: m.in_progress })}
        />
        <Chip
          size="small"
          color="error"
          variant="outlined"
          label={t("p.plan.sprints.metricsBlocked", { count: m.blocked })}
        />
        <Chip
          size="small"
          variant="outlined"
          label={t("p.plan.sprints.metricsPending", { count: m.pending })}
        />
      </Stack>
      {m.story_points_total > 0 && (
        <Typography variant="body2" color="text.secondary">
          {t("p.plan.sprints.metricsPoints", {
            done: m.story_points_done,
            total: m.story_points_total,
          })}
        </Typography>
      )}
      {m.added_after_start > 0 && (
        <Alert severity="warning" icon={false} sx={{ py: 0.5 }}>
          {t("p.plan.sprints.metricsScopeCreep", {
            count: m.added_after_start,
            pct: m.scope_creep_pct,
          })}
        </Alert>
      )}
    </Stack>
  );
}
