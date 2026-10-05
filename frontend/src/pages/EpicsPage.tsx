import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
  LinearProgress,
  IconButton,
  Tooltip,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, Trash2, Pencil, Eye, Folder } from "lucide-react";
import { useTranslation } from "react-i18next";
import { epicsApi, projectsApi, type Epic } from "../api/resources";
import { DateField } from "../components/DateField";
import { EmptyState } from "../components/ui/states";
import PageHeader from "../components/ui/PageHeader";
import type { Task, Project } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import { useProject } from "../auth/ProjectContext";

const EPIC_STATES: Epic["state"][] = ["planned", "in_progress", "completed", "cancelled"];

interface EpicForm {
  title: string;
  description: string;
  color: string;
  state: Epic["state"];
  start_date: string;
  end_date: string;
  project_id: string;
}

const emptyForm: EpicForm = {
  title: "",
  description: "",
  color: "#9c27b0",
  state: "planned",
  start_date: "",
  end_date: "",
  project_id: "",
};

export default function EpicsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const projectCtx = useProject();
  const { project: ctxProject } = projectCtx;
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [viewTasksEpic, setViewTasksEpic] = useState<Epic | null>(null);
  const [form, setForm] = useState<EpicForm>(emptyForm);

  const { data: epics = [], isLoading } = useQuery({
    queryKey: ["epics"],
    queryFn: epicsApi.list,
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData)
    ? projectsData
    : (projectsData as { results?: Project[] } | undefined)?.results || [];

  const projectMap = new Map<number, string>(
    projects.map((p) => [p.id, p.name as string]),
  );

  const { data: epicTasks = [], isLoading: isLoadingEpicTasks } = useQuery({
    queryKey: ["epic-tasks", viewTasksEpic?.id],
    queryFn: () => epicsApi.getTasks(viewTasksEpic!.id),
    enabled: !!viewTasksEpic,
  });

  const createMut = useMutation({
    mutationFn: () =>
      epicsApi.create({
        ...form,
        project: form.project_id ? Number(form.project_id) : null,
      } as Partial<Epic>),
    onSuccess: () => {
      notify.success(t("p.plan.epics.created"));
      qc.invalidateQueries({ queryKey: ["epics"] });
      setDialogOpen(false);
      setForm(emptyForm);
    },
    onError: () => notify.error(t("p.plan.epics.createError")),
  });

  const updateMut = useMutation({
    mutationFn: () =>
      epicsApi.update(editingId!, {
        ...form,
        project: form.project_id ? Number(form.project_id) : null,
      } as Partial<Epic>),
    onSuccess: () => {
      notify.success(t("p.plan.epics.updated"));
      qc.invalidateQueries({ queryKey: ["epics"] });
      setEditOpen(false);
      setEditingId(null);
      setForm(emptyForm);
    },
    onError: () => notify.error(t("p.plan.epics.updateError")),
  });

  const deleteMut = useMutation({
    mutationFn: epicsApi.remove,
    onSuccess: () => {
      notify.info(t("p.plan.epics.deleted"));
      qc.invalidateQueries({ queryKey: ["epics"] });
    },
    onError: () => notify.error(t("p.plan.epics.deleteError")),
  });

  const stateLabels: Record<string, string> = {
    planned: t("p.plan.epics.statePlanned"),
    in_progress: t("task.state.in_progress"),
    completed: t("task.state.completed"),
    cancelled: t("task.state.cancelled"),
  };
  const taskStateLabel = (s: string) =>
    t(`task.state.${s === "review" ? "in_review" : s}`, { defaultValue: s });
  const taskPriorityLabel = (p: number) =>
    t(`p.work.priority.p${p}`, { defaultValue: `P${p}` });

  const stateColors: Record<string, "default" | "primary" | "success" | "error"> = {
    planned: "default",
    in_progress: "primary",
    completed: "success",
    cancelled: "error",
  };

  const openEdit = (epic: Epic) => {
    setEditingId(epic.id);
    setForm({
      title: epic.title,
      description: epic.description,
      color: epic.color,
      state: epic.state,
      start_date: epic.start_date ?? "",
      end_date: epic.end_date ?? "",
      project_id: epic.project != null ? String(epic.project) : "",
    });
    setEditOpen(true);
  };

  return (
    <Box maxWidth={900} mx="auto">
      <PageHeader
        title={t("p.plan.epics.title")}
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={18} />}
            onClick={() => {
              setForm({
                ...emptyForm,
                project_id: ctxProject ? String(ctxProject.id) : "",
              });
              setDialogOpen(true);
            }}
          >
            {t("p.plan.epics.new")}
          </Button>
        }
      />

      {isLoading && <LinearProgress />}

      {epics.length === 0 && !isLoading && (
        <EmptyState
          title={t("p.plan.epics.emptyTitle")}
          description={t("p.plan.epics.empty")}
          action={
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              onClick={() => {
                setForm({
                  ...emptyForm,
                  project_id: ctxProject ? String(ctxProject.id) : "",
                });
                setDialogOpen(true);
              }}
            >
              {t("p.plan.epics.new")}
            </Button>
          }
        />
      )}

      <Stack spacing={2}>
        {epics.map((epic) => {
          const pct =
            epic.progress_total > 0
              ? Math.round((epic.progress_done / epic.progress_total) * 100)
              : 0;
          return (
            <Card key={epic.id} variant="outlined">
              <CardContent>
                <Stack direction="row" alignItems="flex-start" spacing={2}>
                  <Layers size={24} color={epic.color} />
                  <Box flex={1}>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <Typography variant="h6">{epic.title}</Typography>
                      <Chip
                        label={stateLabels[epic.state]}
                        color={stateColors[epic.state]}
                        size="small"
                      />
                      {epic.project != null && projectMap.has(epic.project) && (
                        <Chip
                          icon={<Folder size={14} />}
                          label={projectMap.get(epic.project)}
                          size="small"
                          variant="outlined"
                          sx={{
                            color: epic.color || undefined,
                            borderColor: epic.color || undefined,
                          }}
                        />
                      )}
                    </Stack>
                    {epic.description && (
                      <Typography variant="body2" color="text.secondary" mb={1}>
                        {epic.description}
                      </Typography>
                    )}
                    <Stack direction="row" alignItems="center" spacing={1} mt={1}>
                      <Box flex={1}>
                        <LinearProgress
                          variant="determinate"
                          value={pct}
                          sx={{
                            height: 8,
                            borderRadius: 4,
                            "& .MuiLinearProgress-bar": { bgcolor: epic.color },
                          }}
                        />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {epic.progress_done}/{epic.progress_total} ({pct}%)
                      </Typography>
                      <Tooltip title={t("p.plan.epics.viewTasks")}>
                        <IconButton size="small" onClick={() => setViewTasksEpic(epic)}>
                          <Eye size={16} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("common.edit")}>
                        <IconButton size="small" onClick={() => openEdit(epic)}>
                          <Pencil size={16} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("common.delete")}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={async () => {
                            if (
                              await confirm(
                                t("p.plan.epics.confirmDelete", {
                                  title: epic.title,
                                }),
                                {
                                  confirmLabel: t("p.plan.epics.confirmDeleteLabel"),
                                },
                              )
                            )
                              deleteMut.mutate(epic.id);
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
          );
        })}
      </Stack>

      {/* Create dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.plan.epics.new")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.plan.epics.fieldTitle")}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              fullWidth
            />
            <TextField
              label={t("p.plan.epics.fieldDescription")}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <FormControl fullWidth>
              <InputLabel>{t("p.plan.epics.fieldProject")}</InputLabel>
              <Select
                label={t("p.plan.epics.fieldProject")}
                value={form.project_id}
                onChange={(e) =>
                  setForm({ ...form, project_id: e.target.value as string })
                }
              >
                <MenuItem value="">
                  <em>{t("p.plan.epics.noProject")}</em>
                </MenuItem>
                {projects.map((p) => (
                  <MenuItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="body2">{t("common.color")}:</Typography>
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                style={{ width: 50, height: 30, border: "none", cursor: "pointer" }}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => createMut.mutate()}
            disabled={!form.title || createMut.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("p.plan.epics.edit")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.plan.epics.fieldTitle")}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              fullWidth
            />
            <TextField
              label={t("p.plan.epics.fieldDescription")}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <FormControl fullWidth>
              <InputLabel>{t("p.plan.epics.fieldProject")}</InputLabel>
              <Select
                label={t("p.plan.epics.fieldProject")}
                value={form.project_id}
                onChange={(e) =>
                  setForm({ ...form, project_id: e.target.value as string })
                }
              >
                <MenuItem value="">
                  <em>{t("p.plan.epics.noProject")}</em>
                </MenuItem>
                {projects.map((p) => (
                  <MenuItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>{t("p.plan.epics.fieldState")}</InputLabel>
              <Select
                label={t("p.plan.epics.fieldState")}
                value={form.state}
                onChange={(e) =>
                  setForm({ ...form, state: e.target.value as Epic["state"] })
                }
              >
                {EPIC_STATES.map((s) => (
                  <MenuItem key={s} value={s}>
                    {stateLabels[s]}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="body2">{t("common.color")}:</Typography>
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                style={{ width: 50, height: 30, border: "none", cursor: "pointer" }}
              />
            </Stack>
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
          <Button onClick={() => setEditOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => updateMut.mutate()}
            disabled={!form.title || updateMut.isPending}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog ver tareas de la épica */}
      <Dialog
        open={!!viewTasksEpic}
        onClose={() => setViewTasksEpic(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {t("p.plan.epics.tasksOf", {
            title: viewTasksEpic?.title,
            count: epicTasks.length,
          })}
        </DialogTitle>
        <DialogContent>
          <Box mb={2}>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                if (viewTasksEpic?.project) {
                  projectCtx.setProject({
                    id: viewTasksEpic.project,
                    name: projectMap.get(viewTasksEpic.project) || "",
                    color: viewTasksEpic.color || "#1976d2",
                  });
                  navigate(`/app/project/${viewTasksEpic.project}`);
                } else {
                  navigate("/app");
                }
              }}
            >
              {t("p.plan.epics.viewInTasks")}
            </Button>
          </Box>
          {isLoadingEpicTasks ? (
            <Stack alignItems="center" sx={{ py: 3 }}>
              <CircularProgress size={32} />
            </Stack>
          ) : epicTasks.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t("p.plan.epics.noTasks")}
            </Typography>
          ) : (
            <List dense>
              {epicTasks.map((task: Task) => (
                <ListItem
                  key={task.id}
                  sx={{ px: 0 }}
                  secondaryAction={
                    <Chip
                      label={taskPriorityLabel(task.priority)}
                      size="small"
                      variant="outlined"
                    />
                  }
                >
                  <ListItemText
                    primary={task.title}
                    secondary={
                      <Chip
                        label={taskStateLabel(task.state)}
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
          <Button onClick={() => setViewTasksEpic(null)}>{t("common.close")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
