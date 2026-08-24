import { useState } from "react";
import { Box, Paper, Typography, Stack, Chip } from "@mui/material";
import { Flag, Calendar } from "lucide-react";
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
  KANBAN_COLUMNS,
  STATE_LABELS,
  STATE_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
} from "../types";

interface Props {
  tasks: Task[];
  onEdit: (t: Task) => void;
}

interface KanbanCardProps {
  task: Task;
  onEdit: (t: Task) => void;
}

function KanbanCard({ task, onEdit }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: task.id,
    });

  const due = task.due_date ? new Date(task.due_date) : null;

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
        {due && (
          <Chip
            size="small"
            icon={<Calendar size={11} />}
            label={format(due, "dd MMM", { locale: es })}
            sx={{ height: 18, fontSize: 10 }}
            variant="outlined"
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
}: {
  state: TaskState;
  tasks: Task[];
  onEdit: (t: Task) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: state });

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      sx={{
        width: 280,
        flexShrink: 0,
        bgcolor: "action.hover",
        p: 1,
        minHeight: 400,
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
          sx={{ height: 18, fontSize: 11 }}
        />
      </Stack>
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
            Arrastra tareas aquí
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}

export default function KanbanBoard({ tasks, onEdit }: Props) {
  const qc = useQueryClient();
  const [activeTask, setActiveTask] = useState<Task | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
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

  const onDragStart = (e: DragStartEvent) => {
    const task = tasks.find((t) => t.id === e.active.id);
    setActiveTask(task || null);
  };

  const onDragEnd = (e: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = e;
    if (!over) return;
    const newState = over.id as TaskState;
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
      <Box sx={{ overflowX: "auto", pb: 1 }}>
        <Stack direction="row" spacing={1.5} sx={{ minWidth: "max-content" }}>
          {KANBAN_COLUMNS.map((col) => {
            const colTasks = tasks.filter((t) => t.state === col);
            return (
              <KanbanColumn
                key={col}
                state={col}
                tasks={colTasks}
                onEdit={onEdit}
              />
            );
          })}
        </Stack>
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
