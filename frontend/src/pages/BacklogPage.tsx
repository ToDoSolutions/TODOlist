import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Stack,
  Paper,
  Chip,
  TextField,
  InputAdornment,
  Button,
  IconButton,
  Menu,
  MenuItem,
  Divider,
  Alert,
} from "@mui/material";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
  closestCorners,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { Plus, Search, ArrowDownToLine } from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { PriorityBadge } from "../components/ui/badges";
import { tasksApi, sprintsApi, type Sprint } from "../api/resources";
import { notify } from "../notify";
import { useProject } from "../auth/ProjectContext";
import type { Task } from "../types";
import { TASK_STATE_I18N_KEYS } from "../i18n/batchTaskUi";
import { formatDate } from "../lib/dates";

/**
 * Backlog: planificación de sprint arrastrando tareas entre contenedores.
 * Capacidad visible en SP, crear inline, "Mover a sprint" alternativo.
 */
export default function BacklogPage() {
  const { t } = useTranslation();
  const { project: ctxProject } = useProject();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [moveAnchor, setMoveAnchor] = useState<{ task: Task; el: HTMLElement } | null>(
    null,
  );

  const { data: tasksData } = useQuery({
    queryKey: ["tasks", { project: ctxProject?.id }],
    queryFn: () => tasksApi.list(ctxProject?.id ? { project: ctxProject.id } : {}),
  });
  const tasks = useMemo(() => (Array.isArray(tasksData) ? tasksData : []), [tasksData]);

  const { data: sprintsData } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
  });
  const sprints: Sprint[] = (Array.isArray(sprintsData) ? sprintsData : []).filter(
    (s) =>
      s.state !== "closed" &&
      (!ctxProject || s.project === ctxProject.id || s.project === null),
  );

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  const assignToSprint = useMutation({
    mutationFn: ({ taskId, sprintId }: { taskId: number; sprintId: number | null }) =>
      sprintId === null
        ? tasksApi.update(taskId, { sprint: null })
        : tasksApi.update(taskId, { sprint: sprintId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      notify.info(t("p.work.backlog.taskUpdated"));
    },
    onError: () => notify.error(t("p.work.backlog.moveError")),
  });

  const createInline = useMutation({
    mutationFn: (title: string) =>
      tasksApi.create({ title, project: ctxProject?.id ?? null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setNewTitle("");
      notify.success(t("p.work.backlog.created"));
    },
  });

  const filtered = useMemo(() => {
    if (!search.trim()) return tasks;
    const q = search.toLowerCase();
    return tasks.filter((task) => task.title.toLowerCase().includes(q));
  }, [tasks, search]);

  const backlogTasks = filtered.filter(
    (task) =>
      !task.sprint && !["completed", "cancelled", "archived"].includes(task.state),
  );
  const unestimated = backlogTasks.filter((task) => !task.story_points).length;

  const onDragEnd = (e: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = e;
    if (!over) return;
    const taskId = Number(active.id);
    const overId = String(over.id);
    const sprintId = overId === "backlog" ? null : Number(overId.replace("sprint-", ""));
    const task = tasks.find((task) => task.id === taskId);
    if (task && task.sprint !== sprintId) {
      assignToSprint.mutate({ taskId, sprintId });
    }
  };

  return (
    <Box>
      <PageHeader
        title={t("p.shell.backlog")}
        description={t("p.work.backlog.desc")}
        breadcrumbs={[{ label: t("section.planning") }, { label: t("p.shell.backlog") }]}
        actions={
          <Button variant="outlined" onClick={() => window.open("/app/sprints", "_self")}>
            {t("p.work.backlog.manageSprints")}
          </Button>
        }
      />

      {unestimated > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {t("p.work.backlog.unestimated", { count: unestimated })}
        </Alert>
      )}

      <TextField
        size="small"
        placeholder={t("p.work.backlog.searchPlaceholder")}
        inputProps={{ "aria-label": t("p.work.backlog.searchPlaceholder") }}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2, minWidth: 260 }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <Search size={16} />
            </InputAdornment>
          ),
        }}
      />

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={(e) =>
          setActiveTask(tasks.find((task) => task.id === e.active.id) ?? null)
        }
        onDragEnd={onDragEnd}
      >
        <Stack spacing={2}>
          {sprints.map((s) => (
            <SprintLane
              key={s.id}
              sprint={s}
              laneTasks={filtered.filter((task) => task.sprint === s.id)}
              onMoveTask={(task, el) => setMoveAnchor({ task, el })}
            />
          ))}
          <SprintLane
            sprint={null}
            laneTasks={backlogTasks}
            newTitle={newTitle}
            onNewTitle={setNewTitle}
            onCreateInline={(title) => createInline.mutate(title)}
            onMoveTask={(task, el) => setMoveAnchor({ task, el })}
          />
        </Stack>
        <DragOverlay>
          {activeTask && (
            <Paper variant="outlined" sx={{ p: 1.25, boxShadow: 8, opacity: 0.9 }}>
              <Typography variant="body2" fontWeight={600}>
                {activeTask.title}
              </Typography>
            </Paper>
          )}
        </DragOverlay>
      </DndContext>

      {/* "Mover a" — alternativa accesible al drag */}
      <Menu
        anchorEl={moveAnchor?.el}
        open={!!moveAnchor}
        onClose={() => setMoveAnchor(null)}
      >
        <MenuItem disabled>{t("p.work.backlog.moveTo")}</MenuItem>
        <MenuItem
          onClick={() => {
            if (moveAnchor)
              assignToSprint.mutate({ taskId: moveAnchor.task.id, sprintId: null });
            setMoveAnchor(null);
          }}
        >
          {t("p.shell.backlog")}
        </MenuItem>
        {sprints.map((s) => (
          <MenuItem
            key={s.id}
            onClick={() => {
              if (moveAnchor)
                assignToSprint.mutate({ taskId: moveAnchor.task.id, sprintId: s.id });
              setMoveAnchor(null);
            }}
          >
            {s.name}
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}

interface SprintLaneProps {
  sprint: Sprint | null;
  laneTasks: Task[];
  /** Solo en la lane de backlog: input inline de creación */
  newTitle?: string;
  onNewTitle?: (v: string) => void;
  onCreateInline?: (title: string) => void;
  onMoveTask: (task: Task, el: HTMLElement) => void;
}

function SprintLane({
  sprint,
  laneTasks,
  newTitle,
  onNewTitle,
  onCreateInline,
  onMoveTask,
}: SprintLaneProps) {
  const { t } = useTranslation();
  const laneId = sprint ? `sprint-${sprint.id}` : "backlog";
  const totalSp = laneTasks.reduce((acc, task) => acc + (task.story_points ?? 0), 0);
  const { setNodeRef, isOver } = useDroppable({ id: laneId });

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      sx={{
        p: 1.5,
        bgcolor: isOver ? "action.hover" : "background.paper",
        transition: "background-color 0.15s",
        minHeight: 120,
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1} mb={1}>
        <Typography variant="subtitle2" fontWeight={700} flex={1}>
          {sprint ? sprint.name.toUpperCase() : t("p.shell.backlog").toUpperCase()}
          {sprint && (
            <Typography component="span" variant="caption" color="text.secondary" ml={1}>
              {formatDate(sprint.start_date)} – {formatDate(sprint.end_date)}
            </Typography>
          )}
        </Typography>
        <Chip
          size="small"
          variant="outlined"
          label={t("p.work.tasks.count", { count: laneTasks.length })}
        />
        <Chip size="small" color="primary" variant="outlined" label={`${totalSp} SP`} />
        {sprint === null && (
          <IconButton
            size="small"
            aria-label={t("p.work.backlog.addTaskAria")}
            onClick={() => document.getElementById("backlog-inline")?.focus()}
          >
            <Plus size={16} />
          </IconButton>
        )}
      </Stack>
      <Divider sx={{ mb: 1 }} />
      <Stack spacing={0.75}>
        {laneTasks.map((task) => (
          <DraggableCard
            key={task.id}
            task={task}
            onMove={(el) => onMoveTask(task, el)}
          />
        ))}
        {laneTasks.length === 0 && (
          <Typography variant="caption" color="text.secondary" textAlign="center" py={2}>
            {sprint ? t("p.work.backlog.dragHint") : t("p.work.backlog.emptyBacklog")}
          </Typography>
        )}
      </Stack>
      {sprint === null && onNewTitle && onCreateInline && (
        <TextField
          id="backlog-inline"
          size="small"
          fullWidth
          placeholder={t("p.work.backlog.newTaskPlaceholder")}
          inputProps={{ "aria-label": t("p.work.backlog.newTaskPlaceholder") }}
          value={newTitle}
          onChange={(e) => onNewTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (newTitle ?? "").trim()) {
              e.preventDefault();
              onCreateInline((newTitle ?? "").trim());
            }
          }}
          sx={{ mt: 1 }}
        />
      )}
    </Paper>
  );
}

function DraggableCard({
  task,
  onMove,
}: {
  task: Task;
  onMove: (el: HTMLElement) => void;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
  });
  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      {...attributes}
      {...listeners}
      style={{
        transform: CSS.Translate.toString(transform),
        opacity: isDragging ? 0.4 : 1,
      }}
      sx={{ p: 1, cursor: "grab", display: "flex", alignItems: "center", gap: 1 }}
    >
      <Box flex={1} minWidth={0}>
        <Typography variant="body2" fontWeight={600} noWrap>
          {task.title}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {t(TASK_STATE_I18N_KEYS[task.state])}
        </Typography>
      </Box>
      <PriorityBadge priority={task.priority} />
      {task.story_points != null && (
        <Chip
          size="small"
          label={`${task.story_points} SP`}
          sx={{ height: 18, fontSize: 10 }}
          variant="outlined"
        />
      )}
      <IconButton
        size="small"
        aria-label={t("p.work.backlog.moveTaskAria", { title: task.title })}
        onClick={(e) => {
          e.stopPropagation();
          onMove(e.currentTarget);
        }}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <ArrowDownToLine size={14} />
      </IconButton>
    </Paper>
  );
}
