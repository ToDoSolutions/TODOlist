import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  Paper,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  ToggleButtonGroup,
  ToggleButton,
  Divider,
} from "@mui/material";
import { Plus, Pencil, Trash2, Clock, Timer, BarChart3 } from "lucide-react";
import { timeEntriesApi, tasksApi, projectsApi } from "../api/resources";
import { notify } from "../notify";
import type { Task } from "../types";

interface TimeEntry {
  id: number;
  task: number;
  task_title?: string;
  duration: number; // minutes
  date: string;
  description?: string;
}

interface EntryForm {
  task: string;
  duration: string;
  description: string;
  date: string;
}

type DateFilter = "today" | "week" | "month" | "all";

const emptyForm: EntryForm = {
  task: "",
  duration: "",
  description: "",
  date: new Date().toISOString().slice(0, 10),
};

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

function startOfWeek(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay(); // 0 = Sunday
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Monday as start
  d.setDate(diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function startOfMonth(date: Date): Date {
  const d = new Date(date);
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  return d;
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export default function TimeEntriesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TimeEntry | null>(null);
  const [form, setForm] = useState<EntryForm>(emptyForm);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [dateFilter, setDateFilter] = useState<DateFilter>("all");

  const { data: entriesData, isLoading } = useQuery({
    queryKey: ["time-entries"],
    queryFn: timeEntriesApi.list,
  });
  const entries: TimeEntry[] = Array.isArray(entriesData)
    ? entriesData
    : (entriesData as any)?.results ?? [];

  const { data: tasksData } = useQuery({
    queryKey: ["tasks-for-selector"],
    queryFn: () => tasksApi.list(),
  });
  const tasks: Task[] = Array.isArray(tasksData) ? tasksData : [];

  const { data: projectsData } = useQuery({
    queryKey: ["projects-for-timeentries"],
    queryFn: projectsApi.list,
  });
  const projectMap = useMemo(() => {
    const m = new Map<number, string>();
    const list = Array.isArray(projectsData) ? projectsData : (projectsData as any)?.results || [];
    list.forEach((p: any) => m.set(p.id, p.name));
    return m;
  }, [projectsData]);

  // Map of task id -> task title (prefer task list, fall back to entry's task_title)
  const taskTitleMap = useMemo(() => {
    const m = new Map<number, string>();
    tasks.forEach((t) => m.set(t.id, t.title));
    entries.forEach((e) => {
      if (!m.has(e.task) && e.task_title) m.set(e.task, e.task_title);
    });
    return m;
  }, [tasks, entries]);

  // Map of task id -> project id
  const taskProjectMap = useMemo(() => {
    const m = new Map<number, number | null>();
    tasks.forEach((t) => m.set(t.id, t.project));
    return m;
  }, [tasks]);

  const getTaskTitle = (taskId: number) =>
    taskTitleMap.get(taskId) ?? `Tarea #${taskId}`;

  // Filtered entries based on date filter
  const filteredEntries = useMemo(() => {
    if (dateFilter === "all") return entries;
    const now = new Date();
    return entries.filter((e) => {
      const d = new Date(e.date + "T00:00:00");
      if (dateFilter === "today") return isSameDay(d, now);
      if (dateFilter === "week") return d >= startOfWeek(now);
      if (dateFilter === "month") return d >= startOfMonth(now);
      return true;
    });
  }, [entries, dateFilter]);

  // Statistics
  const stats = useMemo(() => {
    const now = new Date();
    const weekStart = startOfWeek(now);
    const monthStart = startOfMonth(now);

    const weekMinutes = entries
      .filter((e) => new Date(e.date + "T00:00:00") >= weekStart)
      .reduce((sum, e) => sum + (e.duration || 0), 0);

    const monthMinutes = entries
      .filter((e) => new Date(e.date + "T00:00:00") >= monthStart)
      .reduce((sum, e) => sum + (e.duration || 0), 0);

    // Time per task (top 5) - based on filtered entries
    const perTask = new Map<number, number>();
    filteredEntries.forEach((e) => {
      perTask.set(e.task, (perTask.get(e.task) || 0) + (e.duration || 0));
    });
    const topTasks = Array.from(perTask.entries())
      .map(([taskId, minutes]) => ({ taskId, minutes, title: getTaskTitle(taskId) }))
      .sort((a, b) => b.minutes - a.minutes)
      .slice(0, 5);

    // Time per project (based on filtered entries, using task->project mapping)
    const perProject = new Map<number, number>();
    const projectHasEntries = new Set<number>();
    filteredEntries.forEach((e) => {
      const projId = taskProjectMap.get(e.task);
      if (projId != null) {
        perProject.set(projId, (perProject.get(projId) || 0) + (e.duration || 0));
        projectHasEntries.add(projId);
      }
    });
    const topProjects = Array.from(perProject.entries())
      .map(([projectId, minutes]) => ({ projectId, minutes }))
      .sort((a, b) => b.minutes - a.minutes);

    const filteredTotal = filteredEntries.reduce(
      (sum, e) => sum + (e.duration || 0),
      0
    );

    return {
      weekMinutes,
      monthMinutes,
      topTasks,
      topProjects,
      filteredTotal,
      hasProjectInfo: projectHasEntries.size > 0,
    };
  }, [entries, filteredEntries, taskTitleMap, taskProjectMap]);

  // Group filtered entries by task
  const groupedEntries = useMemo(() => {
    const groups = new Map<number, TimeEntry[]>();
    filteredEntries.forEach((e) => {
      const arr = groups.get(e.task) ?? [];
      arr.push(e);
      groups.set(e.task, arr);
    });
    // Sort groups by total time descending
    return Array.from(groups.entries())
      .map(([taskId, items]) => ({
        taskId,
        title: getTaskTitle(taskId),
        items: items.sort((a, b) => (a.date < b.date ? 1 : -1)),
        total: items.reduce((s, e) => s + (e.duration || 0), 0),
      }))
      .sort((a, b) => b.total - a.total);
  }, [filteredEntries, taskTitleMap]);

  const createMut = useMutation({
    mutationFn: () =>
      timeEntriesApi.create({
        task: Number(form.task),
        duration: Number(form.duration),
        description: form.description,
        date: form.date,
      }),
    onSuccess: () => {
      notify.success("Registro de tiempo creado");
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo crear el registro"),
  });

  const updateMut = useMutation({
    mutationFn: () =>
      timeEntriesApi.update(editing!.id, {
        task: Number(form.task),
        duration: Number(form.duration),
        description: form.description,
        date: form.date,
      }),
    onSuccess: () => {
      notify.success("Registro de tiempo actualizado");
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setOpen(false);
    },
    onError: () => notify.error("No se pudo actualizar"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => timeEntriesApi.delete(id),
    onSuccess: () => {
      notify.success("Registro de tiempo eliminado");
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setDeleteId(null);
    },
    onError: () => notify.error("No se pudo eliminar"),
  });

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (e: TimeEntry) => {
    setEditing(e);
    setForm({
      task: String(e.task),
      duration: String(e.duration),
      description: e.description ?? "",
      date: e.date ?? "",
    });
    setOpen(true);
  };

  const save = () => {
    if (!form.task || !form.duration || !form.date) return;
    if (editing) updateMut.mutate();
    else createMut.mutate();
  };

  return (
    <Box maxWidth={900} mx="auto">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h5" fontWeight={700}>
          Registros de tiempo
        </Typography>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          Nuevo registro
        </Button>
      </Stack>

      {/* Estadísticas */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <BarChart3 size={20} />
          <Typography variant="subtitle1" fontWeight={700}>
            Estadísticas
          </Typography>
        </Stack>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} flexWrap="wrap">
          <Box sx={{ flex: "1 1 auto", minWidth: 140 }}>
            <Typography variant="caption" color="text.secondary">
              Tiempo esta semana
            </Typography>
            <Typography variant="h6" fontWeight={700}>
              {formatDuration(stats.weekMinutes)}
            </Typography>
          </Box>
          <Box sx={{ flex: "1 1 auto", minWidth: 140 }}>
            <Typography variant="caption" color="text.secondary">
              Tiempo este mes
            </Typography>
            <Typography variant="h6" fontWeight={700}>
              {formatDuration(stats.monthMinutes)}
            </Typography>
          </Box>
          <Box sx={{ flex: "1 1 auto", minWidth: 140 }}>
            <Typography variant="caption" color="text.secondary">
              Total (filtro actual)
            </Typography>
            <Typography variant="h6" fontWeight={700}>
              {formatDuration(stats.filteredTotal)}
            </Typography>
          </Box>
        </Stack>

        <Divider sx={{ my: 2 }} />

        <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" fontWeight={600} mb={1}>
              Tiempo por tarea (top 5)
            </Typography>
            {stats.topTasks.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Sin datos
              </Typography>
            ) : (
              <Stack spacing={0.5}>
                {stats.topTasks.map((t) => (
                  <Stack
                    key={t.taskId}
                    direction="row"
                    justifyContent="space-between"
                    alignItems="center"
                  >
                    <Typography
                      variant="body2"
                      noWrap
                      sx={{ maxWidth: 260 }}
                      title={t.title}
                    >
                      {t.title}
                    </Typography>
                    <Chip
                      size="small"
                      icon={<Timer size={12} />}
                      label={formatDuration(t.minutes)}
                    />
                  </Stack>
                ))}
              </Stack>
            )}
          </Box>

          {stats.hasProjectInfo && (
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle2" fontWeight={600} mb={1}>
                Tiempo por proyecto
              </Typography>
              {stats.topProjects.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  Sin datos
                </Typography>
              ) : (
                <Stack spacing={0.5}>
                  {stats.topProjects.map((p) => (
                    <Stack
                      key={p.projectId}
                      direction="row"
                      justifyContent="space-between"
                      alignItems="center"
                    >
                      <Typography variant="body2">
                        {projectMap.get(p.projectId) || `Proyecto #${p.projectId}`}
                      </Typography>
                      <Chip
                        size="small"
                        icon={<Timer size={12} />}
                        label={formatDuration(p.minutes)}
                      />
                    </Stack>
                  ))}
                </Stack>
              )}
            </Box>
          )}
        </Stack>
      </Paper>

      {/* Date filter */}
      <Stack direction="row" alignItems="center" spacing={1} mb={2}>
        <Typography variant="body2" color="text.secondary">
          Filtrar por fecha:
        </Typography>
        <ToggleButtonGroup
          size="small"
          value={dateFilter}
          exclusive
          onChange={(_, v: DateFilter | null) => v && setDateFilter(v)}
        >
          <ToggleButton value="today">Hoy</ToggleButton>
          <ToggleButton value="week">Esta semana</ToggleButton>
          <ToggleButton value="month">Este mes</ToggleButton>
          <ToggleButton value="all">Todo</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : filteredEntries.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Clock size={32} style={{ color: "#bbb" }} />
          <Typography color="text.secondary" mt={1}>
            No hay registros de tiempo para este filtro. Crea uno para empezar a rastrear tu tiempo.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {groupedEntries.map((group) => (
            <Paper key={group.taskId} variant="outlined">
              <Box
                sx={{
                  px: 2,
                  py: 1,
                  bgcolor: "action.hover",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Clock size={16} style={{ color: "#888" }} />
                  <Typography variant="subtitle2" fontWeight={700} noWrap>
                    {group.title}
                  </Typography>
                </Stack>
                <Chip
                  size="small"
                  icon={<Timer size={12} />}
                  label={formatDuration(group.total)}
                />
              </Box>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Duración</TableCell>
                    <TableCell>Fecha</TableCell>
                    <TableCell>Descripción</TableCell>
                    <TableCell align="right">Acciones</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {group.items.map((e) => (
                    <TableRow key={e.id} hover>
                      <TableCell>
                        <Chip
                          size="small"
                          icon={<Timer size={14} />}
                          label={formatDuration(e.duration)}
                        />
                      </TableCell>
                      <TableCell>{e.date}</TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          noWrap
                          maxWidth={220}
                        >
                          {e.description || "—"}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="Editar">
                          <IconButton size="small" onClick={() => openEdit(e)}>
                            <Pencil size={16} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Eliminar">
                          <IconButton size="small" onClick={() => setDeleteId(e.id)}>
                            <Trash2 size={16} />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Paper>
          ))}
        </Stack>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>
          {editing ? "Editar registro de tiempo" : "Nuevo registro de tiempo"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl fullWidth required error={!form.task}>
              <InputLabel id="task-select-label">Tarea *</InputLabel>
              <Select
                labelId="task-select-label"
                label="Tarea *"
                value={form.task}
                onChange={(e) => setForm({ ...form, task: String(e.target.value) })}
                autoFocus
                displayEmpty
              >
                <MenuItem value="" disabled>
                  Selecciona una tarea
                </MenuItem>
                {tasks.map((t) => (
                  <MenuItem key={t.id} value={String(t.id)}>
                    {t.title}
                  </MenuItem>
                ))}
              </Select>
              {!form.task && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                  La tarea es obligatoria
                </Typography>
              )}
            </FormControl>
            <TextField
              label="Duración (minutos)"
              fullWidth
              required
              type="number"
              value={form.duration}
              onChange={(e) => setForm({ ...form, duration: e.target.value })}
            />
            <TextField
              label="Fecha"
              type="date"
              fullWidth
              required
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="Descripción"
              fullWidth
              multiline
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancelar</Button>
          <Button
            variant="contained"
            onClick={save}
            disabled={!form.task || !form.duration || !form.date}
          >
            {editing ? "Guardar" : "Crear"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs">
        <DialogTitle>Eliminar registro</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            ¿Seguro que deseas eliminar este registro de tiempo? Esta acción no se puede deshacer.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>Cancelar</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
          >
            Eliminar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
