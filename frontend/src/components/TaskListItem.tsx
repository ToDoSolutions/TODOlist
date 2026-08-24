import {
  Paper,
  Stack,
  Typography,
  Chip,
  IconButton,
  Box,
  Checkbox,
  Collapse,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  CircularProgress,
} from "@mui/material";
import {
  Calendar,
  Flag,
  Trash2,
  FolderInput,
  History,
  ChevronDown,
  ChevronRight,
  Target,
} from "lucide-react";
import { useState } from "react";
import { format, isPast, isToday } from "date-fns";
import { es } from "date-fns/locale";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi, sprintsApi } from "../api/resources";
import { notify } from "../notify";
import {
  Task,
  TaskState,
  Activity,
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
  const [showSprintSelect, setShowSprintSelect] = useState(false);
  const [showActivities, setShowActivities] = useState(false);

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

  const { data: sprints = [] } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
    enabled: showSprintSelect,
  });

  const moveToSprint = useMutation({
    mutationFn: (sprintId: number) => tasksApi.moveToSprint(task.id, sprintId),
    onSuccess: () => {
      notify.success("Tarea movida al sprint");
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setShowSprintSelect(false);
    },
    onError: () => notify.error("No se pudo mover la tarea"),
  });

  const { data: activitiesData, isLoading: activitiesLoading } = useQuery({
    queryKey: ["task-activities", task.id],
    queryFn: () => tasksApi.getActivities(task.id),
    enabled: !!showActivities,
  });
  const activities: Activity[] = Array.isArray(activitiesData) ? activitiesData : (activitiesData as any)?.results || [];

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
            {task.sprint_name && (
              <Chip
                size="small"
                variant="outlined"
                icon={<Target size={12} />}
                label={task.sprint_name}
                sx={{ height: 20, fontSize: 11, bgcolor: "primary.light", borderColor: "primary.main" }}
              />
            )}
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
            {(task.subtasks || []).length > 0 && (
              <Typography variant="caption" color="text.secondary">
                {(task.subtasks || []).filter((s) => s.is_done).length}/{(task.subtasks || []).length} subtareas
              </Typography>
            )}
          </Stack>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Tooltip title="Mover a sprint">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                setShowSprintSelect((v) => !v);
              }}
              sx={{ opacity: 0.5, "&:hover": { opacity: 1 } }}
            >
              <FolderInput size={16} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Actividad">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                setShowActivities((v) => !v);
              }}
              sx={{ opacity: 0.5, "&:hover": { opacity: 1 } }}
            >
              <History size={16} />
            </IconButton>
          </Tooltip>
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
      </Stack>

      {showSprintSelect && (
        <Box mt={1} onClick={(e) => e.stopPropagation()}>
          <FormControl size="small" fullWidth>
            <Select
              value=""
              displayEmpty
              onChange={(e) => {
                const val = e.target.value;
                if (val) moveToSprint.mutate(Number(val));
              }}
              renderValue={() =>
                moveToSprint.isPending
                  ? "Moviendo..."
                  : "Selecciona un sprint"
              }
            >
              {sprints.length === 0 && (
                <MenuItem disabled>No hay sprints</MenuItem>
              )}
              {sprints.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      )}

      <Collapse in={showActivities}>
        <Box mt={1} onClick={(e) => e.stopPropagation()}>
          <Stack direction="row" spacing={0.5} alignItems="center" mb={0.5}>
            {showActivities ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <Typography variant="caption" fontWeight={600}>
              Actividad
            </Typography>
          </Stack>
          {activitiesLoading ? (
            <CircularProgress size={16} />
          ) : activities && activities.length > 0 ? (
            <Stack spacing={0.5}>
              {activities.map((a: Activity) => (
                <Typography key={a.id} variant="caption" color="text.secondary">
                  {a.action} · {a.actor_email || "sistema"} ·{" "}
                  {format(new Date(a.created_at), "dd MMM HH:mm", { locale: es })}
                </Typography>
              ))}
            </Stack>
          ) : (
            <Typography variant="caption" color="text.secondary">
              Sin actividad registrada
            </Typography>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
