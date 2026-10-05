import { useState, useMemo } from "react";
import { useStateLabels } from "../api/featOrg";
import { useTranslation } from "react-i18next";
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
  ChevronsLeft,
  ChevronsRight,
  ArrowRight,
} from "lucide-react";
import { useMediaQuery, useTheme, Select, FormControl } from "@mui/material";
import { formatShort } from "../lib/dates";
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
import { useContextMenu } from "./ui/contextMenu";
import { TaskContextMenu } from "./TaskListItem";
import { useUiStore } from "../store/uiStore";
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
  projectId?: number;
}

type SwimlaneMode = "none" | "priority" | "type" | "sprint" | "assignee";

const SWIMLANE_LABELS: Record<SwimlaneMode, string> = {
  none: "p.board.swimlane.none",
  priority: "p.board.swimlane.priority",
  type: "p.board.swimlane.type",
  sprint: "p.board.swimlane.sprint",
  assignee: "p.board.swimlane.assignee",
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
  /** Handler onContextMenu ya vinculado a esta tarea (menu.openFor(task)). */
  onContextMenu?: (e: React.MouseEvent) => void;
}

function KanbanCard({ task, onEdit, onContextMenu }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
  });

  const due = task.due_date ? new Date(task.due_date) : null;
  const isOverdue = due && due < new Date() && task.state !== "completed";

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      onClick={() => !isDragging && onEdit(task)}
      onContextMenu={onContextMenu}
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
              color: "common.white",
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
            label={formatShort(due)}
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
  stateLabel,
  collapsed,
  onToggleCollapse,
  onCardContextMenu,
}: {
  state: TaskState;
  tasks: Task[];
  onEdit: (t: Task) => void;
  onQuickAdd?: (state: TaskState) => void;
  swimlaneKey: string;
  stateLabel: (s: TaskState) => string;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onCardContextMenu?: (task: Task) => (e: React.MouseEvent) => void;
}) {
  const { t } = useTranslation();
  const { setNodeRef, isOver } = useDroppable({ id: swimlaneKey });
  const wipLimit = WIP_LIMITS[state];
  const isOverWip = wipLimit && tasks.length > wipLimit;

  // Columna colapsada: strip vertical estrecho (patrón ClickUp/Linear).
  // Sigue siendo droppable para poder soltar tareas sobre ella.
  if (collapsed) {
    return (
      <Paper
        ref={setNodeRef}
        variant="outlined"
        onClick={onToggleCollapse}
        sx={{
          width: 44,
          flexShrink: 0,
          bgcolor: "action.hover",
          py: 1,
          px: 0.5,
          minHeight: 200,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 1,
          cursor: "pointer",
          borderColor: isOver ? "primary.main" : "divider",
          borderWidth: isOver ? 2 : 1,
          transition: "border-color 0.2s, border-width 0.2s",
        }}
      >
        <Tooltip title={t("p.board.expandColumn")}>
          <IconButton
            size="small"
            aria-label={t("p.board.expandColumn")}
            onClick={(e) => {
              e.stopPropagation();
              onToggleCollapse();
            }}
            sx={{ p: 0.25 }}
          >
            <ChevronsRight size={14} />
          </IconButton>
        </Tooltip>
        <Box
          sx={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            bgcolor: STATE_COLORS[state],
          }}
        />
        <Typography
          variant="caption"
          fontWeight={700}
          sx={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
        >
          {stateLabel(state)}
        </Typography>
        <Chip
          size="small"
          label={tasks.length}
          variant="outlined"
          aria-label={t("p.board.count", { count: tasks.length })}
          sx={{ height: 18, fontSize: 11 }}
        />
      </Paper>
    );
  }

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
          {stateLabel(state)}
        </Typography>
        <Chip
          size="small"
          label={tasks.length}
          aria-label={t("p.board.count", { count: tasks.length })}
          sx={{
            height: 18,
            fontSize: 11,
            color: isOverWip ? "error.main" : "text.secondary",
            borderColor: isOverWip ? "error.main" : "divider",
          }}
          variant="outlined"
        />
        {onQuickAdd && (
          <Tooltip title={t("p.board.addTaskHere")}>
            <IconButton
              size="small"
              onClick={() => onQuickAdd(state)}
              sx={{ ml: "auto", p: 0.25 }}
            >
              <Plus size={14} />
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title={t("p.board.collapseColumn")}>
          <IconButton
            size="small"
            aria-label={t("p.board.collapseColumn")}
            onClick={onToggleCollapse}
            sx={{ ml: onQuickAdd ? 0 : "auto", p: 0.25 }}
          >
            <ChevronsLeft size={14} />
          </IconButton>
        </Tooltip>
      </Stack>
      {isOverWip && (
        <Alert severity="warning" sx={{ py: 0, mb: 0.5, fontSize: 10 }}>
          WIP {tasks.length}/{wipLimit}
        </Alert>
      )}
      <Stack spacing={1}>
        {tasks.map((t) => (
          <KanbanCard
            key={t.id}
            task={t}
            onEdit={onEdit}
            onContextMenu={onCardContextMenu ? onCardContextMenu(t) : undefined}
          />
        ))}
        {tasks.length === 0 && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ p: 1, textAlign: "center" }}
          >
            {t("p.board.dragHere")}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}

export default function KanbanBoard({ tasks, onEdit, onQuickAdd, projectId }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const muiTheme = useTheme();
  const { labelFor } = useStateLabels(projectId);
  const stateLabel = (s: TaskState) => labelFor(s) ?? STATE_LABELS[s];
  const isMobile = useMediaQuery(muiTheme.breakpoints.down("md"));
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [swimlaneMode, setSwimlaneMode] = useState<SwimlaneMode>("none");
  const [search, setSearch] = useState("");
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  // Móvil: una columna visible a la vez + "Mover a" por tarjeta
  // (drag-and-drop táctil es una mala UX y poco accesible)
  const [mobileColumn, setMobileColumn] = useState<TaskState>("in_progress");
  const [moveAnchor, setMoveAnchor] = useState<{ task: Task; el: HTMLElement } | null>(
    null,
  );
  // Menú contextual (clic derecho) sobre tarjetas — compartido con la lista.
  const ctxMenu = useContextMenu<Task>();
  // Columnas colapsadas persistidas por proyecto (o "global").
  const kanbanCollapsed = useUiStore((s) => s.kanbanCollapsed);
  const toggleKanbanColumn = useUiStore((s) => s.toggleKanbanColumn);
  const collapseKey = (col: TaskState) => String(projectId ?? "global") + ":" + col;

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  const move = useMutation({
    mutationFn: ({ id, state }: { id: number; state: TaskState }) =>
      tasksApi.update(id, { state }),
    onSuccess: () => {
      notify.info(t("p.board.taskMoved"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  // Filtrar por búsqueda
  const filteredTasks = useMemo(() => {
    if (!search.trim()) return tasks;
    const q = search.toLowerCase();
    return tasks.filter(
      (t) => t.title.toLowerCase().includes(q) || t.description.toLowerCase().includes(q),
    );
  }, [tasks, search]);

  // Agrupar por swimlane
  const swimlanes = useMemo(() => {
    if (swimlaneMode === "none") {
      return [{ key: "all", label: "", tasks: filteredTasks }];
    }
    const groups: Record<string, { label: string; tasks: Task[] }> = {};
    for (const task of filteredTasks) {
      let key = "sin_asignar";
      let label = t("p.board.unassigned");
      if (swimlaneMode === "priority") {
        key = `p${task.priority}`;
        label = PRIORITY_LABELS[task.priority];
      } else if (swimlaneMode === "type") {
        key = task.task_type || "task";
        label = TYPE_LABELS[(task.task_type || "task") as TaskType] || t("p.board.task");
      } else if (swimlaneMode === "sprint") {
        key = task.sprint ? `s${task.sprint}` : "no_sprint";
        label = task.sprint_name || t("p.board.noSprint");
      } else if (swimlaneMode === "assignee") {
        key = task.assignee ? `a${task.assignee}` : "no_assignee";
        label = task.assignee_email || t("p.board.unassigned");
      }
      if (!groups[key]) groups[key] = { label, tasks: [] };
      groups[key]!.tasks.push(task);
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
  }, [filteredTasks, swimlaneMode, t]);

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
          placeholder={t("p.board.searchBoard")}
          inputProps={{ "aria-label": t("p.board.searchBoard") }}
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
            {t(SWIMLANE_LABELS[swimlaneMode])}
          </Typography>
          <ChevronDown size={14} />
        </IconButton>
        <Menu anchorEl={anchorEl} open={!!anchorEl} onClose={() => setAnchorEl(null)}>
          {(Object.keys(SWIMLANE_LABELS) as SwimlaneMode[]).map((mode) => (
            <MenuItem
              key={mode}
              selected={swimlaneMode === mode}
              onClick={() => {
                setSwimlaneMode(mode);
                setAnchorEl(null);
              }}
            >
              <ListItemText primary={t(SWIMLANE_LABELS[mode])} />
            </MenuItem>
          ))}
        </Menu>
      </Stack>

      {/* Móvil: una columna a la vez con selector + "Mover a" por tarjeta */}
      {isMobile ? (
        <Box>
          <FormControl size="small" fullWidth sx={{ mb: 1.5 }}>
            <Select
              value={mobileColumn}
              onChange={(e) => setMobileColumn(e.target.value as TaskState)}
              aria-label={t("p.board.boardColumn")}
            >
              {KANBAN_COLUMNS.map((col) => {
                const n = filteredTasks.filter((t) => t.state === col).length;
                const wip = WIP_LIMITS[col];
                return (
                  <MenuItem key={col} value={col}>
                    {stateLabel(col)} — {n}
                    {wip ? ` / WIP ${wip}` : ""}
                  </MenuItem>
                );
              })}
            </Select>
          </FormControl>
          {WIP_LIMITS[mobileColumn] &&
            filteredTasks.filter((t) => t.state === mobileColumn).length >
              WIP_LIMITS[mobileColumn]! && (
              <Alert severity="warning" sx={{ mb: 1.5 }}>
                {t("p.board.wipExceeded", {
                  count: filteredTasks.filter((task) => task.state === mobileColumn)
                    .length,
                  limit: WIP_LIMITS[mobileColumn],
                })}
              </Alert>
            )}
          <Stack spacing={1}>
            {filteredTasks
              .filter((task) => task.state === mobileColumn)
              .map((task) => (
                <Paper
                  key={task.id}
                  variant="outlined"
                  sx={{
                    p: 1.5,
                    borderLeft: `3px solid ${PRIORITY_COLORS[task.priority]}`,
                  }}
                  onClick={() => onEdit(task)}
                  onContextMenu={ctxMenu.openFor(task)}
                >
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Box flex={1} minWidth={0}>
                      <Typography variant="body2" fontWeight={600}>
                        {task.title}
                      </Typography>
                    </Box>
                    <IconButton
                      size="small"
                      aria-label={t("p.board.moveToColumn", { title: task.title })}
                      onClick={(e) => {
                        e.stopPropagation();
                        setMoveAnchor({ task, el: e.currentTarget });
                      }}
                    >
                      <ArrowRight size={16} />
                    </IconButton>
                  </Stack>
                </Paper>
              ))}
            {filteredTasks.filter((t) => t.state === mobileColumn).length === 0 && (
              <Typography
                variant="body2"
                color="text.secondary"
                textAlign="center"
                py={4}
              >
                {t("p.board.emptyColumn")}
              </Typography>
            )}
          </Stack>
          <Menu
            anchorEl={moveAnchor?.el}
            open={!!moveAnchor}
            onClose={() => setMoveAnchor(null)}
          >
            <ListItemText
              primary={t("p.board.moveTo")}
              sx={{ px: 2, py: 0.5, opacity: 0.6, pointerEvents: "none" }}
            />
            {KANBAN_COLUMNS.filter((c) => c !== moveAnchor?.task.state).map((c) => (
              <MenuItem
                key={c}
                onClick={() => {
                  if (moveAnchor) move.mutate({ id: moveAnchor.task.id, state: c });
                  setMoveAnchor(null);
                }}
              >
                {stateLabel(c)}
              </MenuItem>
            ))}
          </Menu>
        </Box>
      ) : (
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
                      stateLabel={stateLabel}
                      collapsed={!!kanbanCollapsed[collapseKey(col)]}
                      onToggleCollapse={() => toggleKanbanColumn(collapseKey(col))}
                      onCardContextMenu={ctxMenu.openFor}
                    />
                  );
                })}
              </Stack>
            </Box>
          ))}
        </Box>
      )}

      {/* Menú contextual (clic derecho) sobre tarjetas */}
      <TaskContextMenu menu={ctxMenu} />

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
