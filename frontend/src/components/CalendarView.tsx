import { useMemo, useState } from "react";
import {
  Box,
  Paper,
  Stack,
  Typography,
  IconButton,
  Chip,
} from "@mui/material";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  addMonths,
  format,
  isSameDay,
  isSameMonth,
  isToday,
} from "date-fns";
import { es } from "date-fns/locale";
import { Task, STATE_COLORS, PRIORITY_COLORS } from "../types";

interface Props {
  tasks: Task[];
  onEdit: (t: Task) => void;
}

const WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

export default function CalendarView({ tasks, onEdit }: Props) {
  const [cursor, setCursor] = useState(new Date());

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
    for (const t of tasks) {
      if (!t.due_date) continue;
      const key = format(new Date(t.due_date), "yyyy-MM-dd");
      (map[key] ||= []).push(t);
    }
    return map;
  }, [tasks]);

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} mb={2}>
        <IconButton onClick={() => setCursor(addMonths(cursor, -1))}>
          <ChevronLeft size={20} />
        </IconButton>
        <Typography variant="h6" fontWeight={700} sx={{ textTransform: "capitalize" }}>
          {format(cursor, "MMMM yyyy", { locale: es })}
        </Typography>
        <IconButton onClick={() => setCursor(addMonths(cursor, 1))}>
          <ChevronRight size={20} />
        </IconButton>
        <Box sx={{ flex: 1 }} />
        <IconButton size="small" onClick={() => setCursor(new Date())}>
          <Chip label="Hoy" size="small" clickable />
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
          const inMonth = isSameMonth(day, cursor);
          const today = isToday(day);
          return (
            <Paper
              key={key}
              variant="outlined"
              sx={{
                minHeight: 90,
                p: 0.5,
                opacity: inMonth ? 1 : 0.4,
                bgcolor: today ? "primary.50" : "background.paper",
                borderColor: today ? "primary.main" : "divider",
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
                {dayTasks.slice(0, 3).map((t) => (
                  <Box
                    key={t.id}
                    onClick={() => onEdit(t)}
                    sx={{
                      cursor: "pointer",
                      bgcolor: STATE_COLORS[t.state] + "22",
                      borderLeft: `3px solid ${PRIORITY_COLORS[t.priority]}`,
                      borderRadius: 0.5,
                      px: 0.5,
                      py: 0.25,
                      "&:hover": { bgcolor: STATE_COLORS[t.state] + "44" },
                    }}
                  >
                    <Typography
                      variant="caption"
                      noWrap
                      sx={{
                        fontSize: 10,
                        lineHeight: 1.2,
                        textDecoration: t.state === "completed" ? "line-through" : "none",
                      }}
                    >
                      {t.title}
                    </Typography>
                  </Box>
                ))}
                {dayTasks.length > 3 && (
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                    +{dayTasks.length - 3} más
                  </Typography>
                )}
              </Stack>
            </Paper>
          );
        })}
      </Box>
    </Box>
  );
}
