import { useState, useMemo } from "react";
import {
  Box,
  Paper,
  Typography,
  Stack,
  Chip,
  TextField,
  InputAdornment,
  Menu,
  MenuItem,
  ListItemText,
  IconButton,
  Tooltip,
  Alert,
} from "@mui/material";
import {
  Flag,
  Calendar,
  Search,
  Layers,
  Plus,
  ChevronDown,
} from "lucide-react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCorners,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { tasksApi } from "../api/resources";
import { notify } from "../notify";
import {
  Task,
  TaskState,
  TaskType,
  KANBAN_COLUMNS,
  STATE_LABELS,
  STATE_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
  TYPE_LABELS,
  TYPE_COLORS,
} from "../types";

interface Props {
  tasks: Task[];
  onEdit: (t: Task) => void;
  onQuickAdd?: (state: TaskState) => void;
}

type SwimlaneMode = "none" | "priority" | "type" | "sprint";

const SWIMLANE_LABELS: Record<SwimlaneMode, string> = {
  none: "Sin swimlanes",
  priority: "Por prioridad",
  type: "Por tipo",
  sprint: "Por sprint",
};

// Límites WIP sugeridos por columna
const WIP_LIMITS: Partial<Record<TaskState, number>> = {
  in_progress: 5,
  review: 3,
  blocked: 3,
};

interface KanbanCardProps {
  task: Task;
  onEdit: (t: Task) => void;
}

function KanbanCard({ task, onEdit }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: task.id });

  const due = task.due_date ? new Date(task.due_date) : null;
  const isOverdue = due && due < new Date() && task.state !== "completed";

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      onClick={() => !isDragging && onEdit(task)}
      {...attributes}
      {...listeners}
      style={{
        transform: CSS.Translate.toString(transform),
        opacity: isDragging ? 0.4 : 1,
      }}
      sx={{
        p: 1.25,
        cursor: isDragging ? "grabbing" : "grab",
        "&:hover": { borderColor: "primary.main" },
        borderLeft: `3px solid ${PRIORITY_COLORS[task.priority]}`,
        touchAction: "none",
      }}
    >
      <Typography variant="body2" fontWeight={600} noWrap>
        {task.title}
      </Typography>
      <Stack
        direction="row"
        spacing={0.5}
        mt={0.5}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
      >
        <Chip
          size="small"
          icon={<Flag size={11} color={PRIORITY_COLORS[task.priority]} />}
          label={PRIORITY_LABELS[task.priority]}
          sx={{ height: 18, fontSize: 10 }}
          variant="outlined"
        />
        {task.task_type && task.task_type !== "task" && (
          <Chip
            size="small"
            label={TYPE_LABELS[task.task_type]}
            sx={{
              height: 18,
              fontSize: 10,
              bgcolor: TYPE_COLORS[task.task_type],
              color: "#fff",
            }}
          />
        )}
        {task.story_points && (
          <Chip
            size="small"
            label={`${task.story_points}pt`}
            sx={{ height: 18, fontSize: 10 }}
            variant="outlined"
          />
        )}
        {due && (
          <Chip
            size="small"
            icon={<Calendar size={11} />}
            label={format(due, "dd MMM", { locale: es })}
            sx={{
              height: 18,
              fontSize: 10,
              variant: "outlined",
              color: isOverdue ? "error.main" : "text.secondary",
              borderColor: isOverdue ? "error.main" : "divider",
            }}
          />
        )}
        {task.subtask_total > 0 && (
          <Chip
            size="small"
            label={`${task.subtask_done}/${task.subtask_total}`}
            sx={{ height: 18, fontSize: 10 }}
            variant="outlined"
          />
        )}
        {task.sprint_name && (
          <Chip
            size="small"
            label={task.sprint_name}
            sx={{ height: 18, fontSize: 10 }}
            variant="outlined"
            color="primary"
          />
        )}
      </Stack>
    </Paper>
  );
}

function KanbanColumn({
  state,
  tasks,
  onEdit,
  onQuickAdd,
  swimlaneKey,
}: {
  state: TaskState;
  tasks: Task[];
  onEdit: (t: Task) => void;
  onQuickAdd?: (state: TaskState) => void;
  swimlaneKey: string;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: swimlaneKey });
  const wipLimit = WIP_LIMITS[state];
  const isOverWip = wipLimit && tasks.length > wipLimit;

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      sx={{
        width: 260,
        flexShrink: 0,
        bgcolor: "action.hover",
        p: 1,
        minHeight: 200,
        borderColor: isOver ? "primary.main" : "divider",
        borderWidth: isOver ? 2 : 1,
        transition: "border-color 0.2s, border-width 0.2s",
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1} mb={1} px={0.5}>
        <Box
          sx={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            bgcolor: STATE_COLORS[state],
          }}
        />
        <Typography variant="subtitle2" fontWeight={700}>
          {STATE_LABELS[state]}
        </Typography>
        <Chip
          size="small"
          label={tasks.length}
          sx={{
            height: 18,
            fontSize: 11,
            color: isOverWip ? "error.main" : "text.secondary",
            borderColor: isOverWip ? "error.main" : "divider",
          }}
          variant="outlined"
        />
        {onQuickAdd && (
          <Tooltip title="Añadir tarea aquí">
            <IconButton size="small" onClick={() => onQuickAdd(state)} sx={{ ml: "auto", p: 0.25 }}>
              <Plus size={14} />
            </IconButton>
          </Tooltip>
        )}
      </Stack>
      {isOverWip && (
        <Alert severity="warning" sx={{ py: 0, mb: 0.5, fontSize: 10 }}>
          WIP {tasks.length}/{wipLimit}
        </Alert>
      )}
      <Stack spacing={1}>
        {tasks.map((t) => (
          <KanbanCard key={t.id} task={t} onEdit={onEdit} />
        ))}
        {tasks.length === 0 && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ p: 1, textAlign: "center" }}
          >
            Arrastra aquí
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}

export default function KanbanBoard({ tasks, onEdit, onQuickAdd }: Props) {
  const qc = useQueryClient();
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [swimlaneMode, setSwimlaneMode] = useState<SwimlaneMode>("none");
  const [search, setSearch] = useState("");
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  );

  const move = useMutation({
    mutationFn: ({ id, state }: { id: number; state: TaskState }) =>
      tasksApi.update(id, { state }),
    onSuccess: () => {
      notify.info("Tarea movida");
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  // Filtrar por búsqueda
  const filteredTasks = useMemo(() => {
    if (!search.trim()) return tasks;
    const q = search.toLowerCase();
    return tasks.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q)
    );
  }, [tasks, search]);

  // Agrupar por swimlane
  const swimlanes = useMemo(() => {
    if (swimlaneMode === "none") {
      return [{ key: "all", label: "", tasks: filteredTasks }];
    }
    const groups: Record<string, { label: string; tasks: Task[] }> = {};
    for (const t of filteredTasks) {
      let key = "sin_asignar";
      let label = "Sin asignar";
      if (swimlaneMode === "priority") {
        key = `p${t.priority}`;
        label = PRIORITY_LABELS[t.priority];
      } else if (swimlaneMode === "type") {
        key = t.task_type || "task";
        label = TYPE_LABELS[(t.task_type || "task") as TaskType] || "Tarea";
      } else if (swimlaneMode === "sprint") {
        key = t.sprint ? `s${t.sprint}` : "no_sprint";
        label = t.sprint_name || "Sin sprint";
      }
      if (!groups[key]) groups[key] = { label, tasks: [] };
      groups[key].tasks.push(t);
    }
    // Ordenar swimlanes de prioridad
    if (swimlaneMode === "priority") {
      const ordered: Record<string, { label: string; tasks: Task[] }> = {};
      for (let p = 0; p <= 5; p++) {
        const k = `p${p}`;
        if (groups[k]) ordered[k] = groups[k];
      }
      return Object.entries(ordered).map(([key, v]) => ({
        key,
        label: v.label,
        tasks: v.tasks,
      }));
    }
    return Object.entries(groups).map(([key, v]) => ({
      key,
      label: v.label,
      tasks: v.tasks,
    }));
  }, [filteredTasks, swimlaneMode]);

  const onDragStart = (e: DragStartEvent) => {
    const task = tasks.find((t) => t.id === e.active.id);
    setActiveTask(task || null);
  };

  const onDragEnd = (e: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = e;
    if (!over) return;
    // El droppable id es "swimlaneKey:state"
    const overId = String(over.id);
    const parts = overId.split(":");
    const newState = parts[parts.length - 1] as TaskState;
    const taskId = Number(active.id);
    const task = tasks.find((t) => t.id === taskId);
    if (task && task.state !== newState) {
      move.mutate({ id: taskId, state: newState });
    }
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      {/* Toolbar: búsqueda + swimlane selector */}
      <Stack direction="row" spacing={1} mb={2} alignItems="center">
        <TextField
          size="small"
          placeholder="Buscar en tablero..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search size={16} />
              </InputAdornment>
            ),
          }}
          sx={{ width: 250 }}
        />
        <IconButton
          size="small"
          onClick={(e) => setAnchorEl(e.currentTarget)}
          sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1 }}
        >
          <Layers size={16} />
          <Typography variant="caption" sx={{ ml: 0.5 }}>
            {SWIMLANE_LABELS[swimlaneMode]}
          </Typography>
          <ChevronDown size={14} />
        </IconButton>
        <Menu
          anchorEl={anchorEl}
          open={!!anchorEl}
          onClose={() => setAnchorEl(null)}
        >
          {(Object.keys(SWIMLANE_LABELS) as SwimlaneMode[]).map((mode) => (
            <MenuItem
              key={mode}
              selected={swimlaneMode === mode}
              onClick={() => {
                setSwimlaneMode(mode);
                setAnchorEl(null);
              }}
            >
              <ListItemText primary={SWIMLANE_LABELS[mode]} />
            </MenuItem>
          ))}
        </Menu>
      </Stack>

      {/* Swimlanes */}
      <Box sx={{ overflowX: "auto", pb: 1 }}>
        {swimlanes.map((lane) => (
          <Box key={lane.key} mb={swimlaneMode !== "none" ? 2 : 0}>
            {swimlaneMode !== "none" && (
              <Paper
                variant="outlined"
                sx={{
                  p: 0.5,
                  px: 1.5,
                  mb: 0.5,
                  bgcolor: "background.default",
                  position: "sticky",
                  left: 0,
                }}
              >
                <Typography variant="overline" fontWeight={700}>
                  {lane.label} ({lane.tasks.length})
                </Typography>
              </Paper>
            )}
            <Stack direction="row" spacing={1.5} sx={{ minWidth: "max-content" }}>
              {KANBAN_COLUMNS.map((col) => {
                const colTasks = lane.tasks.filter((t) => t.state === col);
                return (
                  <KanbanColumn
                    key={`${lane.key}:${col}`}
                    state={col}
                    tasks={colTasks}
                    onEdit={onEdit}
                    onQuickAdd={onQuickAdd}
                    swimlaneKey={`${lane.key}:${col}`}
                  />
                );
              })}
            </Stack>
          </Box>
        ))}
      </Box>

      <DragOverlay>
        {activeTask ? (
          <Paper
            variant="outlined"
            sx={{
              p: 1.25,
              cursor: "grabbing",
              borderLeft: `3px solid ${PRIORITY_COLORS[activeTask.priority]}`,
              boxShadow: 8,
              opacity: 0.9,
            }}
          >
            <Typography variant="body2" fontWeight={600} noWrap>
              {activeTask.title}
            </Typography>
          </Paper>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
