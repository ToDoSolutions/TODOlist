import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Button,
  TextField,
  MenuItem,
  Stack,
  Paper,
  Chip,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  Alert,
} from "@mui/material";
import { Plus, List as ListIcon, Columns, Search, Calendar } from "lucide-react";
import { tasksApi, TaskFilters } from "../api/resources";
import { tagsApi } from "../api/resources";
import {
  Task,
  TaskPriority,
  TaskState,
  STATE_LABELS,
  STATE_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
} from "../types";
import TaskDialog from "../components/TaskDialog";
import TaskListItem from "../components/TaskListItem";
import KanbanBoard from "../components/KanbanBoard";
import CalendarView from "../components/CalendarView";

interface TasksPageProps {
  projectId?: number;
  title: string;
}

export default function TasksPage({ projectId, title }: TasksPageProps) {
  const [params, setParams] = useSearchParams();
  const view = (params.get("view") as "list" | "kanban" | "calendar") || "list";
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const qc = useQueryClient();

  const filters: TaskFilters = useMemo(
    () => ({
      project: projectId,
      state: params.get("state") || undefined,
      priority: params.get("priority") ? Number(params.get("priority")) : undefined,
      tags: params.get("tag") ? Number(params.get("tag")) : undefined,
      search: params.get("q") || undefined,
      ordering: params.get("ordering") || "-created_at",
    }),
    [projectId, params]
  );

  const { data: tasks = [], isLoading, error } = useQuery({
    queryKey: ["tasks", filters],
    queryFn: () => tasksApi.list(filters),
  });

  const { data: tags = [] } = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
    setParams(next);
  };

  const openNew = () => {
    setEditing(null);
    setDialogOpen(true);
  };
  const openEdit = (t: Task) => {
    setEditing(t);
    setDialogOpen(true);
  };

  const onSaved = () => {
    qc.invalidateQueries({ queryKey: ["tasks"] });
    qc.invalidateQueries({ queryKey: ["projects"] });
    setDialogOpen(false);
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h5" fontWeight={700}>
          {title}
        </Typography>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          Nueva tarea
        </Button>
      </Stack>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
          <TextField
            size="small"
            placeholder="Buscar…"
            value={params.get("q") || ""}
            onChange={(e) => setParam("q", e.target.value)}
            sx={{ minWidth: 220 }}
            InputProps={{ startAdornment: <Search size={16} style={{ marginRight: 6, color: "#888" }} /> }}
          />
          <TextField
            select
            size="small"
            label="Estado"
            value={params.get("state") || ""}
            onChange={(e) => setParam("state", e.target.value)}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">Todos</MenuItem>
            {(Object.keys(STATE_LABELS) as TaskState[]).map((s) => (
              <MenuItem key={s} value={s}>
                {STATE_LABELS[s]}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Prioridad"
            value={params.get("priority") || ""}
            onChange={(e) => setParam("priority", e.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">Todas</MenuItem>
            {([0, 1, 2, 3, 4, 5] as TaskPriority[]).map((p) => (
              <MenuItem key={p} value={p}>
                {PRIORITY_LABELS[p]}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Etiqueta"
            value={params.get("tag") || ""}
            onChange={(e) => setParam("tag", e.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">Todas</MenuItem>
            {tags.map((t) => (
              <MenuItem key={t.id} value={t.id}>
                {t.name}
              </MenuItem>
            ))}
          </TextField>
          <Box sx={{ flex: 1 }} />
          <ToggleButtonGroup
            size="small"
            value={view}
            exclusive
            onChange={(_, v) => v && setParam("view", v)}
          >
            <ToggleButton value="list">
              <ListIcon size={16} />
            </ToggleButton>
            <ToggleButton value="kanban">
              <Columns size={16} />
            </ToggleButton>
            <ToggleButton value="calendar">
              <Calendar size={16} />
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      </Paper>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">No se pudieron cargar las tareas.</Alert>
      ) : tasks.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Typography color="text.secondary">
            No hay tareas. Crea la primera con “Nueva tarea”.
          </Typography>
        </Paper>
      ) : view === "kanban" ? (
        <KanbanBoard tasks={tasks} onEdit={openEdit} />
      ) : view === "calendar" ? (
        <CalendarView tasks={tasks} onEdit={openEdit} />
      ) : (
        <Stack spacing={1}>
          {tasks.map((t) => (
            <TaskListItem key={t.id} task={t} onEdit={openEdit} />
          ))}
        </Stack>
      )}

      <TaskDialog
        open={dialogOpen}
        task={editing}
        defaultProjectId={projectId}
        onClose={() => setDialogOpen(false)}
        onSaved={onSaved}
      />
    </Box>
  );
}
