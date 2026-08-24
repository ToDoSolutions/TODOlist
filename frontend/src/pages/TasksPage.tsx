import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
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
  Checkbox,
  Tooltip,
  FormControl,
  InputLabel,
  Select,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
} from "@mui/material";
import { Plus, List as ListIcon, Columns, Search, Calendar, Table as TableIcon, Trash2, Edit3, FolderInput, Bookmark, X, Sparkles } from "lucide-react";
import { tasksApi, TaskFilters, bulkOpsApi, savedSearchesApi, sprintsApi, epicsApi, searchApi } from "../api/resources";
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
import TaskTableView from "../components/TaskTableView";
import { notify } from "../notify";
import { useProject } from "../auth/ProjectContext";

interface TasksPageProps {
  projectId?: number;
  title: string;
}

export default function TasksPage({ projectId, title }: TasksPageProps) {
  const [params, setParams] = useSearchParams();
  const { project: ctxProject } = useProject();
  const effectiveProjectId = projectId ?? ctxProject?.id;
  const view = (params.get("view") as "list" | "kanban" | "calendar" | "table") || "list";
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkDialog, setBulkDialog] = useState<"update" | "moveSprint" | null>(null);
  const [bulkState, setBulkState] = useState("");
  const [bulkSprint, setBulkSprint] = useState<number | "">("");
  const [saveSearchDialog, setSaveSearchDialog] = useState(false);
  const [searchName, setSearchName] = useState("");
  const [advancedSearch, setAdvancedSearch] = useState(false);
  const qc = useQueryClient();

  const filters: TaskFilters = useMemo(
    () => ({
      project: effectiveProjectId,
      state: params.get("state") || undefined,
      priority: params.get("priority") ? Number(params.get("priority")) : undefined,
      tags: params.get("tag") ? Number(params.get("tag")) : undefined,
      sprint: params.get("sprint") ? Number(params.get("sprint")) : undefined,
      epic: params.get("epic") ? Number(params.get("epic")) : undefined,
      search: params.get("q") || undefined,
      ordering: params.get("ordering") || "-created_at",
    }),
    [effectiveProjectId, params]
  );

  const { data: tasksData, isLoading, error } = useQuery({
    queryKey: ["tasks", filters],
    queryFn: () => tasksApi.list(filters),
  });
  const tasks = Array.isArray(tasksData) ? tasksData : [];

  const { data: tagsData } = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });
  const tags = Array.isArray(tagsData) ? tagsData : [];

  const { data: sprintsData } = useQuery({
    queryKey: ["sprints"],
    queryFn: () => sprintsApi.list(),
  });
  const sprints: any[] = Array.isArray(sprintsData) ? sprintsData : (sprintsData as any)?.results || [];

  const { data: epicsData } = useQuery({
    queryKey: ["epics"],
    queryFn: epicsApi.list,
  });
  const epics: any[] = Array.isArray(epicsData) ? epicsData : (epicsData as any)?.results || [];

  const { data: savedSearches } = useQuery({
    queryKey: ["saved-searches"],
    queryFn: savedSearchesApi.list,
  });
  const savedSearchList = Array.isArray(savedSearches) ? savedSearches : [];

  const bulkUpdateMut = useMutation({
    mutationFn: ({ ids, updates }: { ids: number[]; updates: any }) => bulkOpsApi.update(ids, updates),
    onSuccess: () => { notify.success(`${selected.size} tareas actualizadas`); qc.invalidateQueries({ queryKey: ["tasks"] }); setBulkDialog(null); setSelected(new Set()); },
    onError: () => notify.error("Error en actualización en lote"),
  });

  const bulkDeleteMut = useMutation({
    mutationFn: (ids: number[]) => bulkOpsApi.delete(ids),
    onSuccess: () => { notify.success(`${selected.size} tareas eliminadas`); qc.invalidateQueries({ queryKey: ["tasks"] }); qc.invalidateQueries({ queryKey: ["projects"] }); setSelected(new Set()); },
    onError: () => notify.error("Error al eliminar en lote"),
  });

  const bulkMoveSprintMut = useMutation({
    mutationFn: ({ ids, sprintId }: { ids: number[]; sprintId: number }) => bulkOpsApi.moveSprint(ids, sprintId),
    onSuccess: () => { notify.success(`${selected.size} tareas movidas al sprint`); qc.invalidateQueries({ queryKey: ["tasks"] }); setBulkDialog(null); setSelected(new Set()); },
    onError: () => notify.error("Error al mover al sprint"),
  });

  const saveSearchMut = useMutation({
    mutationFn: (data: any) => savedSearchesApi.create(data),
    onSuccess: () => { notify.success("Búsqueda guardada"); qc.invalidateQueries({ queryKey: ["saved-searches"] }); setSaveSearchDialog(false); setSearchName(""); },
    onError: () => notify.error("No se pudo guardar la búsqueda"),
  });

  const deleteSearchMut = useMutation({
    mutationFn: (id: number) => savedSearchesApi.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["saved-searches"] }); notify.success("Búsqueda eliminada"); },
  });

  const searchMut = useMutation({
    mutationFn: (q: string) => searchApi.tasks(q),
    onSuccess: (data) => {
      const results = Array.isArray(data) ? data : data?.results || [];
      notify.info(`Búsqueda avanzada: ${results.length} resultados`);
      qc.setQueryData(["tasks", params.toString()], results);
    },
    onError: () => notify.error("Error en búsqueda avanzada"),
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

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === tasks.length) setSelected(new Set());
    else setSelected(new Set(tasks.map((t) => t.id)));
  };

  const clearSelection = () => setSelected(new Set());

  const selectedIds = Array.from(selected);

  const handleBulkUpdate = () => {
    const updates: any = {};
    if (bulkState) updates.state = bulkState;
    if (Object.keys(updates).length === 0) { notify.warning("Selecciona al menos un campo"); return; }
    bulkUpdateMut.mutate({ ids: selectedIds, updates });
  };

  const handleBulkMoveSprint = () => {
    if (bulkSprint === "") { notify.warning("Selecciona un sprint"); return; }
    bulkMoveSprintMut.mutate({ ids: selectedIds, sprintId: Number(bulkSprint) });
  };

  const handleBulkDelete = () => {
    if (!confirm(`¿Eliminar ${selected.size} tareas?`)) return;
    bulkDeleteMut.mutate(selectedIds);
  };

  const handleSaveSearch = () => {
    if (!searchName.trim()) return;
    const filters: any = {};
    if (params.get("state")) filters.state = params.get("state");
    if (params.get("priority")) filters.priority = params.get("priority");
    if (params.get("tag")) filters.tag = params.get("tag");
    if (params.get("sprint")) filters.sprint = params.get("sprint");
    if (params.get("epic")) filters.epic = params.get("epic");
    if (params.get("q")) filters.search = params.get("q");
    saveSearchMut.mutate({ name: searchName, filters: JSON.stringify(filters) });
  };

  const loadSavedSearch = (ss: any) => {
    try {
      const f = JSON.parse(ss.filters);
      const next = new URLSearchParams();
      if (f.state) next.set("state", f.state);
      if (f.priority) next.set("priority", f.priority);
      if (f.tag) next.set("tag", f.tag);
      if (f.sprint) next.set("sprint", f.sprint);
      if (f.epic) next.set("epic", f.epic);
      if (f.search) next.set("q", f.search);
      setParams(next);
    } catch { notify.error("Filtros inválidos"); }
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
          <Tooltip title="Búsqueda avanzada (full-text)">
            <IconButton
              size="small"
              color={advancedSearch ? "primary" : "default"}
              onClick={() => {
                setAdvancedSearch(!advancedSearch);
                if (!advancedSearch && params.get("q")) {
                  searchMut.mutate(params.get("q")!);
                }
              }}
            >
              <Sparkles size={16} />
            </IconButton>
          </Tooltip>
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
          <TextField
            select
            size="small"
            label="Sprint"
            value={params.get("sprint") || ""}
            onChange={(e) => setParam("sprint", e.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">Todos</MenuItem>
            {sprints.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Épica"
            value={params.get("epic") || ""}
            onChange={(e) => setParam("epic", e.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">Todas</MenuItem>
            {epics.map((e) => (
              <MenuItem key={e.id} value={e.id}>
                {e.title}
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
            <ToggleButton value="table">
              <TableIcon size={16} />
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

      {/* Saved searches */}
      {savedSearchList.length > 0 && (
        <Stack direction="row" spacing={1} mb={2} flexWrap="wrap" useFlexGap>
          <Typography variant="caption" color="text.secondary" sx={{ pt: 0.5 }}>
            Búsquedas guardadas:
          </Typography>
          {savedSearchList.map((ss: any) => (
            <Chip
              key={ss.id}
              size="small"
              label={ss.name}
              onClick={() => loadSavedSearch(ss)}
              onDelete={() => deleteSearchMut.mutate(ss.id)}
              variant="outlined"
            />
          ))}
        </Stack>
      )}

      {/* Bulk actions bar */}
      {selected.size > 0 && (
        <Paper sx={{ p: 1.5, mb: 2, display: "flex", alignItems: "center", gap: 1, bgcolor: "primary.main", color: "primary.contrastText" }}>
          <Typography variant="body2" fontWeight={600}>
            {selected.size} seleccionada{selected.size > 1 ? "s" : ""}
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button size="small" color="inherit" startIcon={<Edit3 size={14} />} onClick={() => setBulkDialog("update")}>
            Cambiar estado
          </Button>
          <Button size="small" color="inherit" startIcon={<FolderInput size={14} />} onClick={() => setBulkDialog("moveSprint")}>
            Mover a sprint
          </Button>
          <Button size="small" color="inherit" startIcon={<Trash2 size={14} />} onClick={handleBulkDelete}>
            Eliminar
          </Button>
          <IconButton size="small" color="inherit" onClick={clearSelection}>
            <X size={16} />
          </IconButton>
        </Paper>
      )}

      {/* Save search button */}
      {(params.get("state") || params.get("priority") || params.get("tag") || params.get("q")) && (
        <Box mb={2}>
          <Button size="small" startIcon={<Bookmark size={14} />} variant="text" onClick={() => setSaveSearchDialog(true)}>
            Guardar búsqueda
          </Button>
        </Box>
      )}

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
      ) : view === "table" ? (
        <TaskTableView tasks={tasks} onEdit={openEdit} />
      ) : (
        <Stack spacing={1}>
          {tasks.length > 0 && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, ml: 0.5 }}>
              <Checkbox
                size="small"
                checked={selected.size === tasks.length && tasks.length > 0}
                indeterminate={selected.size > 0 && selected.size < tasks.length}
                onChange={toggleSelectAll}
                sx={{ opacity: selected.size > 0 ? 1 : 0.5 }}
              />
              <Typography variant="caption" color="text.secondary">
                {selected.size > 0 ? `${selected.size} seleccionada${selected.size > 1 ? "s" : ""} — usa las acciones arriba` : "Seleccionar todo para acciones en lote"}
              </Typography>
            </Box>
          )}
          {tasks.map((t) => (
            <Box
              key={t.id}
              sx={{
                display: "flex",
                alignItems: "flex-start",
                gap: 0.5,
                "&:hover .select-checkbox": { opacity: 1 },
              }}
            >
              <Checkbox
                className="select-checkbox"
                size="small"
                checked={selected.has(t.id)}
                onChange={() => toggleSelect(t.id)}
                sx={{
                  mt: 0.5,
                  opacity: selected.has(t.id) ? 1 : 0,
                  transition: "opacity 0.2s",
                  color: "primary.main",
                  "&.Mui-checked": { opacity: 1 },
                }}
              />
              <Box sx={{ flex: 1 }}>
                <TaskListItem task={t} onEdit={openEdit} />
              </Box>
            </Box>
          ))}
        </Stack>
      )}

      <TaskDialog
        open={dialogOpen}
        task={editing}
        defaultProjectId={effectiveProjectId}
        onClose={() => setDialogOpen(false)}
        onSaved={onSaved}
      />

      {/* Bulk: Cambiar estado */}
      <Dialog open={bulkDialog === "update"} onClose={() => setBulkDialog(null)} fullWidth maxWidth="xs">
        <DialogTitle>Cambiar estado ({selected.size} tareas)</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel>Nuevo estado</InputLabel>
            <Select value={bulkState} label="Nuevo estado" onChange={(e) => setBulkState(e.target.value)}>
              <MenuItem value="pending">Pendiente</MenuItem>
              <MenuItem value="in_progress">En progreso</MenuItem>
              <MenuItem value="blocked">Bloqueada</MenuItem>
              <MenuItem value="completed">Completada</MenuItem>
              <MenuItem value="cancelled">Cancelada</MenuItem>
              <MenuItem value="archived">Archivada</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkDialog(null)}>Cancelar</Button>
          <Button variant="contained" onClick={handleBulkUpdate} disabled={bulkUpdateMut.isPending}>Aplicar</Button>
        </DialogActions>
      </Dialog>

      {/* Bulk: Mover a sprint */}
      <Dialog open={bulkDialog === "moveSprint"} onClose={() => setBulkDialog(null)} fullWidth maxWidth="xs">
        <DialogTitle>Mover a sprint ({selected.size} tareas)</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel>Sprint</InputLabel>
            <Select value={bulkSprint} label="Sprint" onChange={(e) => setBulkSprint(e.target.value as number | "")}>
              <MenuItem value="">Sin sprint</MenuItem>
              {sprints.map((s: any) => (
                <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkDialog(null)}>Cancelar</Button>
          <Button variant="contained" onClick={handleBulkMoveSprint} disabled={bulkMoveSprintMut.isPending}>Mover</Button>
        </DialogActions>
      </Dialog>

      {/* Guardar búsqueda */}
      <Dialog open={saveSearchDialog} onClose={() => setSaveSearchDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>Guardar búsqueda</DialogTitle>
        <DialogContent>
          <TextField
            label="Nombre"
            fullWidth
            autoFocus
            sx={{ mt: 1 }}
            value={searchName}
            onChange={(e) => setSearchName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleSaveSearch(); } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveSearchDialog(false)}>Cancelar</Button>
          <Button variant="contained" onClick={handleSaveSearch} disabled={!searchName.trim() || saveSearchMut.isPending}>Guardar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
