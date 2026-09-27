import { lazy, Suspense, useEffect, useState } from "react";
import {
  Drawer,
  Button,
  TextField,
  MenuItem,
  Box,
  Stack,
  Typography,
  Checkbox,
  IconButton,
  Chip,
  Divider,
  Autocomplete,
  Alert,
  Select,
  FormControl,
  InputLabel,
  Tooltip,
  FormControlLabel,
  Popover,
  Collapse,
  LinearProgress,
} from "@mui/material";
import {
  Trash2,
  Plus,
  Send,
  Link2,
  Paperclip,
  Upload,
  Download,
  Pencil,
  Check,
  X,
  AtSign,
  SmilePlus,
  Eye,
  EyeOff,
  Play,
  Square,
  BellOff,
  Timer,
  ExternalLink,
  Copy,
  ShieldCheck,
} from "lucide-react";

const EmojiPicker = lazy(() => import("emoji-picker-react"));
import { Controller, useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import "../i18n";
import { useDropzone } from "react-dropzone";
import imageCompression from "browser-image-compression";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  projectsApi,
  tagsApi,
  tasksApi,
  attachmentsApi,
  type ApiError,
} from "../api/resources";
import { taskXApi, useUndoDelete, type TaskX, type TaskXPatch } from "../api/featTask";
import { taskX2Api } from "../api/featTask2";
import { sectionsApi } from "../api/featSect";
import {
  approvalsApi,
  approverDirectory,
  type ApproverOption,
  type TaskApprovalFields,
  type ApprovalStatus,
} from "../api/featTask3";
import type { AttachmentItem } from "../types";
import { notify } from "../notify";
import { useConfirm } from "./ConfirmDialog";
import {
  Task,
  TaskInput,
  TaskPriority,
  TaskState,
  TaskRelation,
  RelationType,
} from "../types";
import { TASK_RELATION_I18N_KEYS, TASK_STATE_I18N_KEYS } from "../i18n/batchTaskUi";
import { format } from "date-fns";

interface Props {
  open: boolean;
  task: Task | null;
  defaultProjectId?: number;
  onClose: () => void;
  onSaved: () => void;
}

interface FormValues {
  title: string;
  description: string;
  state: TaskState;
  priority: TaskPriority;
  due_date: string;
  reminder_at: string;
  project: number | null;
  section: number | null;
  tags: number[];
  assignees: number[];
  recurrence_enabled: boolean;
  recurrence_frequency: string;
  recurrence_interval: number;
  is_milestone: boolean;
}

/** Campos de aprobación/tiempo registrado que el backend añade a Task. */
type Task3 = TaskX & TaskApprovalFields;

const APPROVAL_CHIP_COLOR: Record<ApprovalStatus, "warning" | "success" | "error"> = {
  pending: "warning",
  approved: "success",
  rejected: "error",
};

/** Formato h:mm para segundos registrados (logged_seconds del backend). */
function formatLoggedHMM(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}:${String(m).padStart(2, "0")}`;
}

/** Formato mm:ss o hh:mm:ss para el tiempo transcurrido del timer. */
function formatElapsed(ms: number): string {
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export default function TaskDialog({
  open,
  task,
  defaultProjectId,
  onClose,
  onSaved,
}: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const undoDelete = useUndoDelete();
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [serverError, setServerError] = useState("");
  const [relTaskId, setRelTaskId] = useState("");
  const [relType, setRelType] = useState<RelationType>("blocks");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [recurrenceEnabled, setRecurrenceEnabled] = useState(false);
  const [recFreq, setRecFreq] = useState("weekly");
  const [recInterval, setRecInterval] = useState(1);
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [emojiAnchor, setEmojiAnchor] = useState<{
    commentId: number;
    el: HTMLElement;
  } | null>(null);
  const [editCommentBody, setEditCommentBody] = useState("");
  const [editingSubtaskId, setEditingSubtaskId] = useState<number | null>(null);
  const [editSubtaskTitle, setEditSubtaskTitle] = useState("");

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];
  const { data: tagsData } = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });
  const tags = Array.isArray(tagsData) ? tagsData : [];

  const { control, handleSubmit, reset, register, setValue } = useForm<FormValues>({
    defaultValues: {
      title: "",
      description: "",
      state: "pending",
      priority: 3,
      due_date: "",
      reminder_at: "",
      project: defaultProjectId ?? null,
      section: null,
      tags: [],
      assignees: [],
      is_milestone: false,
    },
  });

  // Proyecto seleccionado en el formulario → fuente de usuarios asignables
  const formProject = useWatch({ control, name: "project" });

  // Secciones del proyecto seleccionado (para el selector "Sección").
  const { data: sections = [] } = useQuery({
    queryKey: ["project-sections", formProject],
    queryFn: () => sectionsApi.list(formProject!),
    enabled: open && !!formProject,
  });

  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    // Ajuste de estado durante render al cambiar `open` (patrón documentado
    // por React para resetear estado derivado de props)
    setPrevOpen(open);
    if (open) {
      setServerError("");
      setRecurrenceEnabled(!!task?.recurrence);
      setRecFreq(task?.recurrence?.frequency || "weekly");
      setRecInterval(task?.recurrence?.interval || 1);
    }
  }

  useEffect(() => {
    if (open) {
      const tx = task as TaskX | null;
      reset({
        title: task?.title || "",
        description: task?.description || "",
        state: task?.state || "pending",
        priority: task?.priority ?? 3,
        due_date: task?.due_date
          ? format(new Date(task.due_date), "yyyy-MM-dd'T'HH:mm")
          : "",
        reminder_at: tx?.reminder_at
          ? format(new Date(tx.reminder_at), "yyyy-MM-dd'T'HH:mm")
          : "",
        project: task?.project ?? defaultProjectId ?? null,
        section: task?.section ?? null,
        tags: task?.tags || [],
        assignees: tx?.assignees ?? (tx?.assignees_detail ?? []).map((u) => u.id),
        is_milestone: task?.is_milestone ?? false,
      });
    }
  }, [open, task, defaultProjectId, reset]);

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      // `section` es writable en create/PATCH según el contrato nuevo;
      // TaskXPatch (featTask.ts, otro batch) aún no lo declara.
      const payload: TaskXPatch & {
        section?: number | null;
        is_milestone?: boolean;
      } = {
        title: values.title,
        description: values.description,
        state: values.state,
        priority: values.priority,
        is_milestone: values.is_milestone,
        due_date: values.due_date ? new Date(values.due_date).toISOString() : null,
        reminder_at: values.reminder_at
          ? new Date(values.reminder_at).toISOString()
          : null,
        project: values.project,
        section: values.project ? values.section : null,
        tags: values.tags,
        assignees: values.assignees,
        recurrence_data: recurrenceEnabled
          ? { frequency: recFreq, interval: recInterval }
          : undefined,
      };
      if (task) return taskXApi.update(task.id, payload);
      return tasksApi.create(payload as TaskInput);
    },
    onSuccess: () => {
      notify.success(task ? t("p.task.taskUpdated") : t("p.task.taskCreated"));
      onSaved();
    },
    onError: (e: ApiError) => {
      const msg =
        (e.response?.data?.title as string[] | undefined)?.[0] || t("p.task.saveError");
      setServerError(msg);
      notify.error(msg);
    },
  });

  const addSubtask = useMutation({
    mutationFn: (title: string) => tasksApi.addSubtask(task!.id, title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      setSubtaskTitle("");
    },
  });

  const toggleSubtask = useMutation({
    mutationFn: ({ id, is_done }: { id: number; is_done: boolean }) =>
      tasksApi.updateSubtask(id, { is_done }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
    },
  });

  const removeSubtask = useMutation({
    mutationFn: (id: number) => tasksApi.removeSubtask(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
    },
  });

  const addComment = useMutation({
    mutationFn: (body: string) => tasksApi.addComment(task!.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      setCommentBody("");
    },
  });

  const updateComment = useMutation({
    mutationFn: ({ id, body }: { id: number; body: string }) =>
      tasksApi.updateComment(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      setEditingCommentId(null);
      notify.success(t("p.task.commentUpdated"));
    },
    onError: () => notify.error(t("p.task.commentUpdateError")),
  });

  const removeComment = useMutation({
    mutationFn: (id: number) => tasksApi.removeComment(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      notify.success(t("p.task.commentDeleted"));
    },
    onError: () => notify.error(t("p.task.commentDeleteError")),
  });

  const editSubtask = useMutation({
    mutationFn: ({ id, title }: { id: number; title: string }) =>
      tasksApi.updateSubtask(id, { title }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      setEditingSubtaskId(null);
      notify.success(t("p.task.subtaskUpdated"));
    },
    onError: () => notify.error(t("p.task.subtaskUpdateError")),
  });

  const removeRelation = useMutation({
    mutationFn: (id: number) => tasksApi.removeRelation(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task-relations", task?.id] });
      notify.success(t("p.task.relationDeleted"));
    },
    onError: () => notify.error(t("p.task.relationDeleteError")),
  });

  const removeTask = useMutation({
    mutationFn: () => tasksApi.remove(task!.id),
    onSuccess: () => {
      // Snackbar con "Deshacer": recrea la tarea desde el snapshot
      undoDelete((displayTask ?? task) as TaskX);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      onSaved();
    },
  });

  const { data: relationsData } = useQuery({
    queryKey: ["task-relations", task?.id],
    queryFn: () => tasksApi.getRelations(task!.id),
    enabled: !!task?.id,
  });
  const relations: TaskRelation[] = Array.isArray(relationsData) ? relationsData : [];

  // Detalle fresco de la tarea: el prop `task` es un snapshot de la lista
  // y queda obsoleto tras mutaciones (comentarios, subtareas, reacciones).
  const { data: freshTask } = useQuery({
    queryKey: ["task", task?.id],
    queryFn: () => tasksApi.get(task!.id),
    enabled: !!task?.id,
    initialData: task ?? undefined,
  });
  const displayTask = freshTask ?? task;
  const displayTaskX = displayTask as TaskX | null;

  // --- Feature extras: asignados, watchers, temporizador ---
  // Usuarios asignables = miembros del proyecto seleccionado en el form.
  // approverDirectory devuelve el mismo shape (AssigneeDetail) + el flag
  // user_out_of_office opcional para el badge OOO del selector de aprobador.
  const { data: assignableUsers } = useQuery({
    queryKey: ["project-members", formProject],
    queryFn: () => approverDirectory(formProject!),
    enabled: open && !!formProject,
  });
  // Opciones = miembros del proyecto ∪ assignees_detail (para no perder
  // chips de asignados que ya no son miembros visibles del proyecto).
  const assigneeOptions = (() => {
    const map = new Map<number, ApproverOption>();
    for (const u of assignableUsers ?? []) map.set(u.id, u);
    for (const u of displayTaskX?.assignees_detail ?? [])
      if (!map.has(u.id)) map.set(u.id, u);
    return [...map.values()];
  })();

  // --- Aprobaciones: solicitar / decidir (approve|reject) ---
  const displayTask3 = displayTaskX as Task3 | null;
  const latestApproval = displayTask3?.approvals?.length
    ? displayTask3.approvals[displayTask3.approvals.length - 1]
    : undefined;
  const [approvalMode, setApprovalMode] = useState<
    "request" | "approve" | "reject" | null
  >(null);
  const [approver, setApprover] = useState<ApproverOption | null>(null);
  const [approvalNote, setApprovalNote] = useState("");
  const resetApprovalForm = () => {
    setApprovalMode(null);
    setApprover(null);
    setApprovalNote("");
  };
  const invalidateTask = () => {
    qc.invalidateQueries({ queryKey: ["task", task?.id] });
    qc.invalidateQueries({ queryKey: ["tasks"] });
  };
  const requestApprovalMut = useMutation({
    mutationFn: () =>
      approvalsApi.requestApproval(task!.id, {
        approver: approver!.id,
        note: approvalNote.trim() || undefined,
      }),
    onSuccess: () => {
      notify.success(t("p.taskx.approval.requested"));
      invalidateTask();
      resetApprovalForm();
    },
    onError: () => notify.error(t("p.taskx.approval.error")),
  });
  const decideApprovalMut = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      decision === "approve"
        ? approvalsApi.approve(task!.id, approvalNote.trim() || undefined)
        : approvalsApi.reject(task!.id, approvalNote.trim() || undefined),
    onSuccess: (_d, decision) => {
      notify.success(
        t(
          decision === "approve"
            ? "p.taskx.approval.approved"
            : "p.taskx.approval.rejected",
        ),
      );
      invalidateTask();
      resetApprovalForm();
    },
    onError: () => notify.error(t("p.taskx.approval.error")),
  });

  const toggleWatch = useMutation({
    mutationFn: () =>
      displayTaskX?.is_watching ? taskXApi.unwatch(task!.id) : taskXApi.watch(task!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.taskx.watch.error")),
  });

  // Estado del temporizador (solo mientras el diálogo está abierto;
  // polling suave cada 30 s por si se inició desde otro cliente).
  const { data: timerStatus } = useQuery({
    queryKey: ["task-timer", task?.id],
    queryFn: () => taskXApi.timerStatus(task!.id),
    enabled: open && !!task?.id,
    refetchInterval: 30_000,
  });
  const timerMut = useMutation({
    mutationFn: (action: "start" | "stop") =>
      action === "start" ? taskXApi.timerStart(task!.id) : taskXApi.timerStop(task!.id),
    onSuccess: (_d, action) => {
      qc.invalidateQueries({ queryKey: ["task-timer", task?.id] });
      notify.success(
        action === "start" ? t("p.taskx.timer.running") : t("p.taskx.timer.stopped"),
      );
    },
    onError: (_e, action) =>
      notify.error(
        action === "start" ? t("p.taskx.timer.startError") : t("p.taskx.timer.stopError"),
      ),
  });
  // Tick 1 s mientras corre para pintar el tiempo transcurrido
  const [nowTs, setNowTs] = useState(() => Date.now());
  useEffect(() => {
    if (!open || !timerStatus?.running || !timerStatus.started_at) return;
    const id = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [open, timerStatus?.running, timerStatus?.started_at]);
  const elapsedMs =
    timerStatus?.running && timerStatus.started_at
      ? Math.max(0, nowTs - new Date(timerStatus.started_at).getTime())
      : 0;

  // Duplicar tarea (POST /tasks/{id}/duplicate/ clona campos/tags/assignees).
  const duplicateMut = useMutation({
    mutationFn: () => taskX2Api.duplicate(task!.id),
    onSuccess: () => {
      notify.success(t("p.taskx.duplicate.done"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => notify.error(t("p.taskx.duplicate.error")),
  });

  const addRelation = useMutation({
    mutationFn: () => tasksApi.addRelation(task!.id, Number(relTaskId), relType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task-relations", task?.id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
      setRelTaskId("");
      setRelType("blocks");
    },
    onError: (e: ApiError) => {
      const msg = e.response?.data?.detail || t("p.task.relationAddError");
      notify.error(msg);
    },
  });

  const reactComment = useMutation({
    mutationFn: ({ id, emoji }: { id: number; emoji: string }) =>
      tasksApi.reactComment(id, emoji),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["task", task?.id] });
    },
  });

  const { data: attachmentsData } = useQuery({
    queryKey: ["task-attachments", task?.id],
    queryFn: () => attachmentsApi.list(task!.id),
    enabled: !!task?.id,
  });
  const attachments = attachmentsData || [];

  const uploadAttachment = useMutation({
    mutationFn: async ({ taskId, file }: { taskId: number; file: File }) => {
      // Comprimir imágenes en cliente antes de subir (ahorro de ancho
      // de banda y almacenamiento; los demás tipos pasan intactos).
      if (file.type.startsWith("image/") && file.size > 300_000) {
        const compressed = await imageCompression(file, {
          maxSizeMB: 0.5,
          maxWidthOrHeight: 1920,
          useWebWorker: true,
        });
        return attachmentsApi.upload(taskId, compressed);
      }
      return attachmentsApi.upload(taskId, file);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task-attachments", task?.id] });
      notify.success(t("p.task.fileUploaded"));
    },
    onError: () => notify.error(t("p.task.fileUploadError")),
  });

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => {
      const f = files[0];
      if (f && task) uploadAttachment.mutate({ taskId: task.id, file: f });
    },
    disabled: uploadAttachment.isPending || !task,
  });

  const removeAttachment = useMutation({
    mutationFn: (id: number) => attachmentsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task-attachments", task?.id] }),
  });

  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const addLink = useMutation({
    mutationFn: (url: string) => attachmentsApi.createLink(task!.id, url.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task-attachments", task?.id] });
      setLinkUrl("");
      setLinkOpen(false);
    },
    onError: () => notify.error(t("p.taskx.attachLink.error")),
  });

  return (
    <Drawer
      open={open}
      onClose={onClose}
      anchor="right"
      PaperProps={{
        sx: { width: { xs: "100%", sm: 560, lg: 780 }, maxWidth: "100vw" },
      }}
    >
      <Box
        component="form"
        onSubmit={handleSubmit((v) => save.mutate(v))}
        sx={{ display: "flex", flexDirection: "column", height: "100%" }}
      >
        <Stack
          direction="row"
          alignItems="center"
          sx={{ px: 2.5, py: 1.5, borderBottom: 1, borderColor: "divider" }}
        >
          <Typography variant="h6" fontWeight={700} sx={{ flex: 1 }} noWrap>
            {task
              ? `${displayTask?.ref ?? `#${task.id}`} · ${task.title}`
              : t("p.task.newTask")}
          </Typography>
          <IconButton onClick={onClose} aria-label={t("common.close")}>
            <X size={18} />
          </IconButton>
        </Stack>
        <Box
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            overflow: "hidden",
          }}
        >
          {/* Columna principal: contenido y actividad */}
          <Box sx={{ flex: 1, overflow: "auto", p: 2.5, minWidth: 0 }}>
            <Stack spacing={2}>
              {serverError && <Alert severity="error">{serverError}</Alert>}
              <TextField
                label={t("p.task.title")}
                fullWidth
                required
                {...register("title")}
                defaultValue={task?.title}
              />
              <TextField
                label={t("p.task.description")}
                fullWidth
                multiline
                minRows={2}
                {...register("description")}
                defaultValue={task?.description}
              />
              {/* Divulgación progresiva: etiquetas y recurrencia van bajo
                "Más opciones" para reducir la densidad del formulario base */}
              <Button
                size="small"
                variant="text"
                onClick={() => setShowAdvanced((v) => !v)}
                endIcon={showAdvanced ? <X size={14} /> : <Plus size={14} />}
                sx={{ alignSelf: "flex-start", textTransform: "none" }}
                aria-expanded={showAdvanced}
              >
                {showAdvanced ? t("p.task.lessOptions") : t("p.task.moreOptions")}
              </Button>
              <Collapse in={showAdvanced}>
                <Stack spacing={2}>
                  <Controller
                    control={control}
                    name="tags"
                    render={({ field }) => (
                      <Autocomplete
                        multiple
                        options={tags}
                        getOptionLabel={(t) => t.name}
                        value={tags.filter((t) => field.value.includes(t.id))}
                        onChange={(_, v) => field.onChange(v.map((t) => t.id))}
                        renderTags={(value, getTagProps) =>
                          value.map((t, idx) => {
                            const { key, ...props } = getTagProps({ index: idx });
                            return (
                              <Chip
                                key={key}
                                size="small"
                                label={t.name}
                                sx={{ bgcolor: t.color, color: "common.white" }}
                                {...props}
                              />
                            );
                          })
                        }
                        renderInput={(params) => (
                          <TextField
                            {...params}
                            label={t("p.task.tags")}
                            placeholder={t("p.task.selectPlaceholder")}
                          />
                        )}
                      />
                    )}
                  />

                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={recurrenceEnabled}
                          onChange={(e) => setRecurrenceEnabled(e.target.checked)}
                        />
                      }
                      label={t("p.task.recurringTask")}
                    />
                    <Controller
                      control={control}
                      name="is_milestone"
                      render={({ field }) => (
                        <FormControlLabel
                          control={
                            <Checkbox checked={field.value} onChange={field.onChange} />
                          }
                          label={t("p.taskx.milestoneLabel")}
                        />
                      )}
                    />
                    {recurrenceEnabled && (
                      <>
                        <TextField
                          select
                          label={t("p.task.frequency")}
                          size="small"
                          value={recFreq}
                          onChange={(e) => setRecFreq(e.target.value)}
                          sx={{ minWidth: 140 }}
                        >
                          <MenuItem value="daily">{t("p.task.freq.daily")}</MenuItem>
                          <MenuItem value="weekly">{t("p.task.freq.weekly")}</MenuItem>
                          <MenuItem value="monthly">{t("p.task.freq.monthly")}</MenuItem>
                          <MenuItem value="yearly">{t("p.task.freq.yearly")}</MenuItem>
                        </TextField>
                        <TextField
                          label={t("p.task.interval")}
                          type="number"
                          size="small"
                          value={recInterval}
                          onChange={(e) => setRecInterval(Number(e.target.value))}
                          sx={{ width: 100 }}
                          inputProps={{ min: 1 }}
                        />
                      </>
                    )}
                  </Stack>
                </Stack>
              </Collapse>

              {task && (
                <>
                  <Divider />
                  <Box>
                    <Typography variant="subtitle2" mb={1}>
                      {t("p.task.subtasks")}
                    </Typography>
                    <Stack direction="row" spacing={1} mb={1}>
                      <TextField
                        size="small"
                        fullWidth
                        label={t("p.task.subtask")}
                        placeholder={t("p.task.addSubtaskPlaceholder")}
                        value={subtaskTitle}
                        onChange={(e) => setSubtaskTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && subtaskTitle.trim()) {
                            e.preventDefault();
                            addSubtask.mutate(subtaskTitle.trim());
                          }
                        }}
                      />
                      <Tooltip title={t("p.task.addSubtask")}>
                        <IconButton
                          onClick={() =>
                            subtaskTitle.trim() && addSubtask.mutate(subtaskTitle.trim())
                          }
                        >
                          <Plus size={18} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                    {(displayTask?.subtasks || []).map((s) => (
                      <Stack key={s.id} direction="row" alignItems="center" spacing={1}>
                        <Checkbox
                          size="small"
                          checked={s.is_done}
                          onChange={() =>
                            toggleSubtask.mutate({ id: s.id, is_done: !s.is_done })
                          }
                        />
                        {editingSubtaskId === s.id ? (
                          <>
                            <TextField
                              size="small"
                              fullWidth
                              value={editSubtaskTitle}
                              onChange={(e) => setEditSubtaskTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && editSubtaskTitle.trim()) {
                                  editSubtask.mutate({
                                    id: s.id,
                                    title: editSubtaskTitle.trim(),
                                  });
                                }
                              }}
                            />
                            <Tooltip title={t("common.save")}>
                              <IconButton
                                size="small"
                                onClick={() =>
                                  editSubtaskTitle.trim() &&
                                  editSubtask.mutate({
                                    id: s.id,
                                    title: editSubtaskTitle.trim(),
                                  })
                                }
                              >
                                <Check size={14} />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title={t("common.cancel")}>
                              <IconButton
                                size="small"
                                onClick={() => setEditingSubtaskId(null)}
                              >
                                <X size={14} />
                              </IconButton>
                            </Tooltip>
                          </>
                        ) : (
                          <>
                            <Typography
                              sx={{
                                flex: 1,
                                textDecoration: s.is_done ? "line-through" : "none",
                                color: s.is_done ? "text.secondary" : "text.primary",
                              }}
                            >
                              {s.title}
                            </Typography>
                            <Tooltip title={t("p.task.editSubtask")}>
                              <IconButton
                                size="small"
                                onClick={() => {
                                  setEditingSubtaskId(s.id);
                                  setEditSubtaskTitle(s.title);
                                }}
                              >
                                <Pencil size={14} />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title={t("p.task.deleteSubtask")}>
                              <IconButton
                                size="small"
                                onClick={async () => {
                                  if (await confirm(t("p.task.confirmDeleteSubtask")))
                                    removeSubtask.mutate(s.id);
                                }}
                              >
                                <Trash2 size={14} />
                              </IconButton>
                            </Tooltip>
                          </>
                        )}
                      </Stack>
                    ))}
                  </Box>

                  <Divider />
                  <Box>
                    <Typography variant="subtitle2" mb={1}>
                      {t("p.task.comments")}
                    </Typography>
                    <Stack direction="row" spacing={1} mb={1}>
                      <TextField
                        size="small"
                        fullWidth
                        multiline
                        minRows={1}
                        maxRows={6}
                        label={t("p.task.comment")}
                        placeholder={t("p.task.commentPlaceholder")}
                        value={commentBody}
                        onChange={(e) => setCommentBody(e.target.value)}
                      />
                      <Tooltip title={t("p.task.sendComment")}>
                        <IconButton
                          onClick={() =>
                            commentBody.trim() && addComment.mutate(commentBody.trim())
                          }
                        >
                          <Send size={18} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                    {(displayTask?.comments || []).map((c) => (
                      <Box key={c.id} sx={{ mb: 1 }}>
                        <Stack direction="row" alignItems="center" spacing={0.5}>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ flex: 1 }}
                          >
                            {c.author_email} ·{" "}
                            {format(new Date(c.created_at), "dd MMM HH:mm")}
                          </Typography>
                          <Tooltip title={t("common.edit")}>
                            <IconButton
                              size="small"
                              onClick={() => {
                                setEditingCommentId(c.id);
                                setEditCommentBody(c.body);
                              }}
                            >
                              <Pencil size={12} />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t("common.delete")}>
                            <IconButton
                              size="small"
                              onClick={async () => {
                                if (await confirm(t("p.task.confirmDeleteComment")))
                                  removeComment.mutate(c.id);
                              }}
                            >
                              <Trash2 size={12} />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                        {editingCommentId === c.id ? (
                          <Stack direction="row" spacing={1} alignItems="center">
                            <TextField
                              size="small"
                              fullWidth
                              multiline
                              value={editCommentBody}
                              onChange={(e) => setEditCommentBody(e.target.value)}
                            />
                            <Tooltip title={t("common.save")}>
                              <IconButton
                                size="small"
                                onClick={() =>
                                  editCommentBody.trim() &&
                                  updateComment.mutate({
                                    id: c.id,
                                    body: editCommentBody.trim(),
                                  })
                                }
                              >
                                <Check size={14} />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title={t("common.cancel")}>
                              <IconButton
                                size="small"
                                onClick={() => setEditingCommentId(null)}
                              >
                                <X size={14} />
                              </IconButton>
                            </Tooltip>
                          </Stack>
                        ) : (
                          <>
                            <Box
                              sx={{
                                "& p": { m: 0, mb: 0.5 },
                                "& p:last-child": { mb: 0 },
                                fontSize: "0.875rem",
                              }}
                            >
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {c.body}
                              </ReactMarkdown>
                            </Box>
                            <Stack
                              direction="row"
                              spacing={0.5}
                              alignItems="center"
                              flexWrap="wrap"
                              sx={{ mt: 0.5 }}
                            >
                              {Object.entries(c.reactions || {}).map(([emoji, users]) => (
                                <Chip
                                  key={emoji}
                                  size="small"
                                  label={`${emoji} ${users.length}`}
                                  variant="outlined"
                                  onClick={() => reactComment.mutate({ id: c.id, emoji })}
                                  sx={{ height: 22, cursor: "pointer" }}
                                />
                              ))}
                              {/@[\w.]+/.test(c.body) && (
                                <Chip
                                  size="small"
                                  icon={<AtSign size={12} />}
                                  label={t("p.task.mention")}
                                  variant="outlined"
                                  sx={{ height: 20 }}
                                />
                              )}
                              <Tooltip title={t("p.task.addReaction")}>
                                <IconButton
                                  size="small"
                                  sx={{ width: 22, height: 22, minWidth: 0 }}
                                  onClick={(e) =>
                                    setEmojiAnchor({
                                      commentId: c.id,
                                      el: e.currentTarget,
                                    })
                                  }
                                >
                                  <SmilePlus size={13} />
                                </IconButton>
                              </Tooltip>
                            </Stack>
                          </>
                        )}
                      </Box>
                    ))}
                  </Box>

                  <Divider />
                  <Box>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <Link2 size={18} />
                      <Typography variant="subtitle2">
                        {t("p.task.dependencies")}
                      </Typography>
                    </Stack>
                    {relations.length > 0 && (
                      <Stack spacing={1} mb={1}>
                        {relations.map((r) => {
                          const isSource = r.source === task.id;
                          const relatedTitle = isSource ? r.target_title : r.source_title;
                          const relatedId = isSource ? r.target : r.source;
                          return (
                            <Stack
                              key={r.id}
                              direction="row"
                              alignItems="center"
                              spacing={1}
                            >
                              <Typography variant="body2" sx={{ flex: 1 }}>
                                #{relatedId} · {relatedTitle}
                              </Typography>
                              <Chip
                                size="small"
                                label={t(TASK_RELATION_I18N_KEYS[r.relation_type])}
                                color={
                                  r.relation_type === "blocks"
                                    ? "error"
                                    : r.relation_type === "depends_on"
                                      ? "warning"
                                      : "default"
                                }
                              />
                              <Tooltip title={t("p.task.deleteRelation")}>
                                <IconButton
                                  size="small"
                                  onClick={async () => {
                                    if (await confirm(t("p.task.confirmDeleteRelation")))
                                      removeRelation.mutate(r.id);
                                  }}
                                >
                                  <Trash2 size={14} />
                                </IconButton>
                              </Tooltip>
                            </Stack>
                          );
                        })}
                      </Stack>
                    )}
                    <Stack direction="row" spacing={1} alignItems="center">
                      <TextField
                        size="small"
                        label={t("p.task.taskId")}
                        type="number"
                        value={relTaskId}
                        onChange={(e) => setRelTaskId(e.target.value)}
                        sx={{ width: 120 }}
                      />
                      <FormControl size="small" sx={{ minWidth: 180 }}>
                        <InputLabel>{t("p.task.relationType")}</InputLabel>
                        <Select
                          label={t("p.task.relationType")}
                          value={relType}
                          onChange={(e) => setRelType(e.target.value as RelationType)}
                        >
                          <MenuItem value="blocks">
                            {t("p.task.relation.blocks")}
                          </MenuItem>
                          <MenuItem value="depends_on">
                            {t("p.task.relation.blockedBy")}
                          </MenuItem>
                          <MenuItem value="related">
                            {t("p.task.relation.related")}
                          </MenuItem>
                        </Select>
                      </FormControl>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Plus size={16} />}
                        disabled={!relTaskId || addRelation.isPending}
                        onClick={() => addRelation.mutate()}
                      >
                        {t("p.task.add")}
                      </Button>
                    </Stack>
                  </Box>

                  <Divider />
                  <Box>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <Paperclip size={18} />
                      <Typography variant="subtitle2">
                        {t("p.task.attachments")}
                      </Typography>
                    </Stack>
                    {attachments.length > 0 && (
                      <Stack spacing={0.5} mb={1}>
                        {attachments.map((a: AttachmentItem) => (
                          <Stack
                            key={a.id}
                            direction="row"
                            alignItems="center"
                            spacing={1}
                          >
                            <Typography variant="body2" sx={{ flex: 1 }} noWrap>
                              {a.filename}
                              {!a.external_url &&
                                ` (${((a.file_size ?? 0) / 1024).toFixed(1)} KB)`}
                            </Typography>
                            {a.external_url ? (
                              <Tooltip title={t("p.taskx.attachLink.open")}>
                                <IconButton
                                  size="small"
                                  component="a"
                                  href={a.external_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  <ExternalLink size={14} />
                                </IconButton>
                              </Tooltip>
                            ) : (
                              <Tooltip title={t("p.task.download")}>
                                <IconButton
                                  size="small"
                                  component="a"
                                  href={`/api/attachments/${a.id}/download/`}
                                  download={a.filename}
                                  rel="noopener noreferrer"
                                >
                                  <Download size={14} />
                                </IconButton>
                              </Tooltip>
                            )}
                            <Tooltip title={t("p.task.deleteAttachment")}>
                              <IconButton
                                size="small"
                                onClick={async () => {
                                  if (await confirm("¿Eliminar este adjunto?"))
                                    removeAttachment.mutate(a.id);
                                }}
                              >
                                <Trash2 size={14} />
                              </IconButton>
                            </Tooltip>
                          </Stack>
                        ))}
                      </Stack>
                    )}
                    <Box
                      {...getRootProps()}
                      sx={{
                        border: 2,
                        borderStyle: "dashed",
                        borderColor: isDragActive ? "primary.main" : "divider",
                        borderRadius: 2,
                        px: 2,
                        py: 1.5,
                        textAlign: "center",
                        cursor: "pointer",
                        transition: "border-color 0.2s",
                        bgcolor: isDragActive ? "action.hover" : "transparent",
                        "&:hover": { borderColor: "primary.light" },
                      }}
                    >
                      <input {...getInputProps()} />
                      <Stack
                        direction="row"
                        spacing={1}
                        justifyContent="center"
                        alignItems="center"
                      >
                        <Upload size={16} />
                        <Typography variant="body2" color="text.secondary">
                          {uploadAttachment.isPending
                            ? "Subiendo..."
                            : isDragActive
                              ? "Suelta el archivo aquí"
                              : "Arrastra un archivo o haz clic para subir"}
                        </Typography>
                      </Stack>
                    </Box>
                    {linkOpen ? (
                      <Stack direction="row" spacing={1} mt={1}>
                        <TextField
                          size="small"
                          fullWidth
                          placeholder={t("p.taskx.attachLink.placeholder")}
                          value={linkUrl}
                          onChange={(e) => setLinkUrl(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && addLink.mutate(linkUrl)}
                        />
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={!linkUrl.trim() || addLink.isPending}
                          onClick={() => addLink.mutate(linkUrl)}
                        >
                          {t("p.taskx.attachLink.add")}
                        </Button>
                      </Stack>
                    ) : (
                      <Button
                        size="small"
                        startIcon={<Link2 size={14} />}
                        sx={{ mt: 0.5, alignSelf: "flex-start" }}
                        onClick={() => setLinkOpen(true)}
                      >
                        {t("p.taskx.attachLink.add")}
                      </Button>
                    )}
                  </Box>
                </>
              )}
            </Stack>
          </Box>
          {/* Panel lateral de propiedades */}
          <Box
            sx={{
              width: { xs: "100%", md: 250 },
              flexShrink: 0,
              borderTop: { xs: 1, md: 0 },
              borderLeft: { md: 1 },
              borderColor: "divider",
              bgcolor: "action.hover",
              p: 2,
              overflow: "auto",
            }}
          >
            <Typography variant="overline" color="text.secondary" fontWeight={700}>
              Propiedades
            </Typography>
            <Stack spacing={2} mt={1}>
              <Controller
                control={control}
                name="state"
                render={({ field }) => (
                  <TextField select size="small" label="Estado" fullWidth {...field}>
                    {(Object.keys(TASK_STATE_I18N_KEYS) as TaskState[]).map((s) => (
                      <MenuItem key={s} value={s}>
                        {t(TASK_STATE_I18N_KEYS[s])}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
              />
              <Controller
                control={control}
                name="priority"
                render={({ field }) => (
                  <TextField select size="small" label="Prioridad" fullWidth {...field}>
                    {([0, 1, 2, 3, 4, 5] as TaskPriority[]).map((p) => (
                      <MenuItem key={p} value={p}>
                        {t(`task.priority.p${p}`)}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
              />
              <Controller
                control={control}
                name="project"
                render={({ field }) => (
                  <TextField
                    select
                    size="small"
                    label="Proyecto"
                    fullWidth
                    value={field.value ?? ""}
                    onChange={(e) => {
                      field.onChange(
                        e.target.value === "" ? null : Number(e.target.value),
                      );
                      // Las secciones son por proyecto: al cambiar de proyecto
                      // la sección elegida deja de ser válida.
                      setValue("section", null);
                    }}
                    onBlur={field.onBlur}
                    name={field.name}
                    ref={field.ref}
                  >
                    <MenuItem value="">Bandeja de entrada</MenuItem>
                    {projects.map((p) => (
                      <MenuItem key={p.id} value={p.id}>
                        {p.name}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
              />
              {/* Sección del proyecto (PATCH task.section); solo con proyecto */}
              {formProject != null && (
                <Controller
                  control={control}
                  name="section"
                  render={({ field }) => (
                    <TextField
                      select
                      size="small"
                      label={t("p.taskx.sections.field")}
                      fullWidth
                      value={field.value ?? ""}
                      onChange={(e) =>
                        field.onChange(
                          e.target.value === "" ? null : Number(e.target.value),
                        )
                      }
                      onBlur={field.onBlur}
                      name={field.name}
                      ref={field.ref}
                    >
                      <MenuItem value="">{t("p.taskx.sections.noSection")}</MenuItem>
                      {sections.map((s) => (
                        <MenuItem key={s.id} value={s.id}>
                          {s.name}
                        </MenuItem>
                      ))}
                    </TextField>
                  )}
                />
              )}
              <Controller
                control={control}
                name="due_date"
                render={({ field }) => (
                  <TextField
                    size="small"
                    label="Fecha límite"
                    type="datetime-local"
                    fullWidth
                    InputLabelProps={{ shrink: true }}
                    {...field}
                  />
                )}
              />
              <Controller
                control={control}
                name="reminder_at"
                render={({ field }) => (
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <TextField
                      size="small"
                      label={t("p.taskx.reminder.label")}
                      type="datetime-local"
                      fullWidth
                      InputLabelProps={{ shrink: true }}
                      name={field.name}
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      inputRef={field.ref}
                    />
                    <Tooltip title={t("p.taskx.reminder.clear")}>
                      <span>
                        <IconButton
                          size="small"
                          aria-label={t("p.taskx.reminder.clear")}
                          disabled={!field.value}
                          onClick={() => field.onChange("")}
                        >
                          <BellOff size={16} />
                        </IconButton>
                      </span>
                    </Tooltip>
                  </Stack>
                )}
              />
              <Controller
                control={control}
                name="assignees"
                render={({ field }) => (
                  <Autocomplete
                    multiple
                    size="small"
                    options={assigneeOptions}
                    getOptionLabel={(u) => u.username || u.email}
                    isOptionEqualToValue={(a, b) => a.id === b.id}
                    value={assigneeOptions.filter((u) => field.value.includes(u.id))}
                    onChange={(_, v) => field.onChange(v.map((u) => u.id))}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label={t("p.taskx.assignees.label")}
                        placeholder={t("p.taskx.assignees.placeholder")}
                      />
                    )}
                  />
                )}
              />
              {task && (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Tooltip
                    title={
                      displayTaskX?.is_watching
                        ? t("p.taskx.watch.unwatch")
                        : t("p.taskx.watch.watch")
                    }
                  >
                    <IconButton
                      size="small"
                      aria-label={
                        displayTaskX?.is_watching
                          ? t("p.taskx.watch.unwatch")
                          : t("p.taskx.watch.watch")
                      }
                      onClick={() => toggleWatch.mutate()}
                      disabled={toggleWatch.isPending}
                      color={displayTaskX?.is_watching ? "primary" : "default"}
                    >
                      {displayTaskX?.is_watching ? (
                        <Eye size={16} />
                      ) : (
                        <EyeOff size={16} />
                      )}
                    </IconButton>
                  </Tooltip>
                  <Typography variant="caption" color="text.secondary">
                    {t("p.taskx.watch.watchers", {
                      count: displayTaskX?.watchers?.length ?? 0,
                    })}
                  </Typography>
                </Stack>
              )}
              {task && (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip
                    size="small"
                    icon={<Timer size={14} />}
                    label={
                      timerStatus?.running
                        ? t("p.taskx.timer.elapsed", {
                            time: formatElapsed(elapsedMs),
                          })
                        : t("p.taskx.timer.stopped")
                    }
                    color={timerStatus?.running ? "error" : "default"}
                    variant={timerStatus?.running ? "filled" : "outlined"}
                  />
                  <Tooltip
                    title={
                      timerStatus?.running
                        ? t("p.taskx.timer.stop")
                        : t("p.taskx.timer.start")
                    }
                  >
                    <span>
                      <IconButton
                        size="small"
                        aria-label={
                          timerStatus?.running
                            ? t("p.taskx.timer.stop")
                            : t("p.taskx.timer.start")
                        }
                        disabled={timerMut.isPending}
                        onClick={() =>
                          timerMut.mutate(timerStatus?.running ? "stop" : "start")
                        }
                      >
                        {timerStatus?.running ? <Square size={16} /> : <Play size={16} />}
                      </IconButton>
                    </span>
                  </Tooltip>
                </Stack>
              )}
              {task && (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Tooltip title={t("p.taskx.duplicate.label")}>
                    <span>
                      <IconButton
                        size="small"
                        aria-label={t("p.taskx.duplicate.label")}
                        disabled={duplicateMut.isPending}
                        onClick={() => duplicateMut.mutate()}
                      >
                        <Copy size={16} />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Typography variant="caption" color="text.secondary">
                    {t("p.taskx.duplicate.label")}
                  </Typography>
                </Stack>
              )}
              {displayTask?.sprint_name && (
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Sprint
                  </Typography>
                  <Typography variant="body2">{displayTask.sprint_name}</Typography>
                </Box>
              )}
              {displayTask?.assignee_email && (
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Responsable
                  </Typography>
                  <Typography variant="body2">{displayTask.assignee_email}</Typography>
                </Box>
              )}
              {/* Tiempo registrado vs estimado (logged_seconds del backend) */}
              {task && (displayTask?.estimate_hours ?? 0) > 0 && (
                <Box>
                  <Typography variant="caption" color="text.secondary" fontWeight={700}>
                    {t("p.taskx.logged.title")}
                  </Typography>
                  {(() => {
                    const estimateH = displayTask?.estimate_hours ?? 0;
                    const loggedS = displayTask3?.logged_seconds ?? 0;
                    const pct =
                      estimateH > 0
                        ? Math.min(100, (loggedS / 3600 / estimateH) * 100)
                        : 0;
                    const over = loggedS / 3600 > estimateH;
                    return (
                      <>
                        <LinearProgress
                          variant="determinate"
                          value={pct}
                          color={over ? "error" : "primary"}
                          sx={{ mt: 0.5, height: 6, borderRadius: 1 }}
                        />
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          display="block"
                          mt={0.5}
                        >
                          {t("p.taskx.logged.vs", {
                            logged: formatLoggedHMM(loggedS),
                            estimate: estimateH,
                          })}
                        </Typography>
                      </>
                    );
                  })()}
                </Box>
              )}
              {/* Aprobación: estado de la última solicitud + acciones */}
              {task && (
                <Box>
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <ShieldCheck size={14} />
                    <Typography variant="caption" color="text.secondary" fontWeight={700}>
                      {t("p.taskx.approval.title")}
                    </Typography>
                  </Stack>
                  {latestApproval && (
                    <Box mt={0.5}>
                      <Stack
                        direction="row"
                        spacing={0.5}
                        alignItems="center"
                        flexWrap="wrap"
                        useFlexGap
                      >
                        <Chip
                          size="small"
                          color={APPROVAL_CHIP_COLOR[latestApproval.status]}
                          label={t(`p.taskx.approval.status.${latestApproval.status}`)}
                        />
                        {latestApproval.approver_email && (
                          <Typography variant="caption" color="text.secondary">
                            {latestApproval.approver_email}
                          </Typography>
                        )}
                      </Stack>
                      {latestApproval.decision_note && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          display="block"
                          mt={0.5}
                        >
                          {latestApproval.decision_note}
                        </Typography>
                      )}
                    </Box>
                  )}
                  {displayTask3?.pending_approval_for_me ? (
                    approvalMode === "approve" || approvalMode === "reject" ? (
                      <Stack spacing={1} mt={1}>
                        <TextField
                          size="small"
                          label={t("p.taskx.approval.noteOptional")}
                          value={approvalNote}
                          onChange={(e) => setApprovalNote(e.target.value)}
                          multiline
                          minRows={1}
                        />
                        <Stack direction="row" spacing={1}>
                          <Button
                            size="small"
                            variant="contained"
                            color={approvalMode === "approve" ? "success" : "error"}
                            disabled={decideApprovalMut.isPending}
                            onClick={() => decideApprovalMut.mutate(approvalMode)}
                          >
                            {t(
                              approvalMode === "approve"
                                ? "p.taskx.approval.approve"
                                : "p.taskx.approval.reject",
                            )}
                          </Button>
                          <Button size="small" onClick={resetApprovalForm}>
                            {t("common.cancel")}
                          </Button>
                        </Stack>
                      </Stack>
                    ) : (
                      <Stack direction="row" spacing={1} mt={1}>
                        <Button
                          size="small"
                          variant="contained"
                          color="success"
                          startIcon={<Check size={14} />}
                          onClick={() => setApprovalMode("approve")}
                        >
                          {t("p.taskx.approval.approve")}
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          startIcon={<X size={14} />}
                          onClick={() => setApprovalMode("reject")}
                        >
                          {t("p.taskx.approval.reject")}
                        </Button>
                      </Stack>
                    )
                  ) : approvalMode === "request" ? (
                    <Stack spacing={1} mt={1}>
                      <Autocomplete
                        size="small"
                        options={assignableUsers ?? []}
                        getOptionLabel={(u) => u.username || u.email}
                        isOptionEqualToValue={(a, b) => a.id === b.id}
                        value={approver}
                        onChange={(_, v) => setApprover(v)}
                        renderOption={(props, option) => (
                          <li {...props} key={option.id}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <span>{option.username || option.email}</span>
                              {option.out_of_office && (
                                <Chip
                                  size="small"
                                  color="warning"
                                  variant="outlined"
                                  label={t("p.taskx.approval.ooo")}
                                />
                              )}
                            </Stack>
                          </li>
                        )}
                        renderInput={(params) => (
                          <TextField
                            {...params}
                            label={t("p.taskx.approval.approverLabel")}
                          />
                        )}
                      />
                      <TextField
                        size="small"
                        label={t("p.taskx.approval.noteOptional")}
                        value={approvalNote}
                        onChange={(e) => setApprovalNote(e.target.value)}
                        multiline
                        minRows={1}
                      />
                      <Stack direction="row" spacing={1}>
                        <Button
                          size="small"
                          variant="contained"
                          disabled={!approver || requestApprovalMut.isPending}
                          onClick={() => requestApprovalMut.mutate()}
                        >
                          {t("p.taskx.approval.requestSubmit")}
                        </Button>
                        <Button size="small" onClick={resetApprovalForm}>
                          {t("common.cancel")}
                        </Button>
                      </Stack>
                    </Stack>
                  ) : (
                    <Button
                      size="small"
                      variant="outlined"
                      sx={{ mt: 0.5 }}
                      onClick={() => setApprovalMode("request")}
                    >
                      {t("p.taskx.approval.request")}
                    </Button>
                  )}
                </Box>
              )}
            </Stack>
          </Box>
        </Box>
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ px: 2.5, py: 1.5, borderTop: 1, borderColor: "divider" }}
        >
          {task && (
            <Button
              color="error"
              startIcon={<Trash2 size={16} />}
              onClick={async () => {
                if (
                  await confirm("¿Eliminar esta tarea y todos sus datos asociados?", {
                    confirmLabel: "Eliminar tarea",
                  })
                )
                  removeTask.mutate();
              }}
            >
              Eliminar
            </Button>
          )}
          <Box sx={{ flex: 1 }} />
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="contained" disabled={save.isPending}>
            Guardar
          </Button>
        </Stack>
      </Box>
      <Popover
        open={!!emojiAnchor}
        anchorEl={emojiAnchor?.el}
        onClose={() => setEmojiAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        <Suspense fallback={<Box sx={{ p: 3 }}>Cargando…</Box>}>
          <EmojiPicker
            height={360}
            width={320}
            searchPlaceHolder="Buscar emoji"
            onEmojiClick={(e) => {
              if (emojiAnchor) {
                reactComment.mutate({ id: emojiAnchor.commentId, emoji: e.emoji });
              }
              setEmojiAnchor(null);
            }}
          />
        </Suspense>
      </Popover>
    </Drawer>
  );
}
