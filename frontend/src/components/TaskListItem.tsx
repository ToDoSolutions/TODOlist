import {
  Paper,
  Stack,
  LinearProgress,
  Typography,
  Chip,
  IconButton,
  Box,
  Checkbox,
  Collapse,
  Tooltip,
  Select,
  MenuItem,
  Menu,
  ListItemIcon,
  ListItemText,
  Divider,
  FormControl,
  CircularProgress,
  Avatar,
  AvatarGroup,
  TextField,
} from "@mui/material";
import {
  Calendar,
  CalendarDays,
  CheckCircle2,
  Flag,
  Trash2,
  FolderInput,
  History,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  RotateCcw,
  Target,
  MoreVertical,
  Eye,
  Timer,
  Copy,
  Pencil,
  Pin,
  PinOff,
  Star,
  StarOff,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { format, isPast, isToday } from "date-fns";
import { es, enUS } from "date-fns/locale";
import { useTranslation } from "react-i18next";
import "../i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi, sprintsApi } from "../api/resources";
import { useUiStore } from "../store/uiStore";
import {
  useUndoDelete,
  type AssigneeDetail,
  type TaskX,
  type TimerStatus,
} from "../api/featTask";
import { taskX2Api } from "../api/featTask2";
import { notify } from "../notify";
import { useConfirm } from "./ConfirmDialog";
import { useContextMenu, type ContextMenuState } from "./ui/contextMenu";
import { TASK_STATE_I18N_KEYS } from "../i18n/batchTaskUi";
import {
  Task,
  TaskState,
  TaskPriority,
  TaskInput,
  Activity,
  STATE_COLORS,
  PRIORITY_COLORS,
} from "../types";

interface Props {
  task: Task;
  onEdit: (t: Task) => void;
  /** Override opcional: el padre puede indicar que el timer corre
   *  (p.ej. desde una query agregada). Si no se pasa, se lee la caché
   *  ["task-timer", id] poblada por TaskDialog — sin fetch extra. */
  timerRunning?: boolean;
}

function initialsOf(u: AssigneeDetail): string {
  const base = u.username || u.email || "?";
  const parts = base.split(/[\s.@_-]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "?").concat(parts[1]?.[0] ?? "").toUpperCase();
}

/**
 * Nuevo vencimiento al programar en `day`: conserva la hora original si la
 * tarea la tenía (distinta de 00:00); si no, cae a las 18:00 — misma
 * convención que el drag-reschedule de CalendarView.
 */
function scheduledISO(task: Task, day: Date): string {
  const next = new Date(day);
  let hours = 18;
  let minutes = 0;
  if (task.due_date) {
    const orig = new Date(task.due_date);
    if (orig.getHours() !== 0 || orig.getMinutes() !== 0) {
      hours = orig.getHours();
      minutes = orig.getMinutes();
    }
  }
  next.setHours(hours, minutes, 0, 0);
  return next.toISOString();
}

const PRIORITY_ORDER: TaskPriority[] = [0, 1, 2, 3, 4, 5];
const MENU_STATES = Object.keys(TASK_STATE_I18N_KEYS) as TaskState[];

/**
 * Menú contextual de tarea (clic derecho) compartido por la lista
 * (TaskListItem) y las tarjetas del kanban. Usa las mismas mutaciones,
 * confirmación de borrado y deshacer que los controles visibles.
 *
 *   const menu = useContextMenu<Task>();
 *   <Row onContextMenu={menu.openFor(task)} />
 *   <TaskContextMenu menu={menu} />
 */
export function TaskContextMenu({
  menu,
}: {
  menu: { state: ContextMenuState<Task> | null; close: () => void };
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const undoDelete = useUndoDelete();
  const [priorityAnchor, setPriorityAnchor] = useState<HTMLElement | null>(null);
  const [stateAnchor, setStateAnchor] = useState<HTMLElement | null>(null);
  const target = menu.state?.target ?? null;

  const closeAll = () => {
    setPriorityAnchor(null);
    setStateAnchor(null);
    menu.close();
  };

  const updateTask = useMutation({
    mutationFn: ({ task, patch }: { task: Task; patch: Partial<TaskInput> }) =>
      tasksApi.update(task.id, patch),
    onSuccess: (_data, vars) => {
      if (vars.patch.state === "completed") notify.success(t("p.task.taskCompleted"));
      else if (vars.patch.state === "pending") notify.success(t("p.task.taskReopened"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.board.updateError")),
  });

  const duplicateTask = useMutation({
    mutationFn: (id: number) => taskX2Api.duplicate(id),
    onSuccess: () => {
      notify.success(t("p.taskx.duplicate.done"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => notify.error(t("p.taskx.duplicate.error")),
  });

  const deleteTask = useMutation({
    mutationFn: (task: Task) => tasksApi.remove(task.id),
    onSuccess: (_data, task) => {
      // Snackbar "Eliminada — Deshacer": restaura el snapshot completo
      undoDelete(task as TaskX);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => notify.error(t("p.task.taskDeleteError")),
  });

  const schedule = (days: number) => {
    const task = target;
    if (!task) return;
    const day = new Date();
    day.setDate(day.getDate() + days);
    updateTask.mutate({
      task,
      patch: { due_date: scheduledISO(task, day) },
    });
  };

  return (
    <>
      <Menu
        open={!!menu.state}
        onClose={closeAll}
        anchorReference="anchorPosition"
        anchorPosition={
          menu.state ? { top: menu.state.mouseY, left: menu.state.mouseX } : undefined
        }
        onClick={(e) => e.stopPropagation()}
      >
        <MenuItem
          onClick={() => {
            const task = target;
            closeAll();
            if (task)
              updateTask.mutate({
                task,
                patch: {
                  state:
                    task.state === "completed"
                      ? ("pending" as TaskState)
                      : ("completed" as TaskState),
                },
              });
          }}
        >
          <ListItemIcon>
            {target?.state === "completed" ? (
              <RotateCcw size={16} />
            ) : (
              <CheckCircle2 size={16} />
            )}
          </ListItemIcon>
          <ListItemText>
            {t(
              target?.state === "completed"
                ? "p.taskx.menu.reopen"
                : "p.taskx.menu.complete",
            )}
          </ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            closeAll();
            schedule(0);
          }}
        >
          <ListItemIcon>
            <Calendar size={16} />
          </ListItemIcon>
          <ListItemText>{t("p.taskx.menu.today")}</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            closeAll();
            schedule(1);
          }}
        >
          <ListItemIcon>
            <CalendarDays size={16} />
          </ListItemIcon>
          <ListItemText>{t("p.taskx.menu.tomorrow")}</ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem
          aria-haspopup="menu"
          onClick={(e) => setPriorityAnchor(e.currentTarget)}
        >
          <ListItemIcon>
            <Flag size={16} />
          </ListItemIcon>
          <ListItemText>{t("p.taskx.menu.priority")}</ListItemText>
          <ChevronRight size={14} />
        </MenuItem>
        <MenuItem aria-haspopup="menu" onClick={(e) => setStateAnchor(e.currentTarget)}>
          <ListItemIcon>
            <ArrowRight size={16} />
          </ListItemIcon>
          <ListItemText>{t("p.work.tasks.changeState")}</ListItemText>
          <ChevronRight size={14} />
        </MenuItem>
        <Divider />
        <MenuItem
          disabled={duplicateTask.isPending}
          onClick={() => {
            const task = target;
            closeAll();
            if (task) duplicateTask.mutate(task.id);
          }}
        >
          <ListItemIcon>
            <Copy size={16} />
          </ListItemIcon>
          <ListItemText>{t("p.taskx.menu.duplicate")}</ListItemText>
        </MenuItem>
        <MenuItem
          sx={{ color: "error.main" }}
          onClick={async () => {
            const task = target;
            closeAll();
            if (
              task &&
              (await confirm(t("p.task.confirmDeleteTask"), {
                confirmLabel: t("p.task.deleteTask"),
              }))
            )
              deleteTask.mutate(task);
          }}
        >
          <ListItemIcon>
            <Trash2 size={16} color="currentColor" />
          </ListItemIcon>
          <ListItemText>{t("p.taskx.menu.delete")}</ListItemText>
        </MenuItem>
      </Menu>
      {/* Submenús anclados al item padre (patrón Linear/Todoist) */}
      <Menu
        anchorEl={priorityAnchor}
        open={!!priorityAnchor}
        onClose={() => setPriorityAnchor(null)}
        anchorOrigin={{ vertical: "top", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        onClick={(e) => e.stopPropagation()}
      >
        {PRIORITY_ORDER.map((p) => (
          <MenuItem
            key={p}
            selected={target?.priority === p}
            onClick={() => {
              const task = target;
              closeAll();
              if (task) updateTask.mutate({ task, patch: { priority: p } });
            }}
          >
            <ListItemIcon>
              <Flag size={14} color={PRIORITY_COLORS[p]} />
            </ListItemIcon>
            <ListItemText>{t(`task.priority.p${p}`)}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
      <Menu
        anchorEl={stateAnchor}
        open={!!stateAnchor}
        onClose={() => setStateAnchor(null)}
        anchorOrigin={{ vertical: "top", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        onClick={(e) => e.stopPropagation()}
      >
        {MENU_STATES.map((s) => (
          <MenuItem
            key={s}
            selected={target?.state === s}
            onClick={() => {
              const task = target;
              closeAll();
              if (task) updateTask.mutate({ task, patch: { state: s } });
            }}
          >
            <ListItemIcon>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  bgcolor: STATE_COLORS[s],
                }}
              />
            </ListItemIcon>
            <ListItemText>{t(TASK_STATE_I18N_KEYS[s])}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}

export default function TaskListItem({ task, onEdit, timerRunning }: Props) {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === "en" ? enUS : es;
  const qc = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const undoDelete = useUndoDelete();
  const [showSprintSelect, setShowSprintSelect] = useState(false);
  const [showActivities, setShowActivities] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [renameVal, setRenameVal] = useState("");
  const ctxMenu = useContextMenu<Task>();
  const taskX = task as TaskX;

  // Indicador de timer sin fetch propio: observa la caché que TaskDialog
  // puebla con ["task-timer", id] (enabled:false → nunca dispara request).
  const { data: cachedTimer } = useQuery<TimerStatus>({
    queryKey: ["task-timer", task.id],
    enabled: false,
  });
  const timerActive = timerRunning ?? cachedTimer?.running ?? false;
  const assignees = taskX.assignees_detail ?? [];
  const watchersCount = taskX.watchers?.length ?? 0;

  const toggleComplete = useMutation({
    mutationFn: () =>
      tasksApi.update(task.id, {
        state:
          task.state === "completed"
            ? ("pending" as TaskState)
            : ("completed" as TaskState),
      }),
    onSuccess: () => {
      notify.success(
        task.state === "completed" ? t("p.task.taskReopened") : t("p.task.taskCompleted"),
      );
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const deleteTask = useMutation({
    mutationFn: () => tasksApi.remove(task.id),
    onSuccess: () => {
      // Snackbar "Eliminada — Deshacer" (5 s): restaura el snapshot completo
      undoDelete(taskX);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => notify.error(t("p.task.taskDeleteError")),
  });

  const duplicateTask = useMutation({
    mutationFn: () => taskX2Api.duplicate(task.id),
    onSuccess: () => {
      notify.success(t("p.taskx.duplicate.done"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => notify.error(t("p.taskx.duplicate.error")),
  });

  // Patch genérico para las acciones rápidas al hover (hoy, prioridad).
  const quickUpdate = useMutation({
    mutationFn: (patch: Partial<TaskInput>) => tasksApi.update(task.id, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.board.updateError")),
  });

  const toggleFavorite = useMutation({
    mutationFn: () =>
      task.is_favorite ? tasksApi.unfavorite(task.id) : tasksApi.favorite(task.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
    onError: () => notify.error(t("p.board.updateError")),
  });

  const { data: sprints = [] } = useQuery({
    queryKey: ["sprints"],
    queryFn: sprintsApi.list,
    enabled: showSprintSelect,
  });

  const moveToSprint = useMutation({
    mutationFn: (sprintId: number) => tasksApi.moveToSprint(task.id, sprintId),
    onSuccess: () => {
      notify.success(t("p.task.movedToSprint"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setShowSprintSelect(false);
    },
    onError: () => notify.error(t("p.task.moveToSprintError")),
  });

  const { data: activitiesData, isLoading: activitiesLoading } = useQuery({
    queryKey: ["task-activities", task.id],
    queryFn: () => tasksApi.getActivities(task.id),
    enabled: !!showActivities,
  });
  const activities: Activity[] = Array.isArray(activitiesData)
    ? activitiesData
    : (activitiesData as { results?: Activity[] } | undefined)?.results || [];

  const due = task.due_date ? new Date(task.due_date) : null;
  const overdue = due && task.state !== "completed" && isPast(due) && !isToday(due);
  // Densidad global (Cómoda/Estándar/Compacta) → padding de la fila
  const density = useUiStore((s) => s.density);
  const rowPy = density === "compact" ? 0.5 : density === "comfortable" ? 2 : 1.5;

  return (
    <Paper
      variant="outlined"
      sx={{
        py: rowPy,
        px: 1.5,
        cursor: "pointer",
        "&:hover": { borderColor: "primary.main" },
        "&:hover .task-quick-actions, &:focus-within .task-quick-actions": {
          opacity: 1,
        },
        opacity: task.state === "completed" ? 0.6 : 1,
      }}
      onClick={() => onEdit(task)}
      onContextMenu={ctxMenu.openFor(task)}
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
          <Stack direction="row" spacing={0.75} alignItems="baseline">
            {task.is_pinned && (
              <Tooltip title={t("p.taskx.pinned")}>
                <Pin
                  size={13}
                  style={{ flexShrink: 0, alignSelf: "center" }}
                  aria-hidden
                />
              </Tooltip>
            )}
            {task.is_favorite && (
              <Tooltip title={t("p.taskx.favorite")}>
                <Star
                  size={13}
                  style={{
                    flexShrink: 0,
                    alignSelf: "center",
                    fill: "currentColor",
                  }}
                  color="#f5a623"
                  aria-hidden
                />
              </Tooltip>
            )}
            {task.is_milestone && (
              <Tooltip title={t("p.taskx.milestone")}>
                <Flag
                  size={13}
                  style={{ flexShrink: 0, alignSelf: "center" }}
                  color="#7c4dff"
                  aria-hidden
                />
              </Tooltip>
            )}
            {task.ref && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontFamily: "monospace", flexShrink: 0 }}
              >
                {task.ref}
              </Typography>
            )}
            {renaming ? (
              <TextField
                size="small"
                autoFocus
                value={renameVal}
                onChange={(e) => setRenameVal(e.target.value)}
                onFocus={(e) => e.target.select()}
                onClick={(e) => e.stopPropagation()}
                onDoubleClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => {
                  e.stopPropagation();
                  if (e.key === "Enter") {
                    const v = renameVal.trim();
                    if (v && v !== task.title) quickUpdate.mutate({ title: v });
                    setRenaming(false);
                  } else if (e.key === "Escape") {
                    setRenaming(false);
                  }
                }}
                onBlur={() => setRenaming(false)}
                sx={{ flex: 1 }}
                inputProps={{ maxLength: 200, "aria-label": t("p.taskx.rename") }}
              />
            ) : (
              <Typography
                fontWeight={600}
                title={t("p.taskx.rename.hint")}
                sx={{
                  textDecoration: task.state === "completed" ? "line-through" : "none",
                }}
                noWrap
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  setRenameVal(task.title);
                  setRenaming(true);
                }}
              >
                {task.title}
              </Typography>
            )}
          </Stack>
          {task.description && (
            <Typography variant="body2" color="text.secondary" noWrap>
              {task.description}
            </Typography>
          )}
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
              label={t(TASK_STATE_I18N_KEYS[task.state])}
              sx={{
                bgcolor: STATE_COLORS[task.state],
                color: "common.white",
                height: 20,
                fontSize: 11,
              }}
            />
            <Chip
              size="small"
              variant="outlined"
              icon={<Flag size={12} color={PRIORITY_COLORS[task.priority]} />}
              label={t(`task.priority.p${task.priority}`)}
              sx={{ height: 20, fontSize: 11 }}
            />
            {task.sprint_name && (
              <Chip
                size="small"
                variant="outlined"
                icon={<Target size={12} />}
                label={task.sprint_name}
                onClick={(e) => {
                  e.stopPropagation();
                  navigate("/app/sprints");
                }}
                sx={{
                  height: 20,
                  fontSize: 11,
                  bgcolor: "primary.light",
                  borderColor: "primary.main",
                  cursor: "pointer",
                }}
              />
            )}
            {due && (
              <Chip
                size="small"
                variant="outlined"
                icon={<Calendar size={12} />}
                label={format(
                  due,
                  due.getHours() || due.getMinutes() ? "dd MMM HH:mm" : "dd MMM",
                  { locale: dateLocale },
                )}
                color={overdue ? "error" : "default"}
                sx={{ height: 20, fontSize: 11 }}
              />
            )}
            {(task.subtasks || []).length > 0 && (
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <LinearProgress
                  variant="determinate"
                  value={
                    ((task.subtasks || []).filter((s) => s.is_done).length /
                      (task.subtasks || []).length) *
                    100
                  }
                  sx={{ width: 44, height: 4, borderRadius: 2 }}
                />
                <Typography variant="caption" color="text.secondary">
                  {t("p.task.subtaskProgress", {
                    done: (task.subtasks || []).filter((s) => s.is_done).length,
                    total: (task.subtasks || []).length,
                  })}
                </Typography>
              </Stack>
            )}
            {timerActive && (
              <Tooltip title={t("p.taskx.timer.running")}>
                <Chip
                  size="small"
                  variant="outlined"
                  icon={<Timer size={12} />}
                  label={
                    <Box
                      component="span"
                      sx={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        bgcolor: "error.main",
                        display: "inline-block",
                      }}
                    />
                  }
                  sx={{ height: 20, fontSize: 11, borderColor: "error.main" }}
                />
              </Tooltip>
            )}
            {taskX.is_watching && (
              <Tooltip
                title={`${t("p.taskx.watch.watching")} · ${t("p.taskx.watch.watchers", { count: watchersCount })}`}
              >
                <Eye
                  size={14}
                  color={STATE_COLORS.in_progress}
                  style={{ alignSelf: "center" }}
                />
              </Tooltip>
            )}
            {assignees.length > 0 && (
              <AvatarGroup
                max={3}
                sx={{
                  ml: 0.5,
                  "& .MuiAvatar-root": {
                    width: 20,
                    height: 20,
                    fontSize: 10,
                  },
                }}
              >
                {assignees.map((u) => (
                  <Tooltip key={u.id} title={u.email || u.username}>
                    <Avatar sx={{ width: 20, height: 20, fontSize: 10 }}>
                      {initialsOf(u)}
                    </Avatar>
                  </Tooltip>
                ))}
              </AvatarGroup>
            )}
          </Stack>
        </Box>
        {/* Acciones rápidas al hover/focus (patrón Todoist): programar hoy
            y ciclar prioridad. opacity-0 pero focusables para teclado. */}
        <Box
          className="task-quick-actions"
          sx={{
            display: "flex",
            alignItems: "center",
            alignSelf: "center",
            opacity: 0,
            transition: "opacity 0.15s",
          }}
        >
          <Tooltip title={t("p.taskx.menu.today")}>
            <IconButton
              size="small"
              aria-label={t("p.taskx.menu.today")}
              onClick={(e) => {
                e.stopPropagation();
                quickUpdate.mutate({ due_date: scheduledISO(task, new Date()) });
              }}
            >
              <Calendar size={16} />
            </IconButton>
          </Tooltip>
          <Tooltip
            title={t("p.taskx.menu.priorityLabel", {
              label: t(`task.priority.p${task.priority}`),
            })}
          >
            <IconButton
              size="small"
              aria-label={t("p.taskx.menu.priority")}
              onClick={(e) => {
                e.stopPropagation();
                quickUpdate.mutate({
                  priority: ((task.priority + 1) % 6) as TaskPriority,
                });
              }}
            >
              <Flag size={16} color={PRIORITY_COLORS[task.priority]} />
            </IconButton>
          </Tooltip>
        </Box>
        <Tooltip title={t("p.task.actions")}>
          <IconButton
            size="small"
            aria-label={t("p.task.actionsFor", { title: task.title })}
            aria-haspopup="menu"
            onClick={(e) => {
              e.stopPropagation();
              setMenuAnchor(e.currentTarget);
            }}
          >
            <MoreVertical size={16} />
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={menuAnchor}
          open={!!menuAnchor}
          onClose={() => setMenuAnchor(null)}
          onClick={(e) => e.stopPropagation()}
        >
          <MenuItem
            onClick={() => {
              setMenuAnchor(null);
              quickUpdate.mutate({ is_pinned: !task.is_pinned });
            }}
          >
            <ListItemIcon>
              {task.is_pinned ? <PinOff size={16} /> : <Pin size={16} />}
            </ListItemIcon>
            <ListItemText>
              {task.is_pinned ? t("p.taskx.unpin") : t("p.taskx.pin")}
            </ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setMenuAnchor(null);
              toggleFavorite.mutate();
            }}
          >
            <ListItemIcon>
              {task.is_favorite ? <StarOff size={16} /> : <Star size={16} />}
            </ListItemIcon>
            <ListItemText>
              {task.is_favorite ? t("p.taskx.unfavorite") : t("p.taskx.favorite")}
            </ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setMenuAnchor(null);
              quickUpdate.mutate({ is_milestone: !task.is_milestone });
            }}
          >
            <ListItemIcon>
              <Flag size={16} />
            </ListItemIcon>
            <ListItemText>
              {task.is_milestone ? t("p.taskx.unmilestone") : t("p.taskx.milestone")}
            </ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setMenuAnchor(null);
              setShowSprintSelect((v) => !v);
            }}
          >
            <ListItemIcon>
              <FolderInput size={16} />
            </ListItemIcon>
            <ListItemText>{t("p.task.moveToSprint")}</ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setMenuAnchor(null);
              setShowActivities((v) => !v);
            }}
          >
            <ListItemIcon>
              <History size={16} />
            </ListItemIcon>
            <ListItemText>{t("p.task.activity")}</ListItemText>
          </MenuItem>
          <MenuItem
            disabled={duplicateTask.isPending}
            onClick={() => {
              setMenuAnchor(null);
              duplicateTask.mutate();
            }}
          >
            <ListItemIcon>
              <Copy size={16} />
            </ListItemIcon>
            <ListItemText>{t("p.taskx.duplicate.label")}</ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              setMenuAnchor(null);
              setRenameVal(task.title);
              setRenaming(true);
            }}
          >
            <ListItemIcon>
              <Pencil size={16} />
            </ListItemIcon>
            <ListItemText>{t("p.taskx.rename")}</ListItemText>
          </MenuItem>
          <MenuItem
            onClick={async () => {
              setMenuAnchor(null);
              if (
                await confirm(t("p.task.confirmDeleteTask"), {
                  confirmLabel: t("p.task.deleteTask"),
                })
              )
                deleteTask.mutate();
            }}
            sx={{ color: "error.main" }}
          >
            <ListItemIcon>
              <Trash2 size={16} color="currentColor" />
            </ListItemIcon>
            <ListItemText>{t("common.delete")}</ListItemText>
          </MenuItem>
        </Menu>
      </Stack>

      {/* Menú contextual (clic derecho) sobre toda la fila */}
      <TaskContextMenu menu={ctxMenu} />

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
                moveToSprint.isPending ? t("p.task.moving") : t("p.task.selectSprint")
              }
            >
              {sprints.length === 0 && (
                <MenuItem disabled>{t("p.task.noSprints")}</MenuItem>
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
              {t("p.task.activity")}
            </Typography>
          </Stack>
          {activitiesLoading ? (
            <CircularProgress size={16} />
          ) : activities && activities.length > 0 ? (
            <Stack spacing={0.5}>
              {activities.map((a: Activity) => (
                <Typography key={a.id} variant="caption" color="text.secondary">
                  {a.action} · {a.actor_email || t("p.task.system")} ·{" "}
                  {format(new Date(a.created_at), "dd MMM HH:mm", { locale: dateLocale })}
                </Typography>
              ))}
            </Stack>
          ) : (
            <Typography variant="caption" color="text.secondary">
              {t("p.task.noActivity")}
            </Typography>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
