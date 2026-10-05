import { formatDate } from "../lib/dates";
import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
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
  Menu,
  Button,
  ListItemText,
} from "@mui/material";
import { Search, Download, Columns3, Trash2 } from "lucide-react";
import Papa from "papaparse";
import { saveAs } from "file-saver";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tasksApi, bulkOpsApi, projectsApi, type ApiPayload } from "../api/resources";
import { notify } from "../notify";
import { useUiStore } from "../store/uiStore";
import { useConfirm } from "./ConfirmDialog";
import {
  Task,
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

type SortField =
  | "title"
  | "state"
  | "priority"
  | "due_date"
  | "task_type"
  | "story_points"
  | "sprint_name"
  | "project";
type SortDir = "asc" | "desc";

const COLUMNS = [
  { id: "title", label: "p.board.colTitle", width: 300, editable: false },
  { id: "state", label: "p.board.colState", width: 130, editable: true },
  { id: "priority", label: "p.board.colPriority", width: 120, editable: true },
  { id: "task_type", label: "p.board.colType", width: 120, editable: true },
  { id: "story_points", label: "p.board.colSp", width: 60, editable: true },
  { id: "size", label: "p.board.colSize", width: 70, editable: true },
  { id: "sprint_name", label: "p.board.colSprint", width: 120, editable: false },
  { id: "epic_title", label: "p.board.colEpic", width: 120, editable: false },
  { id: "project", label: "p.board.colProject", width: 140, editable: false },
  { id: "due_date", label: "p.board.colDue", width: 110, editable: true },
] as const;

export default function TaskTableView({ tasks, onEdit }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<SortField>("priority");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selected, setSelected] = useState<number[]>([]);
  const [editing, setEditing] = useState<{
    id: number;
    field: string;
    value: unknown;
  } | null>(null);
  const [colsAnchor, setColsAnchor] = useState<HTMLElement | null>(null);

  // Columnas configurables (persistidas) + densidad global
  const hiddenCols = useUiStore((s) => s.hiddenTableColumns);
  const toggleColumn = useUiStore((s) => s.toggleTableColumn);
  const density = useUiStore((s) => s.density);
  const tableSize = density === "compact" ? "small" : "medium";
  const isVisible = (id: string) => !hiddenCols.includes(id);
  const visibleColumns = COLUMNS.filter((c) => c.id === "title" || isVisible(c.id));

  // Nombres de proyecto para la columna "Proyecto" (caché compartida
  // ["projects"], misma query que TaskDialog/TaskListItem).
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
    enabled: isVisible("project"),
  });
  const projectById = useMemo(() => {
    const map = new Map<number, string>();
    if (Array.isArray(projectsData))
      for (const p of projectsData as { id: number; name: string }[])
        map.set(p.id, p.name);
    return map;
  }, [projectsData]);
  const projectLabel = (task: Task) => {
    const base = task.project
      ? (projectById.get(task.project) ?? `#${task.project}`)
      : "";
    const extra = task.extra_projects?.length ?? 0;
    return base + (extra > 0 ? ` +${extra}` : "");
  };

  const bulkUpdate = useMutation({
    mutationFn: ({ ids, data }: { ids: number[]; data: ApiPayload }) =>
      bulkOpsApi.update(ids, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setSelected([]);
      notify.success(t("p.board.tasksUpdated"));
    },
    onError: () => notify.error(t("p.board.bulkError")),
  });

  const bulkDelete = useMutation({
    mutationFn: (ids: number[]) => bulkOpsApi.delete(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setSelected([]);
      notify.success(t("p.board.tasksDeleted"));
    },
    onError: () => notify.error(t("p.board.deleteError")),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiPayload }) =>
      tasksApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => notify.error(t("p.board.updateError")),
  });

  const filtered = useMemo(() => {
    if (!search.trim()) return tasks;
    const q = search.toLowerCase();
    return tasks.filter(
      (t) => t.title.toLowerCase().includes(q) || t.description.toLowerCase().includes(q),
    );
  }, [tasks, search]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const aRaw = (a as unknown as Record<string, unknown>)[sortField];
      const bRaw = (b as unknown as Record<string, unknown>)[sortField];
      const aNorm = typeof aRaw === "string" ? aRaw.toLowerCase() : aRaw;
      const bNorm = typeof bRaw === "string" ? bRaw.toLowerCase() : bRaw;
      const cmp =
        typeof aNorm === "number" && typeof bNorm === "number"
          ? aNorm - bNorm
          : String(aNorm ?? "").localeCompare(String(bNorm ?? ""));
      return sortDir === "asc" ? cmp : -cmp;
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
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const handleSelectAll = () => {
    if (selected.length === sorted.length) {
      setSelected([]);
    } else {
      setSelected(sorted.map((t) => t.id));
    }
  };

  const commitEdit = (taskId: number, field: string, value: unknown) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;
    const currentValue = (task as unknown as Record<string, unknown>)[field];
    if (value === currentValue) {
      setEditing(null);
      return;
    }
    updateMut.mutate({ id: taskId, data: { [field]: value } });
    setEditing(null);
  };

  // CSV export canónico: papaparse (escapado correcto) + file-saver (descarga)
  const exportCSV = () => {
    const csv = Papa.unparse(
      sorted.map((task) => {
        const row: Record<string, unknown> = {};
        for (const c of visibleColumns)
          row[t(c.label)] =
            c.id === "project"
              ? projectLabel(task)
              : ((task as unknown as Record<string, unknown>)[c.id] ?? "");
        return row;
      }),
    );
    saveAs(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
      `tareas-${new Date().toISOString().slice(0, 10)}.csv`,
    );
  };

  return (
    <Box>
      <Stack direction="row" spacing={1} mb={2} alignItems="center">
        <TextField
          size="small"
          placeholder={t("p.board.searchPlaceholder")}
          inputProps={{ "aria-label": t("p.board.searchPlaceholder") }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: <Search size={16} style={{ marginRight: 8 }} />,
          }}
          sx={{ width: 250 }}
        />
        <Typography variant="caption" color="text.secondary">
          {sorted.length} {t("common.tasks")}
          {selected.length > 0 &&
            ` ${t("p.board.selectedSuffix", { count: selected.length })}`}
        </Typography>
        <Box flex={1} />
        <Tooltip title={t("p.board.columns")}>
          <IconButton
            size="small"
            onClick={(e) => setColsAnchor(e.currentTarget)}
            aria-label={t("p.board.configureColumns")}
          >
            <Columns3 size={18} />
          </IconButton>
        </Tooltip>
        <Tooltip title={t("p.board.exportCsv")}>
          <IconButton size="small" onClick={exportCSV}>
            <Download size={18} />
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={colsAnchor}
          open={!!colsAnchor}
          onClose={() => setColsAnchor(null)}
        >
          <MenuItem disabled dense>
            <ListItemText
              primaryTypographyProps={{ variant: "caption", fontWeight: 700 }}
            >
              {t("p.board.visibleColumns")}
            </ListItemText>
          </MenuItem>
          {COLUMNS.filter((c) => c.id !== "title").map((c) => (
            <MenuItem key={c.id} dense onClick={() => toggleColumn(c.id)}>
              <Checkbox size="small" checked={isVisible(c.id)} sx={{ p: 0.5 }} />
              <ListItemText primary={t(c.label)} />
            </MenuItem>
          ))}
        </Menu>
      </Stack>

      {/* Barra de acciones masivas al seleccionar filas */}
      {selected.length > 0 && (
        <Paper
          variant="outlined"
          sx={{
            mb: 1,
            p: 1,
            display: "flex",
            alignItems: "center",
            gap: 1,
            borderColor: "primary.light",
            bgcolor: "action.hover",
          }}
        >
          <Typography variant="body2" fontWeight={600}>
            {t("p.board.selectedTasks", { count: selected.length })}
          </Typography>
          <Select
            size="small"
            displayEmpty
            value=""
            onChange={(e) =>
              e.target.value &&
              bulkUpdate.mutate({ ids: selected, data: { state: e.target.value } })
            }
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="" disabled>
              {t("p.board.changeState")}
            </MenuItem>
            {Object.entries(STATE_LABELS).map(([k, v]) => (
              <MenuItem key={k} value={k}>
                {v}
              </MenuItem>
            ))}
          </Select>
          <Button
            size="small"
            color="error"
            startIcon={<Trash2 size={14} />}
            onClick={async () => {
              if (await confirm(t("p.board.confirmDelete", { count: selected.length })))
                bulkDelete.mutate(selected);
            }}
          >
            {t("common.delete")}
          </Button>
          <Box flex={1} />
          <Button size="small" onClick={() => setSelected([])}>
            {t("p.board.deselect")}
          </Button>
        </Paper>
      )}

      <TableContainer component={Paper} variant="outlined" sx={{ overflowX: "auto" }}>
        <Table size={tableSize} stickyHeader>
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
              {visibleColumns.map((col) => (
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
                    {t(col.label)}
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
                  <Typography
                    variant="body2"
                    fontWeight={600}
                    noWrap
                    sx={{ maxWidth: 280 }}
                  >
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
                {isVisible("state") && (
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
                          color: "common.white",
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
                )}

                {/* Prioridad (editable) */}
                {isVisible("priority") && (
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {editing?.id === task.id && editing.field === "priority" ? (
                      <Select
                        size="small"
                        autoFocus
                        value={task.priority}
                        onChange={(e) =>
                          commitEdit(task.id, "priority", Number(e.target.value))
                        }
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
                        icon={
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: "50%",
                              bgcolor: PRIORITY_COLORS[task.priority],
                            }}
                          />
                        }
                        label={PRIORITY_LABELS[task.priority]}
                        sx={{ height: 18, fontSize: 10, cursor: "pointer" }}
                        variant="outlined"
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditing({
                            id: task.id,
                            field: "priority",
                            value: task.priority,
                          });
                        }}
                      />
                    )}
                  </TableCell>
                )}

                {/* Tipo (editable) */}
                {isVisible("task_type") && (
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
                          color: "common.white",
                          cursor: "pointer",
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditing({
                            id: task.id,
                            field: "task_type",
                            value: task.task_type,
                          });
                        }}
                      />
                    )}
                  </TableCell>
                )}

                {/* Story points (editable) */}
                {isVisible("story_points") && (
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {editing?.id === task.id && editing.field === "story_points" ? (
                      <TextField
                        size="small"
                        autoFocus
                        type="number"
                        defaultValue={task.story_points}
                        onKeyDown={(e) => {
                          if (e.key === "Enter")
                            commitEdit(
                              task.id,
                              "story_points",
                              Number((e.target as HTMLInputElement).value),
                            );
                          if (e.key === "Escape") setEditing(null);
                        }}
                        onBlur={() => setEditing(null)}
                        sx={{ width: 50 }}
                      />
                    ) : (
                      <Typography
                        variant="body2"
                        sx={{
                          cursor: "pointer",
                          color: task.story_points ? "text.primary" : "text.disabled",
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditing({
                            id: task.id,
                            field: "story_points",
                            value: task.story_points,
                          });
                        }}
                      >
                        {task.story_points || "—"}
                      </Typography>
                    )}
                  </TableCell>
                )}

                {/* Size */}
                {isVisible("size") && (
                  <TableCell>
                    {task.size ? (
                      <Chip
                        size="small"
                        label={SIZE_LABELS[task.size as keyof typeof SIZE_LABELS]}
                        sx={{ height: 18, fontSize: 10 }}
                      />
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                )}

                {/* Sprint */}
                {isVisible("sprint_name") && (
                  <TableCell>
                    {task.sprint_name ? (
                      <Chip
                        size="small"
                        label={task.sprint_name}
                        sx={{ height: 18, fontSize: 10 }}
                        variant="outlined"
                        color="primary"
                      />
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                )}

                {/* Épica */}
                {isVisible("epic_title") && (
                  <TableCell>
                    {task.epic_title ? (
                      <Typography variant="body2" noWrap sx={{ maxWidth: 100 }}>
                        {task.epic_title}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                )}

                {/* Proyecto (canónico + "+N" por hogares extra) */}
                {isVisible("project") && (
                  <TableCell>
                    {task.project ? (
                      <Tooltip
                        title={
                          (task.extra_projects?.length ?? 0) > 0
                            ? (task.extra_projects ?? [])
                                .map((id) => projectById.get(id) ?? `#${id}`)
                                .join(", ")
                            : ""
                        }
                      >
                        <Typography variant="body2" noWrap sx={{ maxWidth: 130 }}>
                          {projectLabel(task)}
                        </Typography>
                      </Tooltip>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                )}

                {/* Vence */}
                {isVisible("due_date") && (
                  <TableCell>
                    {task.due_date ? (
                      <Typography
                        variant="body2"
                        color={
                          new Date(task.due_date) < new Date() &&
                          task.state !== "completed"
                            ? "error.main"
                            : "text.secondary"
                        }
                      >
                        {formatDate(task.due_date)}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
            {sorted.length === 0 && (
              <TableRow>
                <TableCell colSpan={visibleColumns.length + 1} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                    {t("p.board.noMatchingTasks")}
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
