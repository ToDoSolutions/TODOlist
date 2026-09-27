import { formatDate } from "../lib/dates";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { okrsApi, tasksApi, type ApiPayload } from "../api/resources";
import { setKeyResultLinkedTasks, type LinkedTaskRef } from "../api/featComp";
import { STATE_COLORS, type Task } from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  LinearProgress,
  IconButton,
  Stack,
  MenuItem,
  Tooltip,
  Alert,
  Divider,
  InputAdornment,
  Autocomplete,
} from "@mui/material";
import { Plus, Pencil, Trash2, TrendingUp, X, Check, Link2 } from "lucide-react";

interface Objective {
  id: number;
  title: string;
  description?: string;
  quarter: string;
  year: number;
  status: string;
  progress: number;
  key_results?: KeyResult[];
}

interface KrUpdate {
  id: number;
  old_value: number;
  new_value: number;
  note?: string;
  created_at: string;
}

interface KeyResult {
  id: number;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  owner?: number;
  progress: number;
  updates?: KrUpdate[];
  /** Tareas vinculadas (PATCH linked_tasks) — progreso derivado del backend. */
  linked_tasks_detail?: LinkedTaskRef[];
  linked_progress?: number;
}

const STATUSES = ["on_track", "at_risk", "behind", "achieved"];
const STATUS_COLORS: Record<string, "default" | "warning" | "error" | "success"> = {
  on_track: "default",
  at_risk: "warning",
  behind: "error",
  achieved: "success",
};

export default function OkrsPage() {
  const { t } = useTranslation();
  const statusLabel = (s: string) =>
    t(`p.collab.okrs.status.${s}`, { defaultValue: s.replace("_", " ") });
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [objDialog, setObjDialog] = useState(false);
  const [editingObj, setEditingObj] = useState<Objective | null>(null);
  const [objForm, setObjForm] = useState({
    title: "",
    description: "",
    quarter: "Q1",
    year: new Date().getFullYear(),
    status: "on_track",
  });

  const [krDialogForObj, setKrDialogForObj] = useState<number | null>(null);
  const [krForm, setKrForm] = useState({
    title: "",
    target_value: 100,
    current_value: 0,
    unit: "%",
  });

  const [updateDialogKr, setUpdateDialogKr] = useState<KeyResult | null>(null);
  const [updateForm, setUpdateForm] = useState({ new_value: 0, note: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["objectives"],
    queryFn: okrsApi.listObjectives,
  });
  const objectives: Objective[] = data?.results || data || [];

  const createObj = useMutation({
    mutationFn: (d: ApiPayload) => okrsApi.createObjective(d),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setObjDialog(false);
      resetObjForm();
      notify.success(t("p.collab.okrs.objCreated"));
    },
    onError: () => notify.error(t("p.collab.okrs.objCreateError")),
  });

  const updateObj = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      okrsApi.updateObjective(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setObjDialog(false);
      resetObjForm();
      notify.success(t("p.collab.okrs.objUpdated"));
    },
    onError: () => notify.error(t("p.collab.okrs.updateError")),
  });

  const deleteObj = useMutation({
    mutationFn: (id: number) => okrsApi.deleteObjective(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      notify.success(t("p.collab.okrs.objDeleted"));
    },
    onError: () => notify.error(t("p.collab.okrs.deleteError")),
  });

  const createKr = useMutation({
    mutationFn: (d: ApiPayload) => okrsApi.createKeyResult(d),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setKrDialogForObj(null);
      resetKrForm();
      notify.success(t("p.collab.okrs.krCreated"));
    },
    onError: () => notify.error(t("p.collab.okrs.krCreateError")),
  });

  const deleteKr = useMutation({
    mutationFn: (id: number) => okrsApi.deleteKeyResult(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      notify.success(t("p.collab.okrs.krDeleted"));
    },
    onError: () => notify.error(t("p.collab.okrs.deleteError")),
  });

  const updateValue = useMutation({
    mutationFn: ({
      id,
      newValue,
      note,
    }: {
      id: number;
      newValue: number;
      note: string;
    }) => okrsApi.updateValue(id, newValue, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setUpdateDialogKr(null);
      notify.success(t("p.collab.okrs.valueUpdated"));
    },
    onError: () => notify.error(t("p.collab.okrs.valueUpdateError")),
  });

  // --- Vincular tareas a un KeyResult (PATCH linked_tasks) ---
  type LinkableTask = Pick<Task, "id" | "title" | "state">;
  const [linkDialogKr, setLinkDialogKr] = useState<KeyResult | null>(null);
  const [linkSelection, setLinkSelection] = useState<LinkableTask[]>([]);

  // Tareas abiertas del usuario; se cargan solo al abrir el diálogo.
  const { data: openTasks } = useQuery({
    queryKey: ["tasks", "kr-linkable"],
    queryFn: () => tasksApi.list(),
    enabled: linkDialogKr !== null,
    select: (tasks) =>
      tasks.filter(
        (task) => !["completed", "cancelled", "archived"].includes(task.state),
      ),
  });
  const linkableTasks: LinkableTask[] = openTasks ?? [];

  const linkTasks = useMutation({
    mutationFn: ({ id, taskIds }: { id: number; taskIds: number[] }) =>
      setKeyResultLinkedTasks(id, taskIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setLinkDialogKr(null);
      notify.success(t("p.org.kr.saved"));
    },
    onError: () => notify.error(t("p.org.kr.saveError")),
  });

  const openLinkTasks = (kr: KeyResult) => {
    setLinkSelection(kr.linked_tasks_detail ?? []);
    setLinkDialogKr(kr);
  };

  const unlinkTask = (kr: KeyResult, taskId: number) => {
    const ids = (kr.linked_tasks_detail ?? [])
      .map((lt) => lt.id)
      .filter((ltId) => ltId !== taskId);
    linkTasks.mutate({ id: kr.id, taskIds: ids });
  };

  const [editKrDialog, setEditKrDialog] = useState<KeyResult | null>(null);
  const [editKrForm, setEditKrForm] = useState({
    title: "",
    target_value: 100,
    current_value: 0,
    unit: "%",
  });
  const updateKr = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      okrsApi.updateKeyResult(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setEditKrDialog(null);
      notify.success(t("p.collab.okrs.krUpdated"));
    },
    onError: () => notify.error(t("p.collab.okrs.krUpdateError")),
  });

  const openEditKr = (kr: KeyResult) => {
    setEditKrForm({
      title: kr.title,
      target_value: kr.target_value,
      current_value: kr.current_value,
      unit: kr.unit || "%",
    });
    setEditKrDialog(kr);
  };

  const resetObjForm = () => {
    setObjForm({
      title: "",
      description: "",
      quarter: "Q1",
      year: new Date().getFullYear(),
      status: "on_track",
    });
    setEditingObj(null);
  };
  const resetKrForm = () => {
    setKrForm({ title: "", target_value: 100, current_value: 0, unit: "%" });
  };

  const openEditObj = (obj: Objective) => {
    setEditingObj(obj);
    setObjForm({
      title: obj.title,
      description: obj.description || "",
      quarter: obj.quarter,
      year: obj.year,
      status: obj.status,
    });
    setObjDialog(true);
  };

  const openCreateObj = () => {
    resetObjForm();
    setObjDialog(true);
  };

  const submitObj = () => {
    if (!objForm.title.trim()) return;
    if (editingObj) updateObj.mutate({ id: editingObj.id, data: objForm });
    else createObj.mutate(objForm);
  };

  const submitKr = () => {
    if (!krForm.title.trim() || krDialogForObj === null) return;
    createKr.mutate({ ...krForm, objective: krDialogForObj });
  };

  const submitUpdate = () => {
    if (!updateDialogKr) return;
    updateValue.mutate({
      id: updateDialogKr.id,
      newValue: updateForm.new_value,
      note: updateForm.note,
    });
  };

  if (isLoading) return <CircularProgress />;

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h5" fontWeight={700}>
            {t("p.collab.okrs.title")}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t("p.collab.okrs.subtitle")}
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Plus size={18} />}
          onClick={openCreateObj}
        >
          {t("p.collab.okrs.newObjective")}
        </Button>
      </Box>

      {objectives.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {t("p.collab.okrs.emptyHint")}
        </Alert>
      )}

      {objectives.map((obj) => (
        <Paper key={obj.id} sx={{ p: 3, mb: 2 }}>
          {/* Header del objetivo */}
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              mb: 1,
            }}
          >
            <Box sx={{ flex: 1 }}>
              <Typography variant="h6" fontWeight={600}>
                {obj.title}
              </Typography>
              {obj.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {obj.description}
                </Typography>
              )}
            </Box>
            <Stack direction="row" spacing={0.5}>
              <Tooltip title={t("common.edit")}>
                <IconButton size="small" onClick={() => openEditObj(obj)}>
                  <Pencil size={16} />
                </IconButton>
              </Tooltip>
              <Tooltip title={t("common.delete")}>
                <IconButton
                  size="small"
                  color="error"
                  onClick={async () => {
                    if (await confirm(t("p.collab.okrs.confirmDeleteObj")))
                      deleteObj.mutate(obj.id);
                  }}
                >
                  <Trash2 size={16} />
                </IconButton>
              </Tooltip>
            </Stack>
          </Box>

          {/* Chips y progreso */}
          <Box sx={{ display: "flex", gap: 1, mb: 1.5, alignItems: "center" }}>
            <Chip label={`${obj.quarter} ${obj.year}`} size="small" variant="outlined" />
            <Chip
              label={statusLabel(obj.status)}
              size="small"
              color={STATUS_COLORS[obj.status] || "default"}
            />
            <Typography variant="caption" color="text.secondary" sx={{ ml: "auto" }}>
              {t("p.collab.okrs.pctDone", { value: obj.progress || 0 })}
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={obj.progress || 0}
            sx={{ height: 8, borderRadius: 4, mb: 2 }}
            color={obj.progress >= 100 ? "success" : "primary"}
          />

          <Divider sx={{ mb: 2 }} />

          {/* Key results */}
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            {t("p.collab.okrs.keyResults")}
          </Typography>
          {obj.key_results && obj.key_results.length > 0 ? (
            <Stack spacing={1.5}>
              {obj.key_results.map((kr) => {
                const pct =
                  kr.target_value > 0
                    ? Math.min(100, (kr.current_value / kr.target_value) * 100)
                    : 0;
                return (
                  <Box
                    key={kr.id}
                    sx={{ pl: 2, borderLeft: "3px solid", borderColor: "primary.main" }}
                  >
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <Typography variant="body2" fontWeight={500}>
                        {kr.title}
                      </Typography>
                      <Stack direction="row" spacing={0.5}>
                        <Tooltip title={t("p.org.kr.linkTasks")}>
                          <IconButton size="small" onClick={() => openLinkTasks(kr)}>
                            <Link2 size={14} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={t("p.collab.okrs.updateValue")}>
                          <IconButton
                            size="small"
                            onClick={() => {
                              setUpdateDialogKr(kr);
                              setUpdateForm({ new_value: kr.current_value, note: "" });
                            }}
                          >
                            <TrendingUp size={14} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={t("p.collab.okrs.editKr")}>
                          <IconButton size="small" onClick={() => openEditKr(kr)}>
                            <Pencil size={14} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={t("p.collab.okrs.deleteKr")}>
                          <IconButton
                            size="small"
                            color="error"
                            onClick={async () => {
                              if (await confirm(t("p.collab.okrs.confirmDeleteKr")))
                                deleteKr.mutate(kr.id);
                            }}
                          >
                            <X size={14} />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </Box>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}>
                      <Typography variant="caption" color="text.secondary">
                        {kr.current_value} / {kr.target_value} {kr.unit}
                      </Typography>
                      <Box sx={{ flex: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={pct}
                          sx={{ height: 6, borderRadius: 3 }}
                          color={pct >= 100 ? "success" : "primary"}
                        />
                      </Box>
                      <Typography variant="caption" fontWeight={600}>
                        {Math.round(pct)}%
                      </Typography>
                      {typeof kr.linked_progress === "number" && (
                        <Tooltip title={t("p.org.kr.linked")}>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ whiteSpace: "nowrap" }}
                          >
                            ·{" "}
                            {t("p.org.kr.linkedProgress", {
                              value: Math.round(kr.linked_progress),
                            })}
                          </Typography>
                        </Tooltip>
                      )}
                    </Box>
                    {kr.linked_tasks_detail && kr.linked_tasks_detail.length > 0 && (
                      <Stack
                        direction="row"
                        spacing={0.5}
                        flexWrap="wrap"
                        useFlexGap
                        sx={{ mt: 0.75 }}
                      >
                        {kr.linked_tasks_detail.map((lt) => (
                          <Chip
                            key={lt.id}
                            size="small"
                            variant="outlined"
                            label={lt.title}
                            onDelete={() => unlinkTask(kr, lt.id)}
                            icon={
                              <Box
                                component="span"
                                sx={{
                                  width: 8,
                                  height: 8,
                                  borderRadius: "50%",
                                  bgcolor: STATE_COLORS[lt.state] ?? "grey.500",
                                  ml: 0.5,
                                }}
                              />
                            }
                          />
                        ))}
                      </Stack>
                    )}
                    {kr.updates && kr.updates.length > 0 && (
                      <Box
                        sx={{
                          mt: 1,
                          pl: 1,
                          borderLeft: "2px solid",
                          borderColor: "divider",
                        }}
                      >
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ display: "block", mb: 0.5 }}
                        >
                          {t("p.collab.okrs.updatesHistory", {
                            count: kr.updates.length,
                          })}
                        </Typography>
                        {kr.updates.slice(0, 5).map((u) => (
                          <Box
                            key={u.id}
                            sx={{
                              display: "flex",
                              gap: 1,
                              alignItems: "baseline",
                              mb: 0.25,
                            }}
                          >
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{ whiteSpace: "nowrap" }}
                            >
                              {formatDate(u.created_at)}
                            </Typography>
                            <Typography variant="caption" fontWeight={500}>
                              {u.old_value} → {u.new_value} {kr.unit}
                            </Typography>
                            {u.note && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ fontStyle: "italic" }}
                              >
                                {u.note}
                              </Typography>
                            )}
                          </Box>
                        ))}
                        {kr.updates.length > 5 && (
                          <Typography variant="caption" color="text.secondary">
                            {t("p.collab.okrs.moreUpdates", {
                              count: kr.updates.length - 5,
                            })}
                          </Typography>
                        )}
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Stack>
          ) : (
            <Typography variant="caption" color="text.secondary">
              {t("p.collab.okrs.noKrs")}
            </Typography>
          )}

          <Button
            size="small"
            startIcon={<Plus size={14} />}
            sx={{ mt: 2 }}
            onClick={() => {
              setKrDialogForObj(obj.id);
              resetKrForm();
            }}
          >
            {t("p.collab.okrs.addKr")}
          </Button>
        </Paper>
      ))}

      {/* Dialog: Crear/Editar Objetivo */}
      <Dialog
        open={objDialog}
        onClose={() => setObjDialog(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>
          {editingObj
            ? t("p.collab.okrs.editObjective")
            : t("p.collab.okrs.newObjective")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.collab.field.title")}
              fullWidth
              autoFocus
              value={objForm.title}
              onChange={(e) => setObjForm({ ...objForm, title: e.target.value })}
            />
            <TextField
              label={t("p.collab.field.description")}
              fullWidth
              multiline
              rows={2}
              value={objForm.description}
              onChange={(e) => setObjForm({ ...objForm, description: e.target.value })}
            />
            <Stack direction="row" spacing={2}>
              <TextField
                fullWidth
                select
                label={t("p.collab.okrs.quarter")}
                value={objForm.quarter}
                onChange={(e) => setObjForm({ ...objForm, quarter: e.target.value })}
                SelectProps={{ native: true }}
              >
                {["Q1", "Q2", "Q3", "Q4"].map((q) => (
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </TextField>
              <TextField
                fullWidth
                type="number"
                label={t("p.collab.okrs.year")}
                value={objForm.year}
                onChange={(e) => setObjForm({ ...objForm, year: Number(e.target.value) })}
              />
            </Stack>
            <TextField
              fullWidth
              select
              label={t("p.collab.field.status")}
              value={objForm.status}
              onChange={(e) => setObjForm({ ...objForm, status: e.target.value })}
            >
              {STATUSES.map((s) => (
                <MenuItem key={s} value={s}>
                  {statusLabel(s)}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setObjDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={!objForm.title.trim()}
            onClick={submitObj}
          >
            {editingObj ? t("common.save") : t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Crear Key Result */}
      <Dialog
        open={krDialogForObj !== null}
        onClose={() => setKrDialogForObj(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{t("p.collab.okrs.newKr")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.collab.field.title")}
              fullWidth
              autoFocus
              value={krForm.title}
              onChange={(e) => setKrForm({ ...krForm, title: e.target.value })}
            />
            <Stack direction="row" spacing={2}>
              <TextField
                fullWidth
                type="number"
                label={t("p.collab.okrs.targetValue")}
                value={krForm.target_value}
                onChange={(e) =>
                  setKrForm({ ...krForm, target_value: Number(e.target.value) })
                }
              />
              <TextField
                fullWidth
                type="number"
                label={t("p.collab.okrs.currentValue")}
                value={krForm.current_value}
                onChange={(e) =>
                  setKrForm({ ...krForm, current_value: Number(e.target.value) })
                }
              />
            </Stack>
            <TextField
              label={t("p.collab.okrs.unit")}
              fullWidth
              placeholder={t("p.collab.okrs.unitPlaceholder")}
              value={krForm.unit}
              onChange={(e) => setKrForm({ ...krForm, unit: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setKrDialogForObj(null)}>{t("common.cancel")}</Button>
          <Button variant="contained" disabled={!krForm.title.trim()} onClick={submitKr}>
            {t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Actualizar valor de KR */}
      <Dialog
        open={!!updateDialogKr}
        onClose={() => setUpdateDialogKr(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>{t("p.collab.okrs.updateProgress")}</DialogTitle>
        <DialogContent>
          {updateDialogKr && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t("p.collab.okrs.currentKr", {
                title: updateDialogKr.title,
                value: updateDialogKr.current_value,
                unit: updateDialogKr.unit,
              })}
            </Typography>
          )}
          <Stack spacing={2}>
            <TextField
              label={t("p.collab.okrs.newValue")}
              type="number"
              fullWidth
              autoFocus
              value={updateForm.new_value}
              onChange={(e) =>
                setUpdateForm({ ...updateForm, new_value: Number(e.target.value) })
              }
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">{updateDialogKr?.unit}</InputAdornment>
                ),
              }}
            />
            <TextField
              label={t("p.collab.okrs.noteOptional")}
              fullWidth
              multiline
              rows={2}
              value={updateForm.note}
              onChange={(e) => setUpdateForm({ ...updateForm, note: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUpdateDialogKr(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            startIcon={<Check size={16} />}
            onClick={submitUpdate}
          >
            {t("p.collab.okrs.update")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit KR dialog */}
      <Dialog
        open={!!editKrDialog}
        onClose={() => setEditKrDialog(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>{t("p.collab.okrs.editKrTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("p.collab.field.title")}
              fullWidth
              value={editKrForm.title}
              onChange={(e) => setEditKrForm({ ...editKrForm, title: e.target.value })}
            />
            <TextField
              label={t("p.collab.okrs.targetValue")}
              type="number"
              fullWidth
              value={editKrForm.target_value}
              onChange={(e) =>
                setEditKrForm({ ...editKrForm, target_value: Number(e.target.value) })
              }
            />
            <TextField
              label={t("p.collab.okrs.currentValue")}
              type="number"
              fullWidth
              value={editKrForm.current_value}
              onChange={(e) =>
                setEditKrForm({ ...editKrForm, current_value: Number(e.target.value) })
              }
            />
            <TextField
              label={t("p.collab.okrs.unit")}
              fullWidth
              value={editKrForm.unit}
              onChange={(e) => setEditKrForm({ ...editKrForm, unit: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditKrDialog(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            startIcon={<Check size={16} />}
            disabled={updateKr.isPending}
            onClick={() =>
              editKrDialog && updateKr.mutate({ id: editKrDialog.id, data: editKrForm })
            }
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: vincular tareas al KeyResult */}
      <Dialog
        open={!!linkDialogKr}
        onClose={() => setLinkDialogKr(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{t("p.org.kr.dialogTitle")}</DialogTitle>
        <DialogContent>
          {linkDialogKr && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {linkDialogKr.title}
            </Typography>
          )}
          <Autocomplete
            multiple
            options={linkableTasks}
            value={linkSelection}
            getOptionLabel={(o) => o.title}
            isOptionEqualToValue={(o, v) => o.id === v.id}
            onChange={(_, v) => setLinkSelection(v)}
            noOptionsText={t("p.org.kr.noOpenTasks")}
            renderInput={(params) => (
              <TextField {...params} label={t("p.org.kr.selectTasks")} />
            )}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLinkDialogKr(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={linkTasks.isPending}
            onClick={() =>
              linkDialogKr &&
              linkTasks.mutate({
                id: linkDialogKr.id,
                taskIds: linkSelection.map((task) => task.id),
              })
            }
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
