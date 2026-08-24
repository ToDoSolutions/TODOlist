import {
  Paper,
  Stack,
  Typography,
  Chip,
  IconButton,
  Box,
  Checkbox,
} from "@mui/material";
import { Calendar, Flag, Trash2 } from "lucide-react";
import { format, isPast, isToday } from "date-fns";
import { es } from "date-fns/locale";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "../api/resources";
import { notify } from "../notify";
import {
  Task,
  TaskState,
  STATE_LABELS,
  STATE_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
} from "../types";

interface Props {
  task: Task;
  onEdit: (t: Task) => void;
}

export default function TaskListItem({ task, onEdit }: Props) {
  const qc = useQueryClient();

  const toggleComplete = useMutation({
    mutationFn: () =>
      tasksApi.update(task.id, {
        state:
          task.state === "completed"
            ? ("pending" as TaskState)
            : ("completed" as TaskState),
      }),
    onSuccess: () => {
      notify.success(task.state === "completed" ? "Tarea reabierta" : "Tarea completada");
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const deleteTask = useMutation({
    mutationFn: () => tasksApi.remove(task.id),
    onSuccess: () => {
      notify.success("Tarea eliminada");
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => notify.error("No se pudo eliminar la tarea"),
  });

  const due = task.due_date ? new Date(task.due_date) : null;
  const overdue =
    due && task.state !== "completed" && isPast(due) && !isToday(due);

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        cursor: "pointer",
        "&:hover": { borderColor: "primary.main" },
        opacity: task.state === "completed" ? 0.6 : 1,
      }}
      onClick={() => onEdit(task)}
    >
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        <Checkbox
          checked={task.state === "completed"}
          onChange={(e) => {
            e.stopPropagation();
            toggleComplete.mutate();
          }}
          onClick={(e) => e.stopPropagation()}
          sx={{ p: 0.5 }}
        />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            fontWeight={600}
            sx={{
              textDecoration: task.state === "completed" ? "line-through" : "none",
            }}
            noWrap
          >
            {task.title}
          </Typography>
          {task.description && (
            <Typography variant="body2" color="text.secondary" noWrap>
              {task.description}
            </Typography>
          )}
          <Stack direction="row" spacing={0.5} mt={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              label={STATE_LABELS[task.state]}
              sx={{
                bgcolor: STATE_COLORS[task.state],
                color: "#fff",
                height: 20,
                fontSize: 11,
              }}
            />
            <Chip
              size="small"
              variant="outlined"
              icon={<Flag size={12} color={PRIORITY_COLORS[task.priority]} />}
              label={PRIORITY_LABELS[task.priority]}
              sx={{ height: 20, fontSize: 11 }}
            />
            {due && (
              <Chip
                size="small"
                variant="outlined"
                icon={<Calendar size={12} />}
                label={format(due, "dd MMM", { locale: es })}
                color={overdue ? "error" : "default"}
                sx={{ height: 20, fontSize: 11 }}
              />
            )}
            {task.subtasks.length > 0 && (
              <Typography variant="caption" color="text.secondary">
                {task.subtasks.filter((s) => s.is_done).length}/{task.subtasks.length} subtareas
              </Typography>
            )}
          </Stack>
        </Box>
        <IconButton
          size="small"
          color="error"
          onClick={(e) => {
            e.stopPropagation();
            if (confirm("¿Eliminar esta tarea?")) deleteTask.mutate();
          }}
          sx={{ opacity: 0.5, "&:hover": { opacity: 1 } }}
        >
          <Trash2 size={16} />
        </IconButton>
      </Stack>
    </Paper>
  );
}
