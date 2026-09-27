import { useState, useMemo, useCallback } from "react";
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
  useTheme,
} from "@mui/material";
import { Plus, Pencil, Trash2, Clock, Timer, BarChart3 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { timeEntriesApi, tasksApi, projectsApi } from "../api/resources";
import { notify } from "../notify";
import { DateField } from "../components/DateField";
import type { Task, Project } from "../types";

interface TimeEntry {
  id: number;
  task: number;
  task_title?: string;
  duration_seconds: number;
  started_at: string;
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

/** Convierte segundos del backend a minutos para la UI */
function secondsToMinutes(seconds: number): number {
  return Math.round((seconds || 0) / 60);
}

/** Convierte minutos de la UI a segundos para el backend */
function minutesToSeconds(minutes: number): number {
  return Math.round(minutes * 60);
}

/** Extrae la fecha (YYYY-MM-DD) desde un ISO datetime del backend */
function dateFromISO(iso: string): string {
  if (!iso) return "";
  return iso.slice(0, 10);
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
  const { t } = useTranslation();
  const theme = useTheme();
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
  const entries: TimeEntry[] = useMemo(
    () =>
      Array.isArray(entriesData)
        ? entriesData
        : ((entriesData as { results?: TimeEntry[] } | undefined)?.results ?? []),
    [entriesData],
  );

  const { data: tasksData } = useQuery({
    queryKey: ["tasks-for-selector"],
    queryFn: () => tasksApi.list(),
  });
  const tasks: Task[] = useMemo(
    () => (Array.isArray(tasksData) ? tasksData : []),
    [tasksData],
  );

  const { data: projectsData } = useQuery({
    queryKey: ["projects-for-timeentries"],
    queryFn: projectsApi.list,
  });
  const projectMap = useMemo(() => {
    const m = new Map<number, string>();
    const list = Array.isArray(projectsData)
      ? projectsData
      : (projectsData as { results?: Project[] } | undefined)?.results || [];
    list.forEach((p) => m.set(p.id, p.name));
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

  const getTaskTitle = useCallback(
    (taskId: number) =>
      taskTitleMap.get(taskId) ?? t("p.ops.taskFallback", { id: taskId }),
    [taskTitleMap, t],
  );

  // Filtered entries based on date filter
  const filteredEntries = useMemo(() => {
    if (dateFilter === "all") return entries;
    const now = new Date();
    return entries.filter((e) => {
      const d = new Date(dateFromISO(e.started_at) + "T00:00:00");
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
      .filter((e) => new Date(dateFromISO(e.started_at) + "T00:00:00") >= weekStart)
      .reduce((sum, e) => sum + (secondsToMinutes(e.duration_seconds) || 0), 0);

    const monthMinutes = entries
      .filter((e) => new Date(dateFromISO(e.started_at) + "T00:00:00") >= monthStart)
      .reduce((sum, e) => sum + (secondsToMinutes(e.duration_seconds) || 0), 0);

    // Time per task (top 5) - based on filtered entries
    const perTask = new Map<number, number>();
    filteredEntries.forEach((e) => {
      perTask.set(
        e.task,
        (perTask.get(e.task) || 0) + (secondsToMinutes(e.duration_seconds) || 0),
      );
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
        perProject.set(
          projId,
          (perProject.get(projId) || 0) + (secondsToMinutes(e.duration_seconds) || 0),
        );
        projectHasEntries.add(projId);
      }
    });
    const topProjects = Array.from(perProject.entries())
      .map(([projectId, minutes]) => ({ projectId, minutes }))
      .sort((a, b) => b.minutes - a.minutes);

    const filteredTotal = filteredEntries.reduce(
      (sum, e) => sum + (secondsToMinutes(e.duration_seconds) || 0),
      0,
    );

    return {
      weekMinutes,
      monthMinutes,
      topTasks,
      topProjects,
      filteredTotal,
      hasProjectInfo: projectHasEntries.size > 0,
    };
  }, [entries, filteredEntries, taskProjectMap, getTaskTitle]);

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
        items: items.sort((a, b) =>
          dateFromISO(a.started_at) < dateFromISO(b.started_at) ? 1 : -1,
        ),
        total: items.reduce((s, e) => s + (secondsToMinutes(e.duration_seconds) || 0), 0),
      }))
      .sort((a, b) => b.total - a.total);
  }, [filteredEntries, getTaskTitle]);

  const createMut = useMutation({
    mutationFn: () =>
      timeEntriesApi.create({
        task: Number(form.task),
        duration_seconds: minutesToSeconds(Number(form.duration)),
        description: form.description,
        started_at: new Date(form.date + "T09:00:00").toISOString(),
      }),
    onSuccess: () => {
      notify.success(t("p.ops.time.created"));
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setOpen(false);
    },
    onError: () => notify.error(t("p.ops.time.createError")),
  });

  const updateMut = useMutation({
    mutationFn: () =>
      timeEntriesApi.update(editing!.id, {
        task: Number(form.task),
        duration_seconds: minutesToSeconds(Number(form.duration)),
        description: form.description,
        started_at: new Date(form.date + "T09:00:00").toISOString(),
      }),
    onSuccess: () => {
      notify.success(t("p.ops.time.updated"));
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setOpen(false);
    },
    onError: () => notify.error(t("p.ops.time.updateError")),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => timeEntriesApi.delete(id),
    onSuccess: () => {
      notify.success(t("p.ops.time.deleted"));
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      setDeleteId(null);
    },
    onError: () => notify.error(t("p.ops.time.deleteError")),
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
      duration: String(secondsToMinutes(e.duration_seconds)),
      description: e.description ?? "",
      date: dateFromISO(e.started_at) ?? "",
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
          {t("p.ops.time.title")}
        </Typography>
        <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
          {t("p.ops.time.new")}
        </Button>
      </Stack>

      {/* Estadísticas */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <BarChart3 size={20} />
          <Typography variant="subtitle1" fontWeight={700}>
            {t("p.ops.time.stats")}
          </Typography>
        </Stack>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} flexWrap="wrap">
          <Box sx={{ flex: "1 1 auto", minWidth: 140 }}>
            <Typography variant="caption" color="text.secondary">
              {t("p.ops.time.week")}
            </Typography>
            <Typography variant="h6" fontWeight={700}>
              {formatDuration(stats.weekMinutes)}
            </Typography>
          </Box>
          <Box sx={{ flex: "1 1 auto", minWidth: 140 }}>
            <Typography variant="caption" color="text.secondary">
              {t("p.ops.time.month")}
            </Typography>
            <Typography variant="h6" fontWeight={700}>
              {formatDuration(stats.monthMinutes)}
            </Typography>
          </Box>
          <Box sx={{ flex: "1 1 auto", minWidth: 140 }}>
            <Typography variant="caption" color="text.secondary">
              {t("p.ops.time.totalFiltered")}
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
              {t("p.ops.time.perTask")}
            </Typography>
            {stats.topTasks.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {t("p.ops.time.noData")}
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
                {t("p.ops.time.perProject")}
              </Typography>
              {stats.topProjects.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  {t("p.ops.time.noData")}
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
                        {projectMap.get(p.projectId) ||
                          t("p.ops.projectFallback", { id: p.projectId })}
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
          {t("p.ops.time.filterByDate")}
        </Typography>
        <ToggleButtonGroup
          size="small"
          value={dateFilter}
          exclusive
          onChange={(_, v: DateFilter | null) => v && setDateFilter(v)}
        >
          <ToggleButton value="today">{t("p.ops.time.filterToday")}</ToggleButton>
          <ToggleButton value="week">{t("p.ops.time.filterWeek")}</ToggleButton>
          <ToggleButton value="month">{t("p.ops.time.filterMonth")}</ToggleButton>
          <ToggleButton value="all">{t("p.ops.time.filterAll")}</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : filteredEntries.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Clock size={32} style={{ color: theme.palette.divider }} />
          <Typography color="text.secondary" mt={1}>
            {t("p.ops.time.empty")}
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
                  <Clock size={16} style={{ color: theme.palette.text.secondary }} />
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
                    <TableCell>{t("p.ops.time.colDuration")}</TableCell>
                    <TableCell>{t("p.ops.date")}</TableCell>
                    <TableCell>{t("p.ops.description")}</TableCell>
                    <TableCell align="right">{t("p.ops.actions")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {group.items.map((e) => (
                    <TableRow key={e.id} hover>
                      <TableCell>
                        <Chip
                          size="small"
                          icon={<Timer size={14} />}
                          label={formatDuration(secondsToMinutes(e.duration_seconds))}
                        />
                      </TableCell>
                      <TableCell>{dateFromISO(e.started_at)}</TableCell>
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
                        <Tooltip title={t("common.edit")}>
                          <IconButton size="small" onClick={() => openEdit(e)}>
                            <Pencil size={16} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={t("common.delete")}>
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
          {editing ? t("p.ops.time.editTitle") : t("p.ops.time.newTitle")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl fullWidth required error={!form.task}>
              <InputLabel id="task-select-label">
                {t("p.ops.time.taskRequired")}
              </InputLabel>
              <Select
                labelId="task-select-label"
                label={t("p.ops.time.taskRequired")}
                value={form.task}
                onChange={(e) => setForm({ ...form, task: String(e.target.value) })}
                autoFocus
                displayEmpty
              >
                <MenuItem value="" disabled>
                  {t("p.ops.time.selectTask")}
                </MenuItem>
                {tasks.map((t) => (
                  <MenuItem key={t.id} value={String(t.id)}>
                    {t.title}
                  </MenuItem>
                ))}
              </Select>
              {!form.task && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                  {t("p.ops.time.taskMandatory")}
                </Typography>
              )}
            </FormControl>
            <TextField
              label={t("p.ops.time.durationMin")}
              fullWidth
              required
              type="number"
              value={form.duration}
              onChange={(e) => setForm({ ...form, duration: e.target.value })}
            />
            <DateField
              label={t("p.ops.date")}
              required
              value={form.date}
              onChange={(v) => setForm({ ...form, date: v })}
            />
            <TextField
              label={t("p.ops.description")}
              fullWidth
              multiline
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={save}
            disabled={
              !form.task ||
              !form.duration ||
              !form.date ||
              createMut.isPending ||
              updateMut.isPending
            }
          >
            {editing ? t("common.save") : t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs">
        <DialogTitle>{t("p.ops.time.deleteTitle")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning">{t("p.ops.time.confirmDelete")}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>{t("common.cancel")}</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => deleteId && deleteMut.mutate(deleteId)}
            disabled={deleteMut.isPending}
          >
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
