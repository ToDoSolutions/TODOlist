import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Box, Paper, Stack, Typography, IconButton, Chip, Tooltip } from "@mui/material";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  startOfDay,
  endOfDay,
  subMilliseconds,
  addDays,
  addMonths,
  format,
  isSameMonth,
  isToday,
  isWithinInterval,
  parseISO,
} from "date-fns";
import { es, enUS } from "date-fns/locale";
import { useTranslation } from "react-i18next";
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
import { Task, TaskState, STATE_COLORS, PRIORITY_COLORS } from "../types";
import { tasksApi } from "../api/resources";
import { notify } from "../notify";
import { fetchOverlayEvents, type OverlayEvent } from "../api/featExtras";

interface Props {
  tasks: Task[];
  onEdit: (t: Task) => void;
}

// Estados terminales: no tiene sentido reprogramar su vencimiento.
const DRAG_DISABLED_STATES: TaskState[] = ["completed", "cancelled"];

const DRAG_PREFIX = "task-";
const DROP_PREFIX = "day-";

/**
 * Nueva fecha límite al soltar sobre `day`: conserva la hora original
 * si la tarea la tenía (distinta de 00:00); si no, cae a las 18:00.
 */
function rescheduledISO(task: Task, day: Date): string {
  const next = new Date(day);
  let hours = 18;
  let minutes = 0;
  if (task.due_date) {
    const orig = new Date(task.due_date);
    const hasTime = orig.getHours() !== 0 || orig.getMinutes() !== 0;
    if (hasTime) {
      hours = orig.getHours();
      minutes = orig.getMinutes();
    }
  }
  next.setHours(hours, minutes, 0, 0);
  return next.toISOString();
}

function TaskChip({ task, onEdit }: { task: Task; onEdit: (t: Task) => void }) {
  const dragDisabled = DRAG_DISABLED_STATES.includes(task.state);
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `${DRAG_PREFIX}${task.id}`,
    disabled: dragDisabled,
  });

  return (
    <Box
      ref={setNodeRef}
      onClick={() => !isDragging && onEdit(task)}
      {...attributes}
      {...listeners}
      style={{
        transform: CSS.Translate.toString(transform),
        opacity: isDragging ? 0.4 : 1,
      }}
      sx={{
        cursor: dragDisabled ? "pointer" : isDragging ? "grabbing" : "grab",
        bgcolor: STATE_COLORS[task.state] + "22",
        borderLeft: `3px solid ${PRIORITY_COLORS[task.priority]}`,
        borderRadius: 0.5,
        px: 0.5,
        py: 0.25,
        touchAction: "none",
        "&:hover": { bgcolor: STATE_COLORS[task.state] + "44" },
      }}
    >
      <Typography
        variant="caption"
        noWrap
        sx={{
          fontSize: 10,
          lineHeight: 1.2,
          textDecoration: task.state === "completed" ? "line-through" : "none",
        }}
      >
        {task.title}
      </Typography>
    </Box>
  );
}

function DayCell({
  dayKey,
  inMonth,
  today,
  day,
  children,
}: {
  dayKey: string;
  inMonth: boolean;
  today: boolean;
  day: Date;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `${DROP_PREFIX}${dayKey}` });

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      sx={{
        minHeight: 90,
        p: 0.5,
        opacity: inMonth ? 1 : 0.4,
        bgcolor: today ? "primary.50" : "background.paper",
        borderColor: isOver ? "primary.main" : today ? "primary.main" : "divider",
        borderWidth: isOver ? 2 : 1,
        transition: "border-color 0.15s, border-width 0.15s",
        overflow: "hidden",
      }}
    >
      <Typography
        variant="caption"
        sx={{
          fontWeight: today ? 700 : 400,
          color: today ? "primary.main" : "text.secondary",
        }}
      >
        {format(day, "d")}
      </Typography>
      <Stack spacing={0.25} sx={{ mt: 0.25 }}>
        {children}
      </Stack>
    </Paper>
  );
}

export default function CalendarView({ tasks, onEdit }: Props) {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === "en" ? enUS : es;
  const qc = useQueryClient();
  const [cursor, setCursor] = useState(new Date());
  const [activeTask, setActiveTask] = useState<Task | null>(null);

  const WEEKDAYS = [
    t("p.shell.ui.calendar.weekday.mon"),
    t("p.shell.ui.calendar.weekday.tue"),
    t("p.shell.ui.calendar.weekday.wed"),
    t("p.shell.ui.calendar.weekday.thu"),
    t("p.shell.ui.calendar.weekday.fri"),
    t("p.shell.ui.calendar.weekday.sat"),
    t("p.shell.ui.calendar.weekday.sun"),
  ];

  const days = useMemo(() => {
    const start = startOfWeek(startOfMonth(cursor), { weekStartsOn: 1 });
    const end = endOfWeek(endOfMonth(cursor), { weekStartsOn: 1 });
    const arr: Date[] = [];
    let d = start;
    while (d <= end) {
      arr.push(d);
      d = addDays(d, 1);
    }
    return arr;
  }, [cursor]);

  const tasksByDay = useMemo(() => {
    const map: Record<string, Task[]> = {};
    for (const task of tasks) {
      if (!task.due_date) continue;
      const key = format(new Date(task.due_date), "yyyy-MM-dd");
      (map[key] ||= []).push(task);
    }
    return map;
  }, [tasks]);

  // Eventos de calendarios externos (iCal) del rango visible del grid
  // (incluye los días de relleno del mes anterior/siguiente).
  const { data: extEvents = [] } = useQuery({
    queryKey: ["external-calendar-events", format(cursor, "yyyy-MM")],
    queryFn: () => fetchOverlayEvents(days[0] ?? cursor, days[days.length - 1] ?? cursor),
  });

  const extEventsByDay = useMemo(() => {
    const map: Record<string, OverlayEvent[]> = {};
    for (const ev of extEvents) {
      const s = parseISO(ev.dtstart);
      // En ICS, DTEND de un evento all-day es exclusivo.
      let e = ev.all_day ? subMilliseconds(parseISO(ev.dtend), 1) : parseISO(ev.dtend);
      if (e < s) e = s;
      for (const day of days) {
        if (isWithinInterval(day, { start: startOfDay(s), end: endOfDay(e) })) {
          (map[format(day, "yyyy-MM-dd")] ||= []).push(ev);
        }
      }
    }
    return map;
  }, [extEvents, days]);

  // Drag & drop: PointerSensor con umbral de 4 px para que el click
  // siga abriendo la edición; el drag empieza solo tras moverse.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  const reschedule = useMutation({
    mutationFn: ({ id, due_date }: { id: number; due_date: string }) =>
      tasksApi.update(id, { due_date }),
    onSuccess: (_d, vars) => {
      notify.success(
        t("p.taskx.cal.rescheduled", {
          date: format(new Date(vars.due_date), "d MMM", { locale: dateLocale }),
        }),
      );
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.taskx.cal.rescheduleError")),
  });

  const onDragStart = (e: DragStartEvent) => {
    const id = Number(String(e.active.id).replace(DRAG_PREFIX, ""));
    setActiveTask(tasks.find((tk) => tk.id === id) ?? null);
  };

  const onDragEnd = (e: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = e;
    if (!over) return;
    const overId = String(over.id);
    if (!overId.startsWith(DROP_PREFIX)) return;
    const dayKey = overId.slice(DROP_PREFIX.length);
    const taskId = Number(String(active.id).replace(DRAG_PREFIX, ""));
    const task = tasks.find((tk) => tk.id === taskId);
    if (!task || DRAG_DISABLED_STATES.includes(task.state)) return;
    const day = parseISO(dayKey);
    // Soltar en el mismo día no cambia nada.
    if (task.due_date && format(new Date(task.due_date), "yyyy-MM-dd") === dayKey) {
      return;
    }
    reschedule.mutate({ id: taskId, due_date: rescheduledISO(task, day) });
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      <Box>
        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <IconButton onClick={() => setCursor(addMonths(cursor, -1))}>
            <ChevronLeft size={20} />
          </IconButton>
          <Typography variant="h6" fontWeight={700} sx={{ textTransform: "capitalize" }}>
            {format(cursor, "MMMM yyyy", { locale: dateLocale })}
          </Typography>
          <IconButton onClick={() => setCursor(addMonths(cursor, 1))}>
            <ChevronRight size={20} />
          </IconButton>
          <Box sx={{ flex: 1 }} />
          <IconButton size="small" onClick={() => setCursor(new Date())}>
            <Chip label={t("p.shell.ui.calendar.today")} size="small" clickable />
          </IconButton>
        </Stack>

        <Stack direction="row" sx={{ mb: 1 }}>
          {WEEKDAYS.map((d) => (
            <Box key={d} sx={{ flex: 1, textAlign: "center" }}>
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                {d}
              </Typography>
            </Box>
          ))}
        </Stack>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(7, 1fr)",
            gap: 0.5,
          }}
        >
          {days.map((day) => {
            const key = format(day, "yyyy-MM-dd");
            const dayTasks = tasksByDay[key] || [];
            const dayEvents = extEventsByDay[key] || [];
            const inMonth = isSameMonth(day, cursor);
            const today = isToday(day);
            return (
              <DayCell key={key} dayKey={key} day={day} inMonth={inMonth} today={today}>
                {dayTasks.slice(0, 3).map((task) => (
                  <TaskChip key={task.id} task={task} onEdit={onEdit} />
                ))}
                {dayTasks.length > 3 && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontSize: 10 }}
                  >
                    {t("p.shell.ui.calendar.more", { count: dayTasks.length - 3 })}
                  </Typography>
                )}
                {dayEvents.slice(0, 2).map((ev) => (
                  <Tooltip
                    key={`${ev.id}-${ev.uid}`}
                    title={`${ev.summary} · ${ev.calendar}`}
                    arrow
                  >
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        minWidth: 0,
                      }}
                    >
                      <Box
                        sx={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          bgcolor: ev.color,
                          flexShrink: 0,
                        }}
                      />
                      <Typography
                        variant="caption"
                        noWrap
                        sx={{ fontSize: 10, lineHeight: 1.2, color: "text.secondary" }}
                      >
                        {ev.summary}
                      </Typography>
                    </Box>
                  </Tooltip>
                ))}
                {dayEvents.length > 2 && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontSize: 10 }}
                  >
                    {t("p.shell.ui.calendar.more", { count: dayEvents.length - 2 })}
                  </Typography>
                )}
              </DayCell>
            );
          })}
        </Box>
      </Box>

      <DragOverlay>
        {activeTask ? (
          <Paper
            variant="outlined"
            sx={{
              px: 0.5,
              py: 0.25,
              cursor: "grabbing",
              bgcolor: STATE_COLORS[activeTask.state] + "44",
              borderLeft: `3px solid ${PRIORITY_COLORS[activeTask.priority]}`,
              boxShadow: 8,
              opacity: 0.95,
              maxWidth: 220,
            }}
          >
            <Typography variant="caption" noWrap sx={{ fontSize: 10 }}>
              {activeTask.title}
            </Typography>
          </Paper>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
