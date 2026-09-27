import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  useTheme,
} from "@mui/material";
import { Plus, Pencil, Trash2, Copy, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { taskTemplatesApi, type ApiPayload } from "../api/resources";
import type { TaskTemplateItem } from "../types";
import { notify } from "../notify";

interface TaskTemplate {
  id: number;
  name: string;
  description?: string;
  default_priority?: number;
  default_project?: number;
  default_project_name?: string;
  default_state?: string;
}

interface TemplateForm {
  name: string;
  description: string;
  default_priority: string;
  default_project_id: string;
  default_state: string;
}

const emptyForm: TemplateForm = {
  name: "",
  description: "",
  default_priority: "3",
  default_project_id: "",
  default_state: "todo",
};

interface OverrideForm {
  title: string;
  project_id: string;
}

const emptyOverride: OverrideForm = {
  title: "",
  project_id: "",
};

export default function TaskTemplatesPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TaskTemplate | null>(null);
  const [form, setForm] = useState<TemplateForm>(emptyForm);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [createTaskFor, setCreateTaskFor] = useState<TaskTemplate | null>(null);
  const [override, setOverride] = useState<OverrideForm>(emptyOverride);

  const { data: templatesData, isLoading } = useQuery({
    queryKey: ["task-templates"],
    queryFn: taskTemplatesApi.list,
  });
  const templates: TaskTemplate[] = Array.isArray(templatesData)
    ? templatesData
    : ((templatesData as { results?: TaskTemplateItem[] } | undefined)?.results ?? []);

  const createMut = useMutation({
    mutationFn: () =>
      taskTemplatesApi.create({
        name: form.name.trim(),
        description: form.description,
        project: form.default_project_id ? Number(form.default_project_id) : null,
        template_data: {
          priority: Number(form.default_priority),
          state: form.default_state,
        },
      }),
    onSuccess: () => {
      notify.success(t("p.ops.templates.created"));
      qc.invalidateQueries({ queryKey: ["task-templates"] });
      setOpen(false);
    },
    onError: () => notify.error(t("p.ops.templates.createError")),
  });

  const updateMut = useMutation({
    mutationFn: (id: number) =>
      taskTemplatesApi.update(id, {
        name: form.name.trim(),
        description: form.description,
        project: form.default_project_id ? Number(form.default_project_id) : null,
        template_data: {
          priority: Number(form.default_priority),
          state: form.default_state,
        },
      }),
    onSuccess: () => {
      notify.success(t("p.ops.templates.updated"));
      qc.invalidateQueries({ queryKey: ["task-templates"] });
      setOpen(false);
    },
    onError: () => notify.error(t("p.ops.templates.updateError")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => taskTemplatesApi.delete(id),
    onSuccess: () => {
      notify.success(t("p.ops.templates.deleted"));
      qc.invalidateQueries({ queryKey: ["task-templates"] });
      setDeleteId(null);
    },
    onError: () => notify.error(t("p.ops.templates.deleteError")),
  });

  const createTaskMut = useMutation({
    mutationFn: () => {
      const overrides: ApiPayload = {};
      if (override.title.trim()) overrides.title = override.title.trim();
      if (override.project_id) overrides.project_id = Number(override.project_id);
      return taskTemplatesApi.createTask(createTaskFor!.id, overrides);
    },
    onSuccess: () => {
      notify.success(t("p.ops.templates.taskCreated"));
      setCreateTaskFor(null);
      setOverride(emptyOverride);
    },
    onError: () => notify.error(t("p.ops.templates.taskCreateError")),
  });

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (tpl: TaskTemplateItem) => {
    setEditing(tpl);
    const td = tpl.template_data || {};
    setForm({
      name: tpl.name,
      description: tpl.description ?? "",
      default_priority: String(td.priority ?? 3),
      default_project_id: tpl.project ? String(tpl.project) : "",
      default_state: String(td.state ?? "pending"),
    });
    setOpen(true);
  };

  const save = () => {
    if (!form.name.trim()) return;
    if (editing) {
      updateMut.mutate(editing.id);
    } else {
      createMut.mutate();
    }
  };

  const openCreateTask = (tpl: TaskTemplate) => {
    setCreateTaskFor(tpl);
    setOverride(emptyOverride);
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h5" fontWeight={700}>
          {t("p.ops.templates.title")}
        </Typography>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          {t("p.ops.templates.new")}
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : templates.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <FileText size={32} style={{ color: theme.palette.divider }} />
          <Typography color="text.secondary" mt={1}>
            {t("p.ops.templates.empty")}
          </Typography>
        </Paper>
      ) : (
        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("common.name")}</TableCell>
                <TableCell>{t("p.ops.description")}</TableCell>
                <TableCell>{t("p.ops.templates.priority")}</TableCell>
                <TableCell>{t("p.ops.project")}</TableCell>
                <TableCell align="right">{t("p.ops.actions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {templates.map((tpl) => (
                <TableRow key={tpl.id} hover>
                  <TableCell>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <FileText
                        size={14}
                        style={{ color: theme.palette.text.secondary }}
                      />
                      <Typography variant="body2" fontWeight={600}>
                        {tpl.name}
                      </Typography>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      noWrap
                      maxWidth={220}
                    >
                      {tpl.description || "—"}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={`P${tpl.default_priority ?? "—"}`} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {tpl.default_project_name ??
                        (tpl.default_project ? `#${tpl.default_project}` : "—")}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title={t("p.ops.templates.createTask")}>
                      <IconButton size="small" onClick={() => openCreateTask(tpl)}>
                        <Copy size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t("common.edit")}>
                      <IconButton size="small" onClick={() => openEdit(tpl)}>
                        <Pencil size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t("common.delete")}>
                      <IconButton size="small" onClick={() => setDeleteId(tpl.id)}>
                        <Trash2 size={16} />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>
          {editing ? t("p.ops.templates.editTitle") : t("p.ops.templates.new")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              fullWidth
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              autoFocus
            />
            <TextField
              label={t("p.ops.description")}
              fullWidth
              multiline
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <TextField
              label={t("p.ops.templates.defaultPriority")}
              fullWidth
              type="number"
              value={form.default_priority}
              onChange={(e) => setForm({ ...form, default_priority: e.target.value })}
            />
            <TextField
              label={t("p.ops.templates.defaultProject")}
              fullWidth
              type="number"
              value={form.default_project_id}
              onChange={(e) => setForm({ ...form, default_project_id: e.target.value })}
            />
            <TextField
              label={t("p.ops.templates.defaultState")}
              fullWidth
              value={form.default_state}
              onChange={(e) => setForm({ ...form, default_state: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={save}
            disabled={!form.name.trim() || createMut.isPending || updateMut.isPending}
          >
            {editing ? t("common.save") : t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create task from template dialog */}
      <Dialog
        open={createTaskFor !== null}
        onClose={() => setCreateTaskFor(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{t("p.ops.templates.createTask")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={2}>
            {t("p.ops.templates.templateLabel")}: <strong>{createTaskFor?.name}</strong>.{" "}
            {t("p.ops.templates.createTaskHint")}
          </Typography>
          <Stack spacing={2}>
            <TextField
              label={t("p.ops.templates.titleOverride")}
              fullWidth
              value={override.title}
              onChange={(e) => setOverride({ ...override, title: e.target.value })}
              autoFocus
            />
            <TextField
              label={t("p.ops.templates.projectOverride")}
              fullWidth
              type="number"
              value={override.project_id}
              onChange={(e) => setOverride({ ...override, project_id: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateTaskFor(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={() => createTaskMut.mutate()}
            disabled={createTaskMut.isPending}
          >
            {t("p.ops.templates.createTaskBtn")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs">
        <DialogTitle>{t("p.ops.templates.deleteTitle")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning">{t("p.ops.templates.confirmDelete")}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>{t("common.cancel")}</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
          >
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
