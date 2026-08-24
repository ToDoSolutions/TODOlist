import { useEffect, useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
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
} from "@mui/material";
import { Trash2, Plus, Send, Link2, Paperclip, Upload } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi, tagsApi, tasksApi, attachmentsApi } from "../api/resources";
import { notify } from "../notify";
import {
  Task,
  TaskInput,
  TaskPriority,
  TaskState,
  TaskRelation,
  RelationType,
  STATE_LABELS,
  PRIORITY_LABELS,
  RELATION_LABELS,
} from "../types";
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
  project: number | null;
  tags: number[];
  recurrence_enabled: boolean;
  recurrence_frequency: string;
  recurrence_interval: number;
}

export default function TaskDialog({
  open,
  task,
  defaultProjectId,
  onClose,
  onSaved,
}: Props) {
  const qc = useQueryClient();
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [serverError, setServerError] = useState("");
  const [relTaskId, setRelTaskId] = useState("");
  const [relType, setRelType] = useState<RelationType>("blocks");
  const [recurrenceEnabled, setRecurrenceEnabled] = useState(false);
  const [recFreq, setRecFreq] = useState("weekly");
  const [recInterval, setRecInterval] = useState(1);

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

  const { control, handleSubmit, reset, register } = useForm<FormValues>({
    defaultValues: {
      title: "",
      description: "",
      state: "pending",
      priority: 3,
      due_date: "",
      project: defaultProjectId ?? null,
      tags: [],
    },
  });

  useEffect(() => {
    if (open) {
      reset({
        title: task?.title || "",
        description: task?.description || "",
        state: task?.state || "pending",
        priority: task?.priority ?? 3,
        due_date: task?.due_date
          ? format(new Date(task.due_date), "yyyy-MM-dd'T'HH:mm")
          : "",
        project: task?.project ?? defaultProjectId ?? null,
        tags: task?.tags || [],
      });
      setServerError("");
      setRecurrenceEnabled(!!task?.recurrence);
      setRecFreq(task?.recurrence?.frequency || "weekly");
      setRecInterval(task?.recurrence?.interval || 1);
    }
  }, [open, task, defaultProjectId, reset]);

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      const payload: TaskInput = {
        title: values.title,
        description: values.description,
        state: values.state,
        priority: values.priority,
        due_date: values.due_date ? new Date(values.due_date).toISOString() : null,
        project: values.project,
        tags: values.tags,
        recurrence_data: recurrenceEnabled
          ? { frequency: recFreq, interval: recInterval }
          : undefined,
      };
      if (task) return tasksApi.update(task.id, payload);
      return tasksApi.create(payload);
    },
    onSuccess: () => {
      notify.success(task ? "Tarea actualizada" : "Tarea creada");
      onSaved();
    },
    onError: (e: any) => {
      const msg = e.response?.data?.title?.[0] || "No se pudo guardar.";
      setServerError(msg);
      notify.error(msg);
    },
  });

  const addSubtask = useMutation({
    mutationFn: (title: string) => tasksApi.addSubtask(task!.id, title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setSubtaskTitle("");
    },
  });

  const toggleSubtask = useMutation({
    mutationFn: ({ id, is_done }: { id: number; is_done: boolean }) =>
      tasksApi.updateSubtask(id, { is_done }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const removeSubtask = useMutation({
    mutationFn: (id: number) => tasksApi.removeSubtask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const addComment = useMutation({
    mutationFn: (body: string) => tasksApi.addComment(task!.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setCommentBody("");
    },
  });

  const removeTask = useMutation({
    mutationFn: () => tasksApi.remove(task!.id),
    onSuccess: () => {
      notify.success("Tarea eliminada");
      qc.invalidateQueries({ queryKey: ["tasks"] });
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

  const addRelation = useMutation({
    mutationFn: () =>
      tasksApi.addRelation(task!.id, Number(relTaskId), relType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task-relations", task?.id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setRelTaskId("");
      setRelType("blocks");
    },
    onError: (e: any) => {
      const msg = e.response?.data?.detail || "No se pudo añadir la relación.";
      notify.error(msg);
    },
  });

  const { data: attachmentsData } = useQuery({
    queryKey: ["task-attachments", task?.id],
    queryFn: () => attachmentsApi.list(task!.id),
    enabled: !!task?.id,
  });
  const attachments = attachmentsData || [];

  const uploadAttachment = useMutation({
    mutationFn: ({ taskId, file }: { taskId: number; file: File }) =>
      attachmentsApi.upload(taskId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task-attachments", task?.id] });
      notify.success("Archivo subido");
    },
    onError: () => notify.error("Error al subir archivo"),
  });

  const removeAttachment = useMutation({
    mutationFn: (id: number) => attachmentsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task-attachments", task?.id] }),
  });

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={handleSubmit((v) => save.mutate(v))}>
        <DialogTitle>{task ? "Editar tarea" : "Nueva tarea"}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2}>
            {serverError && <Alert severity="error">{serverError}</Alert>}
            <TextField
              label="Título"
              fullWidth
              required
              {...register("title")}
              defaultValue={task?.title}
            />
            <TextField
              label="Descripción"
              fullWidth
              multiline
              minRows={2}
              {...register("description")}
              defaultValue={task?.description}
            />
            <Stack direction="row" spacing={1.5}>
              <Controller
                control={control}
                name="state"
                render={({ field }) => (
                  <TextField select label="Estado" fullWidth {...field}>
                    {(Object.keys(STATE_LABELS) as TaskState[]).map((s) => (
                      <MenuItem key={s} value={s}>
                        {STATE_LABELS[s]}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
              />
              <Controller
                control={control}
                name="priority"
                render={({ field }) => (
                  <TextField select label="Prioridad" fullWidth {...field}>
                    {([0, 1, 2, 3, 4, 5] as TaskPriority[]).map((p) => (
                      <MenuItem key={p} value={p}>
                        {PRIORITY_LABELS[p]}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
              />
            </Stack>
            <Stack direction="row" spacing={1.5}>
              <Controller
                control={control}
                name="project"
                render={({ field }) => (
                  <TextField
                    select
                    label="Proyecto"
                    fullWidth
                    value={field.value ?? ""}
                    onChange={(e) =>
                      field.onChange(e.target.value === "" ? null : Number(e.target.value))
                    }
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
              <Controller
                control={control}
                name="due_date"
                render={({ field }) => (
                  <TextField
                    label="Fecha límite"
                    type="datetime-local"
                    fullWidth
                    InputLabelProps={{ shrink: true }}
                    {...field}
                  />
                )}
              />
            </Stack>
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
                          sx={{ bgcolor: t.color, color: "#fff" }}
                          {...props}
                        />
                      );
                    })
                  }
                  renderInput={(params) => (
                    <TextField {...params} label="Etiquetas" placeholder="Selecciona" />
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
                label="Tarea recurrente"
              />
              {recurrenceEnabled && (
                <>
                  <TextField
                    select
                    label="Frecuencia"
                    size="small"
                    value={recFreq}
                    onChange={(e) => setRecFreq(e.target.value)}
                    sx={{ minWidth: 140 }}
                  >
                    <MenuItem value="daily">Diaria</MenuItem>
                    <MenuItem value="weekly">Semanal</MenuItem>
                    <MenuItem value="monthly">Mensual</MenuItem>
                    <MenuItem value="yearly">Anual</MenuItem>
                  </TextField>
                  <TextField
                    label="Intervalo"
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

            {task && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" mb={1}>
                    Subtareas
                  </Typography>
                  <Stack direction="row" spacing={1} mb={1}>
                    <TextField
                      size="small"
                      fullWidth
                      label="Subtarea"
                      placeholder="Añadir subtarea…"
                      value={subtaskTitle}
                      onChange={(e) => setSubtaskTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && subtaskTitle.trim()) {
                          e.preventDefault();
                          addSubtask.mutate(subtaskTitle.trim());
                        }
                      }}
                    />
                    <Tooltip title="Añadir subtarea">
                      <IconButton
                        onClick={() => subtaskTitle.trim() && addSubtask.mutate(subtaskTitle.trim())}
                      >
                        <Plus size={18} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                  {(task.subtasks || []).map((s) => (
                    <Stack key={s.id} direction="row" alignItems="center" spacing={1}>
                      <Checkbox
                        size="small"
                        checked={s.is_done}
                        onChange={() => toggleSubtask.mutate({ id: s.id, is_done: !s.is_done })}
                      />
                      <Typography
                        sx={{
                          flex: 1,
                          textDecoration: s.is_done ? "line-through" : "none",
                          color: s.is_done ? "text.secondary" : "text.primary",
                        }}
                      >
                        {s.title}
                      </Typography>
                      <Tooltip title="Eliminar subtarea">
                        <IconButton size="small" onClick={() => removeSubtask.mutate(s.id)}>
                          <Trash2 size={14} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  ))}
                </Box>

                <Divider />
                <Box>
                  <Typography variant="subtitle2" mb={1}>
                    Comentarios
                  </Typography>
                  <Stack direction="row" spacing={1} mb={1}>
                    <TextField
                      size="small"
                      fullWidth
                      label="Comentario"
                      placeholder="Escribe un comentario…"
                      value={commentBody}
                      onChange={(e) => setCommentBody(e.target.value)}
                    />
                    <Tooltip title="Enviar comentario">
                      <IconButton
                        onClick={() => commentBody.trim() && addComment.mutate(commentBody.trim())}
                      >
                        <Send size={18} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                  {(task.comments || []).map((c) => (
                    <Box key={c.id} sx={{ mb: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        {c.author_email} · {format(new Date(c.created_at), "dd MMM HH:mm")}
                      </Typography>
                      <Typography variant="body2">{c.body}</Typography>
                    </Box>
                  ))}
                </Box>

                <Divider />
                <Box>
                  <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                    <Link2 size={18} />
                    <Typography variant="subtitle2">Dependencias</Typography>
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
                              label={RELATION_LABELS[r.relation_type]}
                              color={
                                r.relation_type === "blocks"
                                  ? "error"
                                  : r.relation_type === "depends_on"
                                  ? "warning"
                                  : "default"
                              }
                            />
                          </Stack>
                        );
                      })}
                    </Stack>
                  )}
                  <Stack direction="row" spacing={1} alignItems="center">
                    <TextField
                      size="small"
                      label="ID tarea"
                      type="number"
                      value={relTaskId}
                      onChange={(e) => setRelTaskId(e.target.value)}
                      sx={{ width: 120 }}
                    />
                    <FormControl size="small" sx={{ minWidth: 180 }}>
                      <InputLabel>Tipo</InputLabel>
                      <Select
                        label="Tipo"
                        value={relType}
                        onChange={(e) =>
                          setRelType(e.target.value as RelationType)
                        }
                      >
                        <MenuItem value="blocks">Bloquea</MenuItem>
                        <MenuItem value="depends_on">Bloqueada por</MenuItem>
                        <MenuItem value="related">Relacionada con</MenuItem>
                      </Select>
                    </FormControl>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<Plus size={16} />}
                      disabled={!relTaskId || addRelation.isPending}
                      onClick={() => addRelation.mutate()}
                    >
                      Añadir
                    </Button>
                  </Stack>
                </Box>

                <Divider />
                <Box>
                  <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                    <Paperclip size={18} />
                    <Typography variant="subtitle2">Adjuntos</Typography>
                  </Stack>
                  {attachments.length > 0 && (
                    <Stack spacing={0.5} mb={1}>
                      {attachments.map((a: any) => (
                        <Stack key={a.id} direction="row" alignItems="center" spacing={1}>
                          <Typography variant="body2" sx={{ flex: 1 }} noWrap>
                            {a.filename} ({(a.file_size / 1024).toFixed(1)} KB)
                          </Typography>
                          <Tooltip title="Eliminar adjunto">
                            <IconButton size="small" onClick={() => removeAttachment.mutate(a.id)}>
                              <Trash2 size={14} />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      ))}
                    </Stack>
                  )}
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<Upload size={16} />}
                    component="label"
                    disabled={uploadAttachment.isPending}
                  >
                    Subir archivo
                    <input
                      type="file"
                      hidden
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f && task) uploadAttachment.mutate({ taskId: task.id, file: f });
                        e.target.value = "";
                      }}
                    />
                  </Button>
                </Box>
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          {task && (
            <Button
              color="error"
              startIcon={<Trash2 size={16} />}
              onClick={() => removeTask.mutate()}
            >
              Eliminar
            </Button>
          )}
          <Box sx={{ flex: 1 }} />
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="contained" disabled={save.isPending}>
            Guardar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
