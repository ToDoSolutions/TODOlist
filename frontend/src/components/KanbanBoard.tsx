import { Box, Paper, Typography, Stack, Chip } from "@mui/material";
import { Flag, Calendar } from "lucide-react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "../api/resources";
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

export default function KanbanBoard({ tasks, onEdit }: Props) {
  const qc = useQueryClient();

  const move = useMutation({
    mutationFn: ({ id, state }: { id: number; state: TaskState }) =>
      tasksApi.update(id, { state }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const onDrop = (e: React.DragEvent, state: TaskState) => {
    e.preventDefault();
    const id = Number(e.dataTransfer.getData("text/plain"));
    if (id) move.mutate({ id, state });
  };

  return (
    <Box sx={{ overflowX: "auto", pb: 1 }}>
      <Stack direction="row" spacing={1.5} sx={{ minWidth: "max-content" }}>
        {KANBAN_COLUMNS.map((col) => {
          const colTasks = tasks.filter((t) => t.state === col);
          return (
            <Paper
              key={col}
              variant="outlined"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => onDrop(e, col)}
              sx={{
                width: 280,
                flexShrink: 0,
                bgcolor: "action.hover",
                p: 1,
                minHeight: 400,
              }}
            >
              <Stack direction="row" alignItems="center" spacing={1} mb={1} px={0.5}>
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    bgcolor: STATE_COLORS[col],
                  }}
                />
                <Typography variant="subtitle2" fontWeight={700}>
                  {STATE_LABELS[col]}
                </Typography>
                <Chip size="small" label={colTasks.length} sx={{ height: 18, fontSize: 11 }} />
              </Stack>
              <Stack spacing={1}>
                {colTasks.map((t) => {
                  const due = t.due_date ? new Date(t.due_date) : null;
                  return (
                    <Paper
                      key={t.id}
                      variant="outlined"
                      draggable
                      onDragStart={(e) =>
                        e.dataTransfer.setData("text/plain", String(t.id))
                      }
                      onClick={() => onEdit(t)}
                      sx={{
                        p: 1.25,
                        cursor: "grab",
                        "&:active": { cursor: "grabbing" },
                        "&:hover": { borderColor: "primary.main" },
                        borderLeft: `3px solid ${PRIORITY_COLORS[t.priority]}`,
                      }}
                    >
                      <Typography variant="body2" fontWeight={600} noWrap>
                        {t.title}
                      </Typography>
                      <Stack direction="row" spacing={0.5} mt={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Chip
                          size="small"
                          icon={<Flag size={11} color={PRIORITY_COLORS[t.priority]} />}
                          label={PRIORITY_LABELS[t.priority]}
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
                })}
                {colTasks.length === 0 && (
                  <Typography variant="caption" color="text.secondary" sx={{ p: 1, textAlign: "center" }}>
                    Arrastra tareas aquí
                  </Typography>
                )}
              </Stack>
            </Paper>
          );
        })}
      </Stack>
    </Box>
  );
}
