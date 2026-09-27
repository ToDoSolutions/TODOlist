import { useState } from "react";
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
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  useTheme,
} from "@mui/material";
import { Plus, Trash2, Settings, Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { customFieldsApi, projectsApi, type ApiPayload } from "../api/resources";
import type { CustomField, CustomFieldValue, Project } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";

const FIELD_TYPES = ["text", "number", "select", "multiselect", "date"] as const;
type FieldType = (typeof FIELD_TYPES)[number];

export default function CustomFieldsPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState<{
    project_id: string;
    name: string;
    type: FieldType;
    options: string;
  }>({
    project_id: "",
    name: "",
    type: "text",
    options: "",
  });

  // Task values section
  const [taskIdInput, setTaskIdInput] = useState("");
  const [taskId, setTaskId] = useState<number | null>(null);
  const [valueForm, setValueForm] = useState<{ fieldId: number; value: string }>({
    fieldId: 0,
    value: "",
  });
  const [editingValueId, setEditingValueId] = useState<number | null>(null);
  const [editValueText, setEditValueText] = useState("");

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects: Project[] = Array.isArray(projectsData)
    ? projectsData
    : (projectsData as { results?: Project[] } | undefined)?.results || [];
  const projectMap = new Map(projects.map((p) => [p.id, p.name]));

  const { data: fields, isLoading } = useQuery({
    queryKey: ["custom-fields"],
    queryFn: customFieldsApi.list,
  });

  const { data: valuesData, isLoading: valuesLoading } = useQuery({
    queryKey: ["custom-field-values", taskId],
    queryFn: () => customFieldsApi.values(),
    enabled: !!taskId,
  });

  const createMut = useMutation({
    mutationFn: customFieldsApi.create,
    onSuccess: () => {
      notify.success(t("p.ops.cf.created"));
      qc.invalidateQueries({ queryKey: ["custom-fields"] });
      setDialogOpen(false);
    },
    onError: () => notify.error(t("p.ops.cf.createError")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => customFieldsApi.remove(id),
    onSuccess: () => {
      notify.info(t("p.ops.cf.deleted"));
      qc.invalidateQueries({ queryKey: ["custom-fields"] });
      setDeleteId(null);
    },
    onError: () => notify.error(t("p.ops.cf.deleteError")),
  });

  const setValueMut = useMutation({
    mutationFn: (data: { task: number; field: number; value: string }) =>
      customFieldsApi.setValue(data),
    onSuccess: () => {
      notify.success(t("p.ops.cf.valueUpdated"));
      qc.invalidateQueries({ queryKey: ["custom-field-values", taskId] });
      setValueForm({ fieldId: 0, value: "" });
    },
    onError: () => notify.error(t("p.ops.cf.valueUpdateError")),
  });

  const updateValueMut = useMutation({
    mutationFn: ({ id, value }: { id: number; value: string }) =>
      customFieldsApi.updateValue(id, value),
    onSuccess: () => {
      notify.success(t("p.ops.cf.valueUpdated"));
      qc.invalidateQueries({ queryKey: ["custom-field-values", taskId] });
      setEditingValueId(null);
    },
    onError: () => notify.error(t("p.ops.cf.valueUpdateError")),
  });

  const removeValueMut = useMutation({
    mutationFn: (id: number) => customFieldsApi.removeValue(id),
    onSuccess: () => {
      notify.info(t("p.ops.cf.valueDeleted"));
      qc.invalidateQueries({ queryKey: ["custom-field-values", taskId] });
    },
    onError: () => notify.error(t("p.ops.cf.valueDeleteError")),
  });

  const handleCreate = () => {
    const payload: ApiPayload = {
      name: form.name,
      field_type: form.type,
      project: Number(form.project_id),
    };
    if (form.type === "select" || form.type === "multiselect") {
      payload.options = form.options
        .split(",")
        .map((o) => o.trim())
        .filter(Boolean);
    }
    createMut.mutate(payload);
  };

  const fieldList: CustomField[] = Array.isArray(fields)
    ? fields
    : (fields as { results?: CustomField[] } | undefined)?.results || [];
  const allValues: CustomFieldValue[] = valuesData || [];
  const taskValues = taskId ? allValues.filter((v) => v.task === taskId) : [];

  const loadTaskValues = () => {
    const id = Number(taskIdInput);
    if (!id) {
      notify.warning(t("p.ops.cf.invalidTaskId"));
      return;
    }
    setTaskId(id);
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Alert severity="info" sx={{ mb: 3 }}>
        {t("p.ops.cf.infoAlert")}
      </Alert>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Settings size={24} style={{ color: theme.palette.primary.main }} />
          <Typography variant="h5" fontWeight={700}>
            {t("p.ops.cf.title")}
          </Typography>
        </Stack>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={() => {
            setForm({ project_id: "", name: "", type: "text", options: "" });
            setDialogOpen(true);
          }}
        >
          {t("p.ops.cf.new")}
        </Button>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={5}>
          <CircularProgress />
        </Box>
      ) : fieldList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Settings size={48} color="text.disabled" />
          <Typography color="text.secondary" mt={1}>
            {t("p.ops.cf.empty")}
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {fieldList.map((f) => (
            <Paper key={f.id} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between">
                <Box>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography variant="subtitle1" fontWeight={600}>
                      {f.name}
                    </Typography>
                    <Chip
                      size="small"
                      label={f.type}
                      sx={{ height: 20, fontSize: 11 }}
                      color="primary"
                      variant="outlined"
                    />
                    {f.project && (
                      <Chip
                        size="small"
                        label={String(
                          projectMap.get(f.project) ||
                            t("p.ops.projectFallback", { id: f.project }),
                        )}
                        sx={{ height: 20, fontSize: 11 }}
                        variant="outlined"
                      />
                    )}
                  </Stack>
                  {(f.type === "select" || f.type === "multiselect") && (
                    <Stack
                      direction="row"
                      spacing={0.5}
                      mt={1}
                      flexWrap="wrap"
                      useFlexGap
                    >
                      {(f.options || []).map((o: string) => (
                        <Chip
                          key={o}
                          size="small"
                          label={o}
                          sx={{ height: 20, fontSize: 10 }}
                          variant="outlined"
                        />
                      ))}
                    </Stack>
                  )}
                </Box>
                <Tooltip title={t("common.delete")}>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => setDeleteId(f.id)}
                  >
                    <Trash2 size={16} />
                  </IconButton>
                </Tooltip>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Sección de valores por tarea */}
      <Paper variant="outlined" sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" fontWeight={700} mb={2}>
          {t("p.ops.cf.valuesTitle")}
        </Typography>
        <Stack direction="row" spacing={1} mb={2}>
          <TextField
            label={t("p.ops.cf.taskIdLabel")}
            value={taskIdInput}
            onChange={(e) => setTaskIdInput(e.target.value)}
            size="small"
            type="number"
          />
          <Button variant="outlined" onClick={loadTaskValues}>
            {t("p.ops.cf.loadValues")}
          </Button>
        </Stack>

        {taskId &&
          (valuesLoading ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress size={24} />
            </Box>
          ) : taskValues.length === 0 ? (
            <Alert severity="info">{t("p.ops.cf.noValues")}</Alert>
          ) : (
            <Stack spacing={1} mb={3}>
              {taskValues.map((v) => {
                const field = fieldList.find((f) => f.id === v.field);
                const valStr = String(v.value_text ?? v.value ?? "");
                return (
                  <Stack
                    key={v.id ?? `${v.field}-${v.value}`}
                    direction="row"
                    alignItems="center"
                    justifyContent="space-between"
                    sx={{ py: 0.5 }}
                  >
                    {editingValueId === v.id ? (
                      <Stack
                        direction="row"
                        spacing={1}
                        alignItems="center"
                        sx={{ flex: 1 }}
                      >
                        <Typography variant="body2" fontWeight={600}>
                          {field?.name ?? t("p.ops.fieldFallback", { id: v.field })}:
                        </Typography>
                        <TextField
                          size="small"
                          value={editValueText}
                          onChange={(e) => setEditValueText(e.target.value)}
                          sx={{ flex: 1, maxWidth: 300 }}
                        />
                        <Button
                          size="small"
                          variant="contained"
                          onClick={() =>
                            updateValueMut.mutate({ id: v.id, value: editValueText })
                          }
                          disabled={updateValueMut.isPending}
                        >
                          {t("common.save")}
                        </Button>
                        <Button size="small" onClick={() => setEditingValueId(null)}>
                          {t("common.cancel")}
                        </Button>
                      </Stack>
                    ) : (
                      <>
                        <Typography variant="body2">
                          <strong>
                            {field?.name ?? t("p.ops.fieldFallback", { id: v.field })}:
                          </strong>{" "}
                          {valStr}
                        </Typography>
                        <Stack direction="row" spacing={0.5}>
                          <Tooltip title={t("p.ops.cf.editValue")}>
                            <IconButton
                              size="small"
                              onClick={() => {
                                setEditingValueId(v.id);
                                setEditValueText(valStr);
                              }}
                            >
                              <Pencil size={14} />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t("p.ops.cf.deleteValue")}>
                            <IconButton
                              size="small"
                              color="error"
                              onClick={async () => {
                                if (await confirm(t("p.ops.cf.confirmDeleteValue")))
                                  removeValueMut.mutate(v.id);
                              }}
                            >
                              <Trash2 size={14} />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </>
                    )}
                  </Stack>
                );
              })}
            </Stack>
          ))}

        {taskId && fieldList.length > 0 && (
          <Stack direction="row" spacing={1} alignItems="center">
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>{t("p.ops.field")}</InputLabel>
              <Select
                value={valueForm.fieldId}
                label={t("p.ops.field")}
                onChange={(e) =>
                  setValueForm({ ...valueForm, fieldId: e.target.value as number })
                }
              >
                <MenuItem value={0} disabled>
                  {t("p.ops.cf.selectField")}
                </MenuItem>
                {fieldList.map((f) => (
                  <MenuItem key={f.id} value={f.id}>
                    {f.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label={t("p.ops.value")}
              value={valueForm.value}
              onChange={(e) => setValueForm({ ...valueForm, value: e.target.value })}
              size="small"
            />
            <Button
              variant="contained"
              disabled={!valueForm.fieldId || setValueMut.isPending}
              onClick={() =>
                setValueMut.mutate({
                  task: taskId,
                  field: valueForm.fieldId,
                  value: valueForm.value,
                })
              }
            >
              {t("common.save")}
            </Button>
          </Stack>
        )}
      </Paper>

      {/* Dialog de creación */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("p.ops.cf.createTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl fullWidth size="small" required>
              <InputLabel>{t("p.ops.project")}</InputLabel>
              <Select
                value={form.project_id}
                label={t("p.ops.cf.projectRequired")}
                onChange={(e) =>
                  setForm({ ...form, project_id: e.target.value as string })
                }
              >
                <MenuItem value="" disabled>
                  {t("p.ops.selectProject")}
                </MenuItem>
                {projects.map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Alert severity="info">{t("p.ops.cf.projectInfo")}</Alert>
            <TextField
              label={t("common.name")}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              size="small"
            />
            <FormControl fullWidth size="small">
              <InputLabel>{t("p.ops.type")}</InputLabel>
              <Select
                value={form.type}
                label={t("p.ops.type")}
                onChange={(e) =>
                  setForm({ ...form, type: e.target.value as FieldType, options: "" })
                }
              >
                {FIELD_TYPES.map((ft) => (
                  <MenuItem key={ft} value={ft}>
                    {ft}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {(form.type === "select" || form.type === "multiselect") && (
              <TextField
                label={t("p.ops.cf.optionsLabel")}
                value={form.options}
                onChange={(e) => setForm({ ...form, options: e.target.value })}
                fullWidth
                size="small"
                helperText={t("p.ops.cf.optionsHelp")}
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!form.name || !form.project_id || createMut.isPending}
          >
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmación de borrado */}
      <Dialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t("p.ops.cf.deleteTitle")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning">{t("p.ops.cf.confirmDelete")}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
            disabled={deleteMut.isPending}
          >
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
