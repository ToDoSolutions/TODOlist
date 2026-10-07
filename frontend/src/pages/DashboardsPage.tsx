import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CardGridSkeleton } from "../components/ui/skeletons";
import {
  Box,
  Typography,
  Paper,
  Stack,
  Chip,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  GridLegacy as Grid,
  Divider,
  Tooltip,
  List,
  ListItemButton,
  ListItemText,
  FormControlLabel,
  Checkbox,
} from "@mui/material";
import {
  LayoutDashboard,
  Plus,
  Share2,
  Pencil,
  Trash2,
  Star,
  X,
  CheckSquare,
  AlertCircle,
  Ban,
  Users,
  TrendingUp,
  GitPullRequest,
  Activity,
  Gauge,
  Rocket,
  ScrollText,
} from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/states";
import {
  dashboardsApi,
  type Dashboard,
  type DashboardWidget,
  type ResolvedWidget,
} from "../api/resources";
import {
  STATE_LABELS,
  PRIORITY_LABELS,
  type TaskPriority,
  type TaskState,
} from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import { formatRelative, formatDate } from "../lib/dates";

const WIDGET_ICONS: Record<string, React.ReactNode> = {
  kpis: <Gauge size={16} />,
  my_tasks: <CheckSquare size={16} />,
  overdue: <AlertCircle size={16} />,
  blocked: <Ban size={16} />,
  workload: <Users size={16} />,
  velocity: <TrendingUp size={16} />,
  prs_open: <GitPullRequest size={16} />,
  upcoming_deadlines: <CheckSquare size={16} />,
  recent_activity: <Activity size={16} />,
  dora: <Rocket size={16} />,
  audit_dashboard: <ScrollText size={16} />,
};

interface TaskBrief {
  id: number;
  title: string;
  state: string;
  priority: number;
  due_date: string | null;
}

/** Dashboards personalizables: composición de widgets + compartición. */
export default function DashboardsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [editWidgetsFor, setEditWidgetsFor] = useState<Dashboard | null>(null);
  const [shareFor, setShareFor] = useState<Dashboard | null>(null);
  const [renameFor, setRenameFor] = useState<Dashboard | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const { data: dashboards, isLoading } = useQuery({
    queryKey: ["dashboards"],
    queryFn: dashboardsApi.list,
  });
  const list = dashboards ?? [];
  const selected =
    list.find((d) => d.id === selectedId) ?? list.find((d) => d.is_default) ?? list[0];

  const { data: resolved, isLoading: loadingData } = useQuery({
    queryKey: ["dashboards", selected?.id, "data"],
    queryFn: () => dashboardsApi.data(selected!.id),
    enabled: !!selected,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["dashboards"] });

  const createMut = useMutation({
    mutationFn: (name: string) =>
      dashboardsApi.create({ name, widgets: [{ id: "w1", type: "kpis" }] }),
    onSuccess: (d) => {
      notify.success(t("p.collab.dashboards.created"));
      invalidate();
      setCreateOpen(false);
      setNewName("");
      setSelectedId(d.id);
    },
    onError: () => notify.error(t("p.collab.dashboards.createError")),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, ...p }: { id: number } & Partial<Dashboard>) =>
      dashboardsApi.update(id, p),
    onSuccess: () => {
      invalidate();
      setRenameFor(null);
    },
    onError: () => notify.error(t("p.collab.dashboards.saveError")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => dashboardsApi.remove(id),
    onSuccess: () => {
      notify.success(t("p.collab.dashboards.deleted"));
      invalidate();
      setSelectedId(null);
    },
  });

  return (
    <Box>
      <PageHeader
        title={t("p.collab.dashboards.title")}
        description={t("p.collab.dashboards.desc")}
        breadcrumbs={[
          { label: t("p.collab.dashboards.breadcrumbTeam") },
          { label: t("p.collab.dashboards.title") },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={15} />}
            onClick={() => setCreateOpen(true)}
          >
            {t("p.collab.dashboards.new")}
          </Button>
        }
      />

      {isLoading ? (
        <CardGridSkeleton />
      ) : list.length === 0 ? (
        <EmptyState
          title={t("p.collab.dashboards.emptyTitle")}
          description={t("p.collab.dashboards.emptyDesc")}
          action={
            <Button
              variant="contained"
              startIcon={<Plus size={15} />}
              onClick={() => setCreateOpen(true)}
            >
              {t("p.collab.dashboards.new")}
            </Button>
          }
        />
      ) : (
        <Grid container spacing={2}>
          {/* Selector de dashboards */}
          <Grid item xs={12} md={3}>
            <Paper variant="outlined">
              <List dense>
                {list.map((d) => (
                  <ListItemButton
                    key={d.id}
                    selected={selected?.id === d.id}
                    onClick={() => setSelectedId(d.id)}
                  >
                    <ListItemText
                      primary={
                        <Stack direction="row" spacing={0.5} alignItems="center">
                          <Typography
                            variant="body2"
                            fontWeight={600}
                            noWrap
                            sx={{ flex: 1 }}
                          >
                            {d.name}
                          </Typography>
                          {d.is_default && (
                            <Star size={12} fill="#f9a825" color="#f9a825" />
                          )}
                          {!d.is_owner && (
                            <Chip
                              size="small"
                              variant="outlined"
                              label={t("p.collab.dashboards.sharedChip")}
                              sx={{ height: 18, fontSize: 10 }}
                            />
                          )}
                        </Stack>
                      }
                      secondary={t("p.collab.dashboards.widgetCount", {
                        count: d.widgets.length,
                      })}
                    />
                  </ListItemButton>
                ))}
              </List>
            </Paper>
          </Grid>

          {/* Dashboard seleccionado */}
          <Grid item xs={12} md={9}>
            {selected && (
              <>
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  mb={2}
                  flexWrap="wrap"
                  useFlexGap
                >
                  <Typography variant="h6" fontWeight={700} sx={{ flex: 1 }}>
                    {selected.name}
                  </Typography>
                  {selected.is_owner ? (
                    <>
                      <Tooltip title={t("p.collab.dashboards.rename")}>
                        <IconButton
                          size="small"
                          aria-label={t("p.collab.dashboards.rename")}
                          onClick={() => {
                            setRenameFor(selected);
                            setRenameValue(selected.name);
                          }}
                        >
                          <Pencil size={15} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip
                        title={
                          selected.is_default
                            ? t("p.collab.dashboards.isDefault")
                            : t("p.collab.dashboards.setDefault")
                        }
                      >
                        <IconButton
                          size="small"
                          aria-label={t("p.collab.dashboards.defaultAria")}
                          onClick={() =>
                            updateMut.mutate({
                              id: selected.id,
                              is_default: !selected.is_default,
                            })
                          }
                        >
                          <Star
                            size={15}
                            fill={selected.is_default ? "#f9a825" : "none"}
                          />
                        </IconButton>
                      </Tooltip>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Plus size={14} />}
                        onClick={() => setEditWidgetsFor(selected)}
                      >
                        {t("p.collab.dashboards.widgets")}
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Share2 size={14} />}
                        onClick={() => setShareFor(selected)}
                      >
                        {t("p.collab.dashboards.share")}
                        {selected.shared_with.length > 0
                          ? ` (${selected.shared_with.length})`
                          : ""}
                      </Button>
                      <Tooltip title={t("p.collab.dashboards.deleteDashboard")}>
                        <IconButton
                          size="small"
                          color="error"
                          aria-label={t("common.delete")}
                          onClick={async () => {
                            if (
                              await confirm(
                                t("p.collab.dashboards.confirmDelete", {
                                  name: selected.name,
                                }),
                                { confirmLabel: t("common.delete") },
                              )
                            )
                              deleteMut.mutate(selected.id);
                          }}
                        >
                          <Trash2 size={15} />
                        </IconButton>
                      </Tooltip>
                    </>
                  ) : (
                    <Chip
                      size="small"
                      icon={<Share2 size={12} />}
                      label={t("p.collab.dashboards.sharedWithYou")}
                      variant="outlined"
                    />
                  )}
                </Stack>

                {loadingData ? (
                  <CardGridSkeleton cards={4} />
                ) : !resolved || resolved.widgets.length === 0 ? (
                  <EmptyState
                    title={t("p.collab.dashboards.emptyDashTitle")}
                    description={
                      selected.is_owner
                        ? t("p.collab.dashboards.emptyDashOwner")
                        : t("p.collab.dashboards.emptyDashViewer")
                    }
                  />
                ) : (
                  <Grid container spacing={2}>
                    {resolved.widgets.map((w, i) => (
                      <Grid
                        item
                        xs={12}
                        sm={w.size === "half" ? 6 : 12}
                        md={w.size === "half" ? 6 : 12}
                        key={w.id ?? i}
                      >
                        <WidgetCard
                          widget={w}
                          onOpenTask={(id) => navigate(`/app/tasks/${id}`)}
                        />
                      </Grid>
                    ))}
                  </Grid>
                )}
              </>
            )}
          </Grid>
        </Grid>
      )}

      {/* Crear */}
      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.collab.dashboards.new")}</DialogTitle>
        <DialogContent>
          <TextField
            label={t("common.name")}
            fullWidth
            autoFocus
            sx={{ mt: 1 }}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && newName.trim()) createMut.mutate(newName.trim());
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!newName.trim() || createMut.isPending}
            onClick={() => createMut.mutate(newName.trim())}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Renombrar */}
      <Dialog
        open={!!renameFor}
        onClose={() => setRenameFor(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.collab.dashboards.renameTitle")}</DialogTitle>
        <DialogContent>
          <TextField
            label={t("common.name")}
            fullWidth
            autoFocus
            sx={{ mt: 1 }}
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRenameFor(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!renameValue.trim()}
            onClick={() =>
              renameFor &&
              updateMut.mutate({ id: renameFor.id, name: renameValue.trim() })
            }
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Editor de widgets */}
      {editWidgetsFor && (
        <WidgetsEditor
          dashboard={editWidgetsFor}
          onClose={() => setEditWidgetsFor(null)}
          onSave={(widgets) => {
            updateMut.mutate({ id: editWidgetsFor.id, widgets });
            setEditWidgetsFor(null);
          }}
        />
      )}

      {/* Compartir */}
      {shareFor && (
        <ShareDialog
          dashboard={shareFor}
          onClose={() => setShareFor(null)}
          onChanged={invalidate}
        />
      )}
    </Box>
  );
}

/* ---------- Editor de widgets ---------- */

function WidgetsEditor({
  dashboard,
  onClose,
  onSave,
}: {
  dashboard: Dashboard;
  onClose: () => void;
  onSave: (widgets: DashboardWidget[]) => void;
}) {
  const { t } = useTranslation();
  const widgetLabel = (type: string) =>
    t(`p.collab.dashboards.widget.${type}`, { defaultValue: type });
  const [widgets, setWidgets] = useState<DashboardWidget[]>(dashboard.widgets);
  const [newType, setNewType] = useState("");

  const { data: types } = useQuery({
    queryKey: ["dashboards", "widget-types"],
    queryFn: dashboardsApi.widgetTypes,
  });
  const available = (types ?? []).filter((t) => !widgets.some((w) => w.type === t));

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {t("p.collab.dashboards.editorTitle", { name: dashboard.name })}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={1} mt={1}>
          {widgets.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              {t("p.collab.dashboards.noWidgets")}
            </Typography>
          )}
          {widgets.map((w, i) => (
            <Paper key={w.id ?? i} variant="outlined" sx={{ p: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                {WIDGET_ICONS[w.type] ?? <LayoutDashboard size={16} />}
                <Typography variant="body2" sx={{ flex: 1 }}>
                  {w.title || widgetLabel(w.type)}
                </Typography>
                <FormControlLabel
                  control={
                    <Checkbox
                      size="small"
                      checked={w.size === "half"}
                      onChange={(e) =>
                        setWidgets((ws) =>
                          ws.map((x, j) =>
                            j === i
                              ? { ...x, size: e.target.checked ? "half" : undefined }
                              : x,
                          ),
                        )
                      }
                    />
                  }
                  label={
                    <Typography variant="caption">
                      {t("p.collab.dashboards.halfWidth")}
                    </Typography>
                  }
                />
                <IconButton
                  size="small"
                  color="error"
                  aria-label={t("p.collab.dashboards.removeWidget")}
                  onClick={() => setWidgets((ws) => ws.filter((_, j) => j !== i))}
                >
                  <X size={14} />
                </IconButton>
              </Stack>
            </Paper>
          ))}
          <Divider />
          <Stack direction="row" spacing={1}>
            <TextField
              select
              size="small"
              label={t("p.collab.dashboards.addWidget")}
              fullWidth
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            >
              {available.map((wt) => (
                <MenuItem key={wt} value={wt}>
                  {widgetLabel(wt)}
                </MenuItem>
              ))}
            </TextField>
            <Button
              variant="outlined"
              disabled={!newType}
              onClick={() => {
                setWidgets((ws) => [...ws, { id: `w${Date.now()}`, type: newType }]);
                setNewType("");
              }}
            >
              {t("p.collab.dashboards.add")}
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button variant="contained" onClick={() => onSave(widgets)}>
          {t("common.save")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ---------- Diálogo de compartición ---------- */

function ShareDialog({
  dashboard,
  onClose,
  onChanged,
}: {
  dashboard: Dashboard;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");

  const shareMut = useMutation({
    mutationFn: () => dashboardsApi.share(dashboard.id, email.trim()),
    onSuccess: () => {
      notify.success(t("p.collab.dashboards.shared"));
      setEmail("");
      onChanged();
    },
    onError: (e: { response?: { data?: { error?: string } } }) =>
      notify.error(e.response?.data?.error ?? t("p.collab.dashboards.shareError")),
  });

  const unshareMut = useMutation({
    mutationFn: (mail: string) => dashboardsApi.unshare(dashboard.id, mail),
    onSuccess: () => {
      notify.success(t("p.collab.dashboards.unshared"));
      onChanged();
    },
    onError: () => notify.error(t("p.collab.dashboards.unshareError")),
  });

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {t("p.collab.dashboards.shareTitle", { name: dashboard.name })}
      </DialogTitle>
      <DialogContent>
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          {t("p.collab.dashboards.shareInfo")}
        </Alert>
        <Stack direction="row" spacing={1}>
          <TextField
            label={t("p.collab.dashboards.emailLabel")}
            size="small"
            fullWidth
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && email.trim()) shareMut.mutate();
            }}
          />
          <Button
            variant="contained"
            disabled={!email.trim() || shareMut.isPending}
            onClick={() => shareMut.mutate()}
          >
            {t("p.collab.dashboards.share")}
          </Button>
        </Stack>
        {dashboard.shared_with.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" mb={1}>
              {t("p.collab.dashboards.sharedWith")}
            </Typography>
            <Stack spacing={0.5}>
              {dashboard.shared_with.map((u) => (
                <Stack key={u.id} direction="row" alignItems="center" spacing={1}>
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {u.email}
                  </Typography>
                  <IconButton
                    size="small"
                    color="error"
                    aria-label={t("p.collab.dashboards.removeAccess", {
                      email: u.email,
                    })}
                    onClick={() => unshareMut.mutate(u.email)}
                  >
                    <X size={14} />
                  </IconButton>
                </Stack>
              ))}
            </Stack>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("common.close")}</Button>
      </DialogActions>
    </Dialog>
  );
}

/* ---------- Render de widgets ---------- */

function WidgetCard({
  widget,
  onOpenTask,
}: {
  widget: ResolvedWidget;
  onOpenTask: (id: number) => void;
}) {
  const { t } = useTranslation();
  const title =
    widget.title ||
    t(`p.collab.dashboards.widget.${widget.type}`, { defaultValue: widget.type });
  return (
    <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
        {WIDGET_ICONS[widget.type] ?? <LayoutDashboard size={16} />}
        <Typography variant="subtitle2" fontWeight={700}>
          {title}
        </Typography>
      </Stack>
      <WidgetBody widget={widget} onOpenTask={onOpenTask} />
    </Paper>
  );
}

function TaskRows({
  tasks,
  onOpenTask,
  emptyLabel,
}: {
  tasks: TaskBrief[];
  onOpenTask: (id: number) => void;
  emptyLabel?: string;
}) {
  const { t } = useTranslation();
  if (tasks.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        {emptyLabel ?? t("p.collab.dashboards.nothingHere")}
      </Typography>
    );
  }
  return (
    <Stack spacing={0.5}>
      {tasks.map((t) => (
        <Paper
          key={t.id}
          variant="outlined"
          sx={{ p: 0.75, cursor: "pointer" }}
          onClick={() => onOpenTask(t.id)}
        >
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body2" sx={{ flex: 1 }} noWrap>
              {t.title}
            </Typography>
            <Chip
              size="small"
              variant="outlined"
              label={STATE_LABELS[t.state as TaskState] ?? t.state}
              sx={{ height: 18, fontSize: 10 }}
            />
            <Chip
              size="small"
              variant="outlined"
              label={PRIORITY_LABELS[t.priority as TaskPriority] ?? `P${t.priority}`}
              sx={{ height: 18, fontSize: 10 }}
            />
            {t.due_date && (
              <Typography variant="caption" color="text.secondary">
                {formatDate(t.due_date)}
              </Typography>
            )}
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
}

function WidgetBody({
  widget,
  onOpenTask,
}: {
  widget: ResolvedWidget;
  onOpenTask: (id: number) => void;
}) {
  const { t } = useTranslation();
  const d = widget.data;
  if (d.error) {
    return (
      <Alert severity="warning" variant="outlined" sx={{ py: 0 }}>
        {d.error}
      </Alert>
    );
  }
  switch (widget.type) {
    case "kpis": {
      const items: [string, number, string][] = [
        [t("p.collab.dashboards.kpi.open"), Number(d.open ?? 0), "#1976d2"],
        [t("p.collab.dashboards.kpi.overdue"), Number(d.overdue ?? 0), "#d32f2f"],
        [t("p.collab.dashboards.kpi.inProgress"), Number(d.in_progress ?? 0), "#ed6c02"],
        [
          t("p.collab.dashboards.kpi.completed30d"),
          Number(d.completed_30d ?? 0),
          "#2e7d32",
        ],
      ];
      return (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {items.map(([label, v, color]) => (
            <Chip
              key={label}
              label={`${v} ${label}`}
              sx={{ borderColor: color, color, fontWeight: 600 }}
              variant="outlined"
            />
          ))}
        </Stack>
      );
    }
    case "my_tasks":
    case "overdue":
    case "upcoming_deadlines":
      return (
        <TaskRows
          tasks={(d.tasks as TaskBrief[]) ?? []}
          onOpenTask={onOpenTask}
          emptyLabel={t(`p.collab.dashboards.empty.${widget.type}`)}
        />
      );
    case "blocked": {
      const blocked = (d.blocked as { task: TaskBrief; blocked_by: TaskBrief }[]) ?? [];
      if (blocked.length === 0)
        return (
          <Typography variant="body2" color="text.secondary">
            {t("p.collab.dashboards.noBlocks")}
          </Typography>
        );
      return (
        <Stack spacing={0.5}>
          {blocked.map((b, i) => (
            <Paper
              key={i}
              variant="outlined"
              sx={{ p: 0.75, cursor: "pointer" }}
              onClick={() => onOpenTask(b.task.id)}
            >
              <Typography variant="body2">
                <strong>{b.task.title}</strong>
                <Box component="span" color="error.main">
                  {" "}
                  {t("p.collab.dashboards.blockedBy", {
                    title: b.blocked_by.title,
                  })}
                </Box>
              </Typography>
            </Paper>
          ))}
        </Stack>
      );
    }
    case "workload": {
      const members =
        (d.members as {
          user_id: number;
          email: string;
          open_tasks: number;
          estimate_hours: number;
          utilization: number;
          over_allocated: boolean;
        }[]) ?? [];
      if (members.length === 0)
        return (
          <Typography variant="body2" color="text.secondary">
            {t("p.collab.dashboards.noWorkload")}
          </Typography>
        );
      return (
        <Stack spacing={0.75}>
          {members.map((m) => (
            <Stack key={m.user_id} direction="row" spacing={1} alignItems="center">
              <Typography variant="body2" sx={{ flex: 1 }} noWrap>
                {m.email}
              </Typography>
              <Chip
                size="small"
                variant="outlined"
                label={t("p.plan.burndown.tasksChip", { count: m.open_tasks })}
                sx={{ height: 18, fontSize: 10 }}
              />
              <Chip
                size="small"
                label={`${m.utilization}%`}
                color={m.over_allocated ? "error" : "default"}
                sx={{ height: 18, fontSize: 10 }}
              />
            </Stack>
          ))}
        </Stack>
      );
    }
    case "velocity": {
      const sprints =
        (d.sprints as {
          sprint: string;
          state: string;
          completed_points: number;
          completed_tasks: number;
        }[]) ?? [];
      if (sprints.length === 0)
        return (
          <Typography variant="body2" color="text.secondary">
            {t("p.collab.dashboards.noSprints")}
          </Typography>
        );
      const max = Math.max(...sprints.map((s) => s.completed_points), 1);
      const estActual =
        (d.estimated_vs_actual as {
          sprint: string;
          estimated_hours: number;
          actual_hours: number;
        }[]) ?? [];
      const bySprint = new Map(estActual.map((e) => [e.sprint, e]));
      const totEst = estActual.reduce((a, e) => a + (e.estimated_hours || 0), 0);
      const totAct = estActual.reduce((a, e) => a + (e.actual_hours || 0), 0);
      return (
        <Stack spacing={0.5}>
          <Stack direction="row" spacing={1} alignItems="flex-end" sx={{ height: 90 }}>
            {sprints.map((s) => {
              const ea = bySprint.get(s.sprint);
              return (
                <Tooltip
                  key={s.sprint}
                  title={t("p.collab.dashboards.velocityTip", {
                    sprint: s.sprint,
                    points: s.completed_points,
                    tasks: s.completed_tasks,
                    est: ea?.estimated_hours ?? 0,
                    act: ea?.actual_hours ?? 0,
                  })}
                >
                  <Box sx={{ textAlign: "center", flex: 1, minWidth: 36 }}>
                    <Box
                      sx={{
                        height: `${(s.completed_points / max) * 70}px`,
                        minHeight: 4,
                        bgcolor: "primary.main",
                        borderRadius: "4px 4px 0 0",
                        mb: 0.5,
                      }}
                    />
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      noWrap
                      display="block"
                    >
                      {s.sprint.split(" - ")[0]}
                    </Typography>
                  </Box>
                </Tooltip>
              );
            })}
          </Stack>
          {estActual.length > 0 && (
            <Typography variant="caption" color="text.secondary">
              {t("p.collab.dashboards.estVsActual", {
                est: Math.round(totEst * 10) / 10,
                act: Math.round(totAct * 10) / 10,
              })}
            </Typography>
          )}
        </Stack>
      );
    }
    case "prs_open": {
      const prs =
        (d.prs as {
          repo: string;
          number: number;
          title: string;
          url: string;
          ci_status: string;
        }[]) ?? [];
      if (prs.length === 0)
        return (
          <Typography variant="body2" color="text.secondary">
            {t("p.collab.dashboards.noPrs")}
          </Typography>
        );
      return (
        <Stack spacing={0.5}>
          {prs.map((p) => (
            <Paper key={`${p.repo}#${p.number}`} variant="outlined" sx={{ p: 0.75 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <GitPullRequest size={14} />
                <Typography variant="body2" sx={{ flex: 1 }} noWrap>
                  {p.repo}#{p.number} — {p.title}
                </Typography>
                <Chip
                  size="small"
                  variant="outlined"
                  label={p.ci_status || "—"}
                  sx={{ height: 18, fontSize: 10 }}
                />
              </Stack>
            </Paper>
          ))}
        </Stack>
      );
    }
    case "recent_activity": {
      const activity =
        (d.activity as { action: string; resource: string; at: string }[]) ?? [];
      if (activity.length === 0)
        return (
          <Typography variant="body2" color="text.secondary">
            {t("p.collab.dashboards.noActivity")}
          </Typography>
        );
      return (
        <Stack spacing={0.5}>
          {activity.map((a, i) => (
            <Typography key={i} variant="body2" color="text.secondary">
              {t(`p.admin.audit.actions.${a.action}`, { defaultValue: a.action })}{" "}
              · {t(`p.admin.audit.res.${a.resource}`, { defaultValue: a.resource })}{" "}
              · {formatRelative(a.at)}
            </Typography>
          ))}
        </Stack>
      );
    }
    case "dora": {
      const fmt = (v: unknown, suffix = "") =>
        v === null || v === undefined ? "—" : `${v}${suffix}`;
      const items: [string, string][] = [
        [t("p.admin.widgets.dora.deployFreq"), fmt(d.deployment_frequency_per_week)],
        [t("p.admin.widgets.dora.leadTime"), fmt(d.lead_time_for_changes_hours, "h")],
        [t("p.admin.widgets.dora.cfr"), fmt(d.change_failure_rate_pct, "%")],
        [t("p.admin.widgets.dora.mttr"), fmt(d.mttr_hours, "h")],
      ];
      const samples =
        (d.samples as {
          releases?: number;
          merged_prs?: number;
          check_runs?: number;
        }) ?? {};
      return (
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {items.map(([label, v]) => (
              <Chip
                key={label}
                label={`${label}: ${v}`}
                variant="outlined"
                sx={{ fontWeight: 600 }}
              />
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {t("p.admin.widgets.dora.period", {
              days: Number(d.period_days ?? 30),
            })}{" "}
            ·{" "}
            {t("p.admin.widgets.dora.samples", {
              releases: samples.releases ?? 0,
              prs: samples.merged_prs ?? 0,
              checks: samples.check_runs ?? 0,
            })}
          </Typography>
        </Stack>
      );
    }
    case "audit_dashboard": {
      const total = Number(d.total_actions ?? 0);
      const last30 = Number(d.last_30_days ?? 0);
      const byAction = (d.by_action as Record<string, number>) ?? {};
      const byResource = (d.by_resource as Record<string, number>) ?? {};
      const top = (obj: Record<string, number>) =>
        Object.entries(obj)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 8);
      const actions = top(byAction);
      const resources = top(byResource);
      if (total === 0)
        return (
          <Typography variant="body2" color="text.secondary">
            {t("p.admin.widgets.audit.empty")}
          </Typography>
        );
      return (
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              label={t("p.admin.widgets.audit.total", { count: total })}
              variant="outlined"
              sx={{ fontWeight: 600 }}
            />
            <Chip
              size="small"
              label={t("p.admin.widgets.audit.last30", { count: last30 })}
              variant="outlined"
            />
          </Stack>
          {actions.length > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t("p.admin.widgets.audit.byAction")}
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {actions.map(([k, v]) => (
                  <Chip
                    key={k}
                    size="small"
                    variant="outlined"
                    label={`${k}: ${v}`}
                    sx={{ height: 18, fontSize: 10 }}
                  />
                ))}
              </Stack>
            </Box>
          )}
          {resources.length > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t("p.admin.widgets.audit.byResource")}
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {resources.map(([k, v]) => (
                  <Chip
                    key={k}
                    size="small"
                    variant="outlined"
                    label={`${k}: ${v}`}
                    sx={{ height: 18, fontSize: 10 }}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </Stack>
      );
    }
    default:
      return (
        <Typography variant="body2" color="text.secondary">
          {t("p.collab.dashboards.unsupportedWidget", { type: widget.type })}
        </Typography>
      );
  }
}