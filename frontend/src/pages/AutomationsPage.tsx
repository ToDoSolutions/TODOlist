import { formatDateTime } from "../lib/dates";
import { useState } from "react";
import { TaskListSkeleton } from "../components/ui/skeletons";
import PageHeader from "../components/ui/PageHeader";
import { ErrorState } from "../components/ui/states";
import {
  Box,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Switch,
  FormControlLabel,
  IconButton,
  Tooltip,
  Collapse,
  useTheme,
} from "@mui/material";
import {
  Plus,
  Zap,
  Play,
  History,
  ChevronDown,
  ChevronRight,
  Trash2,
  Pencil,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  automationsApi,
  sprintsApi,
  type ApiPayload,
  type Sprint,
} from "../api/resources";
import {
  STATE_LABELS,
  PRIORITY_LABELS,
  type AutomationRule,
  type AutomationLog,
} from "../types";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";

type ParamFieldType = "text" | "number" | "state" | "priority" | "sprint";

interface CondRow {
  field: string;
  operator: string;
  value: string;
}

const NUMERIC_PARAM_KEYS = new Set(["priority", "days_from_now", "sprint_id"]);

export default function AutomationsPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    trigger: "task_blocked",
    action: "set_priority",
    schedule_hours: 24,
    enabled: true,
  });
  const [conds, setConds] = useState<CondRow[]>([]);
  const [params, setParams] = useState<Record<string, string>>({});

  const TRIGGER_LABELS: Record<string, string> = {
    task_created: t("p.ops.automations.trigger.taskCreated"),
    task_state_changed: t("p.ops.automations.trigger.stateChanged"),
    task_completed: t("p.ops.automations.trigger.taskCompleted"),
    task_blocked: t("p.ops.automations.trigger.taskBlocked"),
    task_overdue: t("p.ops.automations.trigger.taskOverdue"),
    comment_added: t("p.ops.automations.trigger.commentAdded"),
    sprint_started: t("p.ops.automations.trigger.sprintStarted"),
    sprint_closed: t("p.ops.automations.trigger.sprintClosed"),
    daily_check: t("p.ops.automations.trigger.dailyCheck"),
    scheduled: t("p.ops.automations.trigger.scheduled"),
  };

  const ACTION_LABELS: Record<string, string> = {
    set_priority: t("p.ops.automations.action.setPriority"),
    set_state: t("p.ops.automations.action.setState"),
    set_assignee: t("p.ops.automations.action.setAssignee"),
    add_tag: t("p.ops.automations.action.addTag"),
    set_due_date: t("p.ops.automations.action.setDueDate"),
    move_to_sprint: t("p.ops.automations.action.moveToSprint"),
    subtasks_in_progress: t("p.ops.automations.action.subtasksInProgress"),
    create_notification: t("p.ops.automations.action.createNotification"),
    create_task: t("p.ops.automations.action.createTask"),
    call_webhook: t("p.ops.automations.action.callWebhook"),
  };

  // Campos de contexto disponibles en las condiciones (ver apps/automations/signals.py)
  const CONDITION_FIELDS = [
    { value: "new_state", label: t("p.ops.automations.field.newState") },
    { value: "old_state", label: t("p.ops.automations.field.oldState") },
    { value: "due_date", label: t("p.ops.automations.field.dueDate") },
    { value: "check_time", label: t("p.ops.automations.field.checkTime") },
  ];

  const CONDITION_OPERATORS = [
    { value: "equals", label: t("p.ops.automations.op.equals") },
    { value: "not_equals", label: t("p.ops.automations.op.notEquals") },
    { value: "contains", label: t("p.ops.automations.op.contains") },
    { value: "gt", label: t("p.ops.automations.op.gt") },
    { value: "lt", label: t("p.ops.automations.op.lt") },
  ];

  // Parámetros tipados por acción (ver _action_* en apps/automations/engine.py)
  const ACTION_PARAMS: Record<
    string,
    { key: string; label: string; type: ParamFieldType }[]
  > = {
    set_priority: [
      { key: "priority", label: t("p.ops.automations.param.priority"), type: "priority" },
    ],
    set_state: [
      { key: "state", label: t("p.ops.automations.param.state"), type: "state" },
    ],
    set_assignee: [
      {
        key: "assignee_email",
        label: t("p.ops.automations.param.assigneeEmail"),
        type: "text",
      },
    ],
    add_tag: [
      { key: "tag_name", label: t("p.ops.automations.param.tagName"), type: "text" },
      { key: "tag_color", label: t("p.ops.automations.param.tagColor"), type: "text" },
    ],
    set_due_date: [
      {
        key: "days_from_now",
        label: t("p.ops.automations.param.daysFromNow"),
        type: "number",
      },
    ],
    move_to_sprint: [
      { key: "sprint_id", label: t("p.ops.automations.param.sprint"), type: "sprint" },
    ],
    subtasks_in_progress: [],
    create_notification: [
      { key: "title", label: t("p.ops.automations.param.title"), type: "text" },
      { key: "body", label: t("p.ops.automations.param.body"), type: "text" },
      { key: "action_url", label: t("p.ops.automations.param.actionUrl"), type: "text" },
    ],
    create_task: [
      { key: "title", label: t("p.ops.automations.param.title"), type: "text" },
      { key: "description", label: t("p.ops.description"), type: "text" },
      {
        key: "priority",
        label: t("p.ops.automations.param.priority"),
        type: "priority",
      },
      { key: "state", label: t("p.ops.automations.param.initialState"), type: "state" },
    ],
    call_webhook: [
      { key: "url", label: t("p.ops.automations.param.webhookUrl"), type: "text" },
      { key: "secret", label: t("p.ops.automations.param.webhookSecret"), type: "text" },
    ],
  };

  const PARAM_FIELD_LABEL: Record<string, string> = {
    new_state: t("p.ops.automations.paramField.newState"),
    old_state: t("p.ops.automations.paramField.oldState"),
  };

  const {
    data: rules,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["automation-rules"],
    queryFn: automationsApi.list,
  });

  const { data: sprintsData } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
  });
  const sprints: Sprint[] = Array.isArray(sprintsData) ? sprintsData : [];

  const { data: logs } = useQuery({
    queryKey: ["automation-logs", expandedId],
    queryFn: () => automationsApi.logs(expandedId!),
    enabled: expandedId !== null,
  });

  const createMut = useMutation({
    mutationFn: automationsApi.create,
    onSuccess: () => {
      notify.success(t("p.ops.automations.created"));
      qc.invalidateQueries({ queryKey: ["automation-rules"] });
      setDialogOpen(false);
      resetForm();
    },
  });

  const editMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      automationsApi.update(id, data),
    onSuccess: () => {
      notify.success(t("p.ops.automations.updated"));
      qc.invalidateQueries({ queryKey: ["automation-rules"] });
      setDialogOpen(false);
      resetForm();
    },
    onError: () => notify.error(t("p.ops.automations.updateError")),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      automationsApi.update(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automation-rules"] }),
  });

  const testMut = useMutation({
    mutationFn: automationsApi.test,
    onSuccess: (data) => {
      notify.info(
        t("p.ops.automations.testResult", {
          results: JSON.stringify(data.results),
        }),
      );
    },
  });

  const deleteMut = useMutation({
    mutationFn: automationsApi.delete,
    onSuccess: () => {
      notify.info(t("p.ops.automations.deleted"));
      qc.invalidateQueries({ queryKey: ["automation-rules"] });
    },
  });

  const resetForm = () => {
    setForm({
      name: "",
      description: "",
      trigger: "task_blocked",
      action: "set_priority",
      schedule_hours: 24,
      enabled: true,
    });
    setConds([]);
    setParams({});
    setEditingId(null);
  };

  const openEdit = (rule: AutomationRule) => {
    setEditingId(rule.id);
    setForm({
      name: rule.name || "",
      description: rule.description || "",
      trigger: rule.trigger || "task_blocked",
      action: rule.action || "set_priority",
      schedule_hours: rule.schedule_hours ?? 24,
      enabled: rule.enabled,
    });
    setConds(
      (Array.isArray(rule.conditions) ? rule.conditions : []).map((c) => ({
        field: String(c.field ?? "new_state"),
        operator: String(c.operator ?? "equals"),
        value: String(c.value ?? ""),
      })),
    );
    const p: Record<string, string> = {};
    for (const [k, v] of Object.entries(rule.action_params || {})) p[k] = String(v ?? "");
    setParams(p);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    const conditions = conds
      .filter((c) => c.value.trim() !== "")
      .map((c) => ({ field: c.field, operator: c.operator, value: c.value }));
    const action_params: Record<string, unknown> = {};
    for (const f of ACTION_PARAMS[form.action] ?? []) {
      const raw = params[f.key];
      if (raw === undefined || raw === "") continue;
      action_params[f.key] = NUMERIC_PARAM_KEYS.has(f.key) ? Number(raw) : raw;
    }
    const payload: ApiPayload = {
      name: form.name,
      description: form.description,
      trigger: form.trigger,
      action: form.action,
      action_params,
      conditions,
      enabled: form.enabled,
    };
    if (form.trigger === "scheduled") payload.schedule_hours = form.schedule_hours;
    if (editingId !== null) {
      editMut.mutate({ id: editingId, data: payload });
    } else {
      createMut.mutate(payload);
    }
  };

  const ruleList = rules ?? [];

  return (
    <Box maxWidth={900} mx="auto">
      <PageHeader
        title={
          <>
            <Zap size={22} style={{ color: theme.palette.secondary.main, verticalAlign: "text-bottom", marginRight: 8 }} />
            {t("p.ops.automations.title")}
          </>
        }
        actions={
          <Button
            variant="contained"
            startIcon={<Plus size={18} />}
            onClick={() => {
              resetForm();
              setDialogOpen(true);
            }}
          >
            {t("p.ops.automations.new")}
          </Button>
        }
      />

      {isError && (
        <ErrorState
          title={t("p.ops.automations.loadError")}
          onRetry={() => void refetch()}
        />
      )}
      {isLoading ? (
        <TaskListSkeleton />
      ) : ruleList.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Zap size={48} color="text.disabled" />
          <Typography color="text.secondary" mt={1}>
            {t("p.ops.automations.empty")}
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={1.5}>
          {ruleList.map((rule: AutomationRule) => (
            <Paper key={rule.id} variant="outlined">
              <Stack
                direction="row"
                alignItems="center"
                spacing={1.5}
                sx={{ p: 2, cursor: "pointer" }}
                onClick={() => setExpandedId(expandedId === rule.id ? null : rule.id)}
              >
                {expandedId === rule.id ? (
                  <ChevronDown size={18} />
                ) : (
                  <ChevronRight size={18} />
                )}
                <Box flex={1}>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {rule.name}
                  </Typography>
                  <Stack
                    direction="row"
                    spacing={0.5}
                    mt={0.5}
                    flexWrap="wrap"
                    useFlexGap
                  >
                    <Chip
                      size="small"
                      label={t("p.ops.automations.triggerChip", {
                        trigger: TRIGGER_LABELS[rule.trigger] || rule.trigger,
                      })}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                    />
                    <Chip
                      size="small"
                      label={t("p.ops.automations.actionChip", {
                        action: ACTION_LABELS[rule.action] || rule.action,
                      })}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                      color="secondary"
                    />
                    <Chip
                      size="small"
                      label={t("p.ops.automations.executions", {
                        count: rule.trigger_count,
                      })}
                      sx={{ height: 20, fontSize: 10 }}
                      variant="outlined"
                    />
                  </Stack>
                </Box>
                <FormControlLabel
                  control={
                    <Switch
                      size="small"
                      checked={rule.enabled}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleMut.mutate({ id: rule.id, enabled: e.target.checked });
                      }}
                    />
                  }
                  label=""
                  onClick={(e) => e.stopPropagation()}
                />
                <Tooltip title={t("common.edit")}>
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      openEdit(rule);
                    }}
                  >
                    <Pencil size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip title={t("p.ops.automations.test")}>
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      testMut.mutate(rule.id);
                    }}
                  >
                    <Play size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip title={t("common.delete")}>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (
                        await confirm(
                          t("p.ops.automations.confirmDelete", {
                            name: rule.name,
                          }),
                          { confirmLabel: t("common.delete") },
                        )
                      )
                        deleteMut.mutate(rule.id);
                    }}
                  >
                    <Trash2 size={16} />
                  </IconButton>
                </Tooltip>
              </Stack>
              <Collapse in={expandedId === rule.id}>
                <Box sx={{ p: 2, pt: 0 }}>
                  {rule.description && (
                    <Typography variant="body2" color="text.secondary" mb={1}>
                      {rule.description}
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary">
                    {t("p.ops.automations.conditions", {
                      json: JSON.stringify(rule.conditions),
                    })}
                  </Typography>
                  <br />
                  <Typography variant="caption" color="text.secondary">
                    {t("p.ops.automations.params", {
                      json: JSON.stringify(rule.action_params),
                    })}
                  </Typography>
                  {rule.last_triggered_at && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      {t("p.ops.automations.lastRun", {
                        date: formatDateTime(rule.last_triggered_at),
                      })}
                    </Typography>
                  )}
                  {/* Logs */}
                  <Box mt={2}>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <History size={14} />
                      <Typography variant="subtitle2">
                        {t("p.ops.automations.history")}
                      </Typography>
                    </Stack>
                    {(logs ?? [])
                      .slice(0, 5)
                      .map((log: AutomationLog) => (
                        <Box key={log.id} sx={{ py: 0.5 }}>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Chip
                              size="small"
                              label={log.status}
                              sx={{
                                height: 16,
                                fontSize: 9,
                                bgcolor:
                                  log.status === "success"
                                    ? "success.main"
                                    : log.status === "failed"
                                      ? "error.main"
                                      : "grey.400",
                                color: "common.white",
                              }}
                            />
                            <Typography variant="caption" color="text.secondary">
                              {formatDateTime(log.created_at)}
                            </Typography>
                            {log.error_message && (
                              <Typography variant="caption" color="error.main">
                                {log.error_message}
                              </Typography>
                            )}
                          </Stack>
                        </Box>
                      ))}
                    {(!logs || logs.length === 0) && (
                      <Typography variant="caption" color="text.secondary">
                        {t("p.ops.automations.noRuns")}
                      </Typography>
                    )}
                  </Box>
                </Box>
              </Collapse>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Dialog de creación */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingId !== null
            ? t("p.ops.automations.editTitle")
            : t("p.ops.automations.newTitle")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("common.name")}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
              size="small"
            />
            <TextField
              label={t("p.ops.description")}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              fullWidth
              size="small"
              multiline
              rows={2}
            />
            {/* WHEN */}
            <Box>
              <Typography variant="overline" color="secondary.main" fontWeight={700}>
                {t("p.ops.automations.when")}
              </Typography>
              <Stack direction="row" spacing={1.5}>
                <FormControl fullWidth size="small">
                  <InputLabel>{t("p.ops.automations.event")}</InputLabel>
                  <Select
                    value={form.trigger}
                    label={t("p.ops.automations.event")}
                    onChange={(e) => setForm({ ...form, trigger: e.target.value })}
                  >
                    {Object.entries(TRIGGER_LABELS).map(([k, v]) => (
                      <MenuItem key={k} value={k}>
                        {v}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {form.trigger === "scheduled" && (
                  <TextField
                    size="small"
                    type="number"
                    label={t("p.ops.automations.everyNHours")}
                    value={form.schedule_hours}
                    onChange={(e) =>
                      setForm({ ...form, schedule_hours: Number(e.target.value) })
                    }
                    sx={{ width: 150 }}
                    inputProps={{ min: 1 }}
                  />
                )}
              </Stack>
            </Box>

            {/* IF: condiciones estructuradas */}
            <Box>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography
                  variant="overline"
                  color="secondary.main"
                  fontWeight={700}
                  sx={{ flex: 1 }}
                >
                  {t("p.ops.automations.if")}
                </Typography>
                <Button
                  size="small"
                  startIcon={<Plus size={14} />}
                  onClick={() =>
                    setConds([
                      ...conds,
                      { field: "new_state", operator: "equals", value: "" },
                    ])
                  }
                >
                  {t("p.ops.automations.addCondition")}
                </Button>
              </Stack>
              {conds.length === 0 && (
                <Typography variant="caption" color="text.secondary">
                  {t("p.ops.automations.noConditions")}
                </Typography>
              )}
              <Stack spacing={1} mt={conds.length ? 1 : 0}>
                {conds.map((c, i) => {
                  const isStateField = c.field === "new_state" || c.field === "old_state";
                  return (
                    <Stack key={i} direction="row" spacing={1} alignItems="center">
                      <FormControl size="small" sx={{ minWidth: 140 }}>
                        <Select
                          value={c.field}
                          onChange={(e) =>
                            setConds(
                              conds.map((x, j) =>
                                j === i ? { ...x, field: e.target.value } : x,
                              ),
                            )
                          }
                        >
                          {CONDITION_FIELDS.map((f) => (
                            <MenuItem key={f.value} value={f.value}>
                              {f.label}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControl size="small" sx={{ minWidth: 130 }}>
                        <Select
                          value={c.operator}
                          onChange={(e) =>
                            setConds(
                              conds.map((x, j) =>
                                j === i ? { ...x, operator: e.target.value } : x,
                              ),
                            )
                          }
                        >
                          {CONDITION_OPERATORS.map((o) => (
                            <MenuItem key={o.value} value={o.value}>
                              {o.label}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      {isStateField ? (
                        <FormControl size="small" sx={{ flex: 1 }}>
                          <Select
                            displayEmpty
                            value={c.value}
                            onChange={(e) =>
                              setConds(
                                conds.map((x, j) =>
                                  j === i ? { ...x, value: e.target.value } : x,
                                ),
                              )
                            }
                          >
                            <MenuItem value="" disabled>
                              {PARAM_FIELD_LABEL[c.field] ??
                                t("p.ops.automations.valueFallback")}
                            </MenuItem>
                            {Object.entries(STATE_LABELS).map(([k, v]) => (
                              <MenuItem key={k} value={k}>
                                {v}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      ) : (
                        <TextField
                          size="small"
                          placeholder={t("p.ops.value")}
                          fullWidth
                          value={c.value}
                          onChange={(e) =>
                            setConds(
                              conds.map((x, j) =>
                                j === i ? { ...x, value: e.target.value } : x,
                              ),
                            )
                          }
                        />
                      )}
                      <IconButton
                        size="small"
                        color="error"
                        aria-label={t("p.ops.automations.removeCondition")}
                        onClick={() => setConds(conds.filter((_, j) => j !== i))}
                      >
                        <Trash2 size={14} />
                      </IconButton>
                    </Stack>
                  );
                })}
              </Stack>
            </Box>

            {/* THEN: acción + parámetros tipados */}
            <Box>
              <Typography variant="overline" color="secondary.main" fontWeight={700}>
                {t("p.ops.automations.then")}
              </Typography>
              <FormControl fullWidth size="small">
                <InputLabel>{t("p.ops.automations.actionLabel")}</InputLabel>
                <Select
                  value={form.action}
                  label={t("p.ops.automations.actionLabel")}
                  onChange={(e) => {
                    setForm({ ...form, action: e.target.value });
                    setParams({});
                  }}
                >
                  {Object.entries(ACTION_LABELS).map(([k, v]) => (
                    <MenuItem key={k} value={k}>
                      {v}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Stack spacing={1.5} mt={1.5}>
                {(ACTION_PARAMS[form.action] ?? []).map((f) => {
                  const val = params[f.key] ?? "";
                  const setVal = (v: string) => setParams({ ...params, [f.key]: v });
                  if (f.type === "state") {
                    return (
                      <FormControl key={f.key} size="small" fullWidth>
                        <InputLabel>{f.label}</InputLabel>
                        <Select
                          value={val}
                          label={f.label}
                          onChange={(e) => setVal(e.target.value)}
                        >
                          {Object.entries(STATE_LABELS).map(([k, v]) => (
                            <MenuItem key={k} value={k}>
                              {v}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    );
                  }
                  if (f.type === "priority") {
                    return (
                      <FormControl key={f.key} size="small" fullWidth>
                        <InputLabel>{f.label}</InputLabel>
                        <Select
                          value={val}
                          label={f.label}
                          onChange={(e) => setVal(e.target.value)}
                        >
                          {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
                            <MenuItem key={k} value={k}>
                              {v}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    );
                  }
                  if (f.type === "sprint") {
                    return (
                      <FormControl key={f.key} size="small" fullWidth>
                        <InputLabel>{f.label}</InputLabel>
                        <Select
                          value={val}
                          label={f.label}
                          onChange={(e) => setVal(e.target.value)}
                        >
                          {sprints.map((s) => (
                            <MenuItem key={s.id} value={String(s.id)}>
                              {s.name}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    );
                  }
                  return (
                    <TextField
                      key={f.key}
                      size="small"
                      fullWidth
                      label={f.label}
                      type={f.type === "number" ? "number" : "text"}
                      value={val}
                      onChange={(e) => setVal(e.target.value)}
                    />
                  );
                })}
              </Stack>
            </Box>
            <FormControlLabel
              control={
                <Switch
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
              }
              label={t("p.ops.automations.enabled")}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={createMut.isPending || editMut.isPending}
          >
            {editingId !== null ? t("common.save") : t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}