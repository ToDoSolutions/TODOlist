import { useState, useMemo } from "react";
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Chip,
  TextField,
  Select,
  MenuItem,
  Stack,
  Typography,
  Tooltip,
  IconButton,
  Checkbox,
} from "@mui/material";
import { Search, Download } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "../api/resources";
import { notify } from "../notify";
import {
  Task,
  TaskState,
  TaskPriority,
  TaskType,
  STATE_LABELS,
  STATE_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
  TYPE_LABELS,
  TYPE_COLORS,
  SIZE_LABELS,
} from "../types";

interface Props {
  tasks: Task[];
  onEdit: (t: Task) => void;
}

type SortField = "title" | "state" | "priority" | "due_date" | "task_type" | "story_points" | "sprint_name";
type SortDir = "asc" | "desc";

const COLUMNS = [
  { id: "title", label: "Título", width: 300, editable: false },
  { id: "state", label: "Estado", width: 130, editable: true },
  { id: "priority", label: "Prioridad", width: 120, editable: true },
  { id: "task_type", label: "Tipo", width: 120, editable: true },
  { id: "story_points", label: "SP", width: 60, editable: true },
  { id: "size", label: "Talla", width: 70, editable: true },
  { id: "sprint_name", label: "Sprint", width: 120, editable: false },
  { id: "epic_title", label: "Épica", width: 120, editable: false },
  { id: "due_date", label: "Vence", width: 110, editable: true },
] as const;

export default function TaskTableView({ tasks, onEdit }: Props) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<SortField>("priority");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selected, setSelected] = useState<number[]>([]);
  const [editing, setEditing] = useState<{ id: number; field: string; value: any } | null>(null);

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      tasksApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error("Error al actualizar"),
  });

  const filtered = useMemo(() => {
    if (!search.trim()) return tasks;
    const q = search.toLowerCase();
    return tasks.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q)
    );
  }, [tasks, search]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let aVal: any = (a as any)[sortField];
      let bVal: any = (b as any)[sortField];
      if (aVal == null) aVal = "";
      if (bVal == null) bVal = "";
      if (typeof aVal === "string") aVal = aVal.toLowerCase();
      if (typeof bVal === "string") bVal = bVal.toLowerCase();
      if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
      if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortField, sortDir]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const handleSelect = (id: number) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSelectAll = () => {
    if (selected.length === sorted.length) {
      setSelected([]);
    } else {
      setSelected(sorted.map((t) => t.id));
    }
  };

  const commitEdit = (taskId: number, field: string, value: any) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;
    const currentValue = (task as any)[field];
    if (value === currentValue) {
      setEditing(null);
      return;
    }
    updateMut.mutate({ id: taskId, data: { [field]: value } });
    setEditing(null);
  };

  const exportCSV = () => {
    const headers = COLUMNS.map((c) => c.label).join(",");
    const rows = sorted.map((t) =>
      COLUMNS.map((c) => {
        const val = (t as any)[c.id];
        return val == null ? "" : `"${String(val).replace(/"/g, '""')}"`;
      }).join(",")
    );
    const csv = [headers, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tareas.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Box>
      <Stack direction="row" spacing={1} mb={2} alignItems="center">
        <TextField
          size="small"
          placeholder="Buscar..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: <Search size={16} style={{ marginRight: 8 }} />,
          }}
          sx={{ width: 250 }}
        />
        <Typography variant="caption" color="text.secondary">
          {sorted.length} tareas
          {selected.length > 0 && ` · ${selected.length} seleccionadas`}
        </Typography>
        <Box flex={1} />
        <Tooltip title="Exportar CSV">
          <IconButton size="small" onClick={exportCSV}>
            <Download size={18} />
          </IconButton>
        </Tooltip>
      </Stack>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" sx={{ width: 40 }}>
                <Checkbox
                  size="small"
                  checked={selected.length === sorted.length && sorted.length > 0}
                  indeterminate={selected.length > 0 && selected.length < sorted.length}
                  onChange={handleSelectAll}
                />
              </TableCell>
              {COLUMNS.map((col) => (
                <TableCell
                  key={col.id}
                  sx={{ width: col.width, minWidth: col.width }}
                  sortDirection={sortField === col.id ? sortDir : false}
                >
                  <TableSortLabel
                    active={sortField === col.id}
                    direction={sortField === col.id ? sortDir : "asc"}
                    onClick={() => handleSort(col.id as SortField)}
                  >
                    {col.label}
                  </TableSortLabel>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((task) => (
              <TableRow
                key={task.id}
                hover
                selected={selected.includes(task.id)}
                sx={{ cursor: "pointer" }}
                onClick={() => onEdit(task)}
              >
                <TableCell padding="checkbox" onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    size="small"
                    checked={selected.includes(task.id)}
                    onChange={() => handleSelect(task.id)}
                  />
                </TableCell>

                {/* Título */}
                <TableCell>
                  <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: 280 }}>
                    {task.title}
                    {task.subtask_total > 0 && (
                      <Chip
                        size="small"
                        label={`${task.subtask_done}/${task.subtask_total}`}
                        sx={{ ml: 0.5, height: 16, fontSize: 10 }}
                      />
                    )}
                  </Typography>
                </TableCell>

                {/* Estado (editable) */}
                <TableCell onClick={(e) => e.stopPropagation()}>
                  {editing?.id === task.id && editing.field === "state" ? (
                    <Select
                      size="small"
                      autoFocus
                      value={task.state}
                      onChange={(e) => commitEdit(task.id, "state", e.target.value)}
                      onBlur={() => setEditing(null)}
                      sx={{ minWidth: 110 }}
                    >
                      {Object.entries(STATE_LABELS).map(([k, v]) => (
                        <MenuItem key={k} value={k}>
                          {v}
                        </MenuItem>
                      ))}
                    </Select>
                  ) : (
                    <Chip
                      size="small"
                      label={STATE_LABELS[task.state]}
                      sx={{
                        bgcolor: STATE_COLORS[task.state],
                        color: "#fff",
                        height: 20,
                        fontSize: 11,
                        cursor: "pointer",
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing({ id: task.id, field: "state", value: task.state });
                      }}
                    />
                  )}
                </TableCell>

                {/* Prioridad (editable) */}
                <TableCell onClick={(e) => e.stopPropagation()}>
                  {editing?.id === task.id && editing.field === "priority" ? (
                    <Select
                      size="small"
                      autoFocus
                      value={task.priority}
                      onChange={(e) => commitEdit(task.id, "priority", Number(e.target.value))}
                      onBlur={() => setEditing(null)}
                      sx={{ minWidth: 100 }}
                    >
                      {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
                        <MenuItem key={k} value={Number(k)}>
                          {v}
                        </MenuItem>
                      ))}
                    </Select>
                  ) : (
                    <Chip
                      size="small"
                      icon={<Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: PRIORITY_COLORS[task.priority] }} />}
                      label={PRIORITY_LABELS[task.priority]}
                      sx={{ height: 18, fontSize: 10, cursor: "pointer" }}
                      variant="outlined"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing({ id: task.id, field: "priority", value: task.priority });
                      }}
                    />
                  )}
                </TableCell>

                {/* Tipo (editable) */}
                <TableCell onClick={(e) => e.stopPropagation()}>
                  {editing?.id === task.id && editing.field === "task_type" ? (
                    <Select
                      size="small"
                      autoFocus
                      value={task.task_type}
                      onChange={(e) => commitEdit(task.id, "task_type", e.target.value)}
                      onBlur={() => setEditing(null)}
                      sx={{ minWidth: 110 }}
                    >
                      {Object.entries(TYPE_LABELS).map(([k, v]) => (
                        <MenuItem key={k} value={k}>
                          {v}
                        </MenuItem>
                      ))}
                    </Select>
                  ) : (
                    <Chip
                      size="small"
                      label={TYPE_LABELS[task.task_type]}
                      sx={{
                        height: 18,
                        fontSize: 10,
                        bgcolor: TYPE_COLORS[task.task_type],
                        color: "#fff",
                        cursor: "pointer",
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing({ id: task.id, field: "task_type", value: task.task_type });
                      }}
                    />
                  )}
                </TableCell>

                {/* Story points (editable) */}
                <TableCell onClick={(e) => e.stopPropagation()}>
                  {editing?.id === task.id && editing.field === "story_points" ? (
                    <TextField
                      size="small"
                      autoFocus
                      type="number"
                      defaultValue={task.story_points}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitEdit(task.id, "story_points", Number((e.target as HTMLInputElement).value));
                        if (e.key === "Escape") setEditing(null);
                      }}
                      onBlur={() => setEditing(null)}
                      sx={{ width: 50 }}
                    />
                  ) : (
                    <Typography
                      variant="body2"
                      sx={{ cursor: "pointer", color: task.story_points ? "text.primary" : "text.disabled" }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing({ id: task.id, field: "story_points", value: task.story_points });
                      }}
                    >
                      {task.story_points || "—"}
                    </Typography>
                  )}
                </TableCell>

                {/* Size */}
                <TableCell>
                  {task.size ? (
                    <Chip size="small" label={SIZE_LABELS[task.size as keyof typeof SIZE_LABELS]} sx={{ height: 18, fontSize: 10 }} />
                  ) : (
                    <Typography variant="body2" color="text.disabled">—</Typography>
                  )}
                </TableCell>

                {/* Sprint */}
                <TableCell>
                  {task.sprint_name ? (
                    <Chip size="small" label={task.sprint_name} sx={{ height: 18, fontSize: 10 }} variant="outlined" color="primary" />
                  ) : (
                    <Typography variant="body2" color="text.disabled">—</Typography>
                  )}
                </TableCell>

                {/* Épica */}
                <TableCell>
                  {task.epic_title ? (
                    <Typography variant="body2" noWrap sx={{ maxWidth: 100 }}>{task.epic_title}</Typography>
                  ) : (
                    <Typography variant="body2" color="text.disabled">—</Typography>
                  )}
                </TableCell>

                {/* Vence */}
                <TableCell>
                  {task.due_date ? (
                    <Typography
                      variant="body2"
                      color={
                        new Date(task.due_date) < new Date() && task.state !== "completed"
                          ? "error.main"
                          : "text.secondary"
                      }
                    >
                      {new Date(task.due_date).toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" })}
                    </Typography>
                  ) : (
                    <Typography variant="body2" color="text.disabled">—</Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {sorted.length === 0 && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length + 1} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                    No hay tareas que coincidan con la búsqueda
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
