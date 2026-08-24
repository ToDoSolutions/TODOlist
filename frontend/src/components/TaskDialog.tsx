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
} from "@mui/material";
import { Trash2, Plus, Send } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi, tagsApi, tasksApi } from "../api/resources";
import { notify } from "../notify";
import {
  Task,
  TaskInput,
  TaskPriority,
  TaskState,
  STATE_LABELS,
  PRIORITY_LABELS,
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

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const { data: tags = [] } = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });

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
                    <IconButton
                      onClick={() => subtaskTitle.trim() && addSubtask.mutate(subtaskTitle.trim())}
                    >
                      <Plus size={18} />
                    </IconButton>
                  </Stack>
                  {task.subtasks.map((s) => (
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
                      <IconButton size="small" onClick={() => removeSubtask.mutate(s.id)}>
                        <Trash2 size={14} />
                      </IconButton>
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
                      placeholder="Escribe un comentario…"
                      value={commentBody}
                      onChange={(e) => setCommentBody(e.target.value)}
                    />
                    <IconButton
                      onClick={() => commentBody.trim() && addComment.mutate(commentBody.trim())}
                    >
                      <Send size={18} />
                    </IconButton>
                  </Stack>
                  {task.comments.map((c) => (
                    <Box key={c.id} sx={{ mb: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        {c.author_email} · {format(new Date(c.created_at), "dd MMM HH:mm")}
                      </Typography>
                      <Typography variant="body2">{c.body}</Typography>
                    </Box>
                  ))}
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
