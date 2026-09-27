import { useMemo, useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
  Menu,
  List,
  ListItem,
  ListItemText,
  useTheme,
  Collapse,
  Badge,
} from "@mui/material";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState, EmptyFilterState } from "../components/ui/states";
import {
  TaskListSkeleton,
  KanbanSkeleton,
  TableSkeleton,
} from "../components/ui/skeletons";
import {
  Plus,
  List as ListIcon,
  Columns,
  Search,
  Calendar,
  Table as TableIcon,
  Trash2,
  Edit3,
  FolderInput,
  Bookmark,
  X,
  Sparkles,
  Download,
  Zap,
  ListTree,
  LayoutList,
  ArrowUp,
  ArrowDown,
  Pencil,
} from "lucide-react";
import Papa from "papaparse";
import { saveAs } from "file-saver";
import { format, addDays } from "date-fns";
import {
  tasksApi,
  TaskFilters,
  bulkOpsApi,
  savedSearchesApi,
  sprintsApi,
  epicsApi,
  searchApi,
  projectsApi,
  type ApiPayload,
  type Sprint,
  type Epic,
  type SavedSearch,
} from "../api/resources";
import { parseQuickAdd } from "../lib/quickAdd";
import { createFromQuickAdd } from "../api/featTask";
import { tagsApi } from "../api/resources";
import { sectionsApi, type ProjectSection } from "../api/featSect";
import { Task, TaskPriority, TaskState } from "../types";
import TaskDialog from "../components/TaskDialog";
import { DateField } from "../components/DateField";
import TaskRows, { type TaskGroup } from "../components/TaskRows";
import KanbanBoard from "../components/KanbanBoard";
import CalendarView from "../components/CalendarView";
import TaskTableView from "../components/TaskTableView";
import { notify } from "../notify";
import { useConfirm } from "../components/ConfirmDialog";
import { useProject } from "../auth/ProjectContext";
import { useUiStore } from "../store/uiStore";

// task.state.* usa la clave in_review para el estado API "review".
const STATE_I18N_KEYS: Record<TaskState, string> = {
  backlog: "task.state.backlog",
  pending: "task.state.pending",
  in_progress: "task.state.in_progress",
  blocked: "task.state.blocked",
  review: "task.state.in_review",
  completed: "task.state.completed",
  cancelled: "task.state.cancelled",
  archived: "task.state.archived",
};

interface TasksPageProps {
  projectId?: number;
  title: string;
  /** Bandeja de entrada real: solo tareas sin clasificar (sin proyecto). */
  inbox?: boolean;
  /** Vista dedicada de favoritos (estrella del usuario). */
  favoritesOnly?: boolean;
  /** Vista dedicada de tareas completadas (archivo tipo Todoist). */
  completedOnly?: boolean;
  /** Deep link: abre el panel de esta tarea al montar. */
  openTaskId?: number;
}

export default function TasksPage({
  projectId,
  title,
  inbox,
  favoritesOnly,
  completedOnly,
  openTaskId,
}: TasksPageProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [params, setParams] = useSearchParams();
  const { project: ctxProject } = useProject();
  const effectiveProjectId = inbox ? undefined : (projectId ?? ctxProject?.id);
  // Vista: URL explícita > preferencia persistida por contexto > lista
  const viewContext = inbox
    ? "inbox"
    : favoritesOnly
      ? "favorites"
      : completedOnly
        ? "completed"
        : effectiveProjectId
          ? `project-${effectiveProjectId}`
          : "global";
  const taskViews = useUiStore((s) => s.taskViews);
  const setTaskView = useUiStore((s) => s.setTaskView);
  const urlView = params.get("view") as "list" | "kanban" | "calendar" | "table" | null;
  const view = urlView || taskViews[viewContext] || "list";
  const markKanbanVisited = useUiStore((s) => s.markKanbanVisited);
  useEffect(() => {
    if (view === "kanban") markKanbanVisited();
  }, [view, markKanbanVisited]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkDate, setBulkDate] = useState("");
  const [bulkPriority, setBulkPriority] = useState<string>("");
  const [bulkDialog, setBulkDialog] = useState<"update" | "moveSprint" | null>(null);
  const [bulkState, setBulkState] = useState("");
  const [bulkSprint, setBulkSprint] = useState<number | "">("");
  const [saveSearchDialog, setSaveSearchDialog] = useState(false);
  const [searchName, setSearchName] = useState("");
  const [editSearchId, setEditSearchId] = useState<number | null>(null);
  const [editSearchName, setEditSearchName] = useState("");
  const [advancedSearch, setAdvancedSearch] = useState(false);
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [quickAddText, setQuickAddText] = useState("");
  const [sectionsDialog, setSectionsDialog] = useState(false);
  const [newSectionName, setNewSectionName] = useState("");
  const [renamingSection, setRenamingSection] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const qc = useQueryClient();
  const confirm = useConfirm();
  // Último checkbox clicado — base para la selección por rango con Shift+clic.
  const lastSelectedRef = useRef<number | null>(null);

  const filters: TaskFilters = useMemo(
    () => ({
      project: effectiveProjectId,
      no_project: inbox ? "true" : undefined,
      favorite: favoritesOnly ? "true" : undefined,
      state: completedOnly ? "completed" : params.get("state") || undefined,
      priority: params.get("priority") ? Number(params.get("priority")) : undefined,
      tags: params.get("tag") ? Number(params.get("tag")) : undefined,
      sprint: params.get("sprint") ? Number(params.get("sprint")) : undefined,
      epic: params.get("epic") ? Number(params.get("epic")) : undefined,
      search: params.get("q") || undefined,
      ordering: params.get("ordering") || "-created_at",
      overdue: params.get("overdue") || undefined,
      no_due: params.get("no_due") || undefined,
      mine: params.get("mine") || undefined,
      is_milestone: params.get("is_milestone") || undefined,
      due_after: params.get("due_after") || undefined,
      due_before: params.get("due_before") || undefined,
    }),
    [effectiveProjectId, params, inbox, favoritesOnly, completedOnly],
  );

  // Presets rápidos estilo Todoist: vencidas / hoy / esta semana /
  // sin fecha / hitos. Un chip activa su combinación de params; al
  // desactivarse se limpian solo las claves del preset.
  const todayStr = format(new Date(), "yyyy-MM-dd");
  const weekEndStr = format(addDays(new Date(), 7), "yyyy-MM-dd");
  const presets: { id: string; label: string; active: boolean; toggle: () => void }[] = [
    {
      id: "mine",
      label: t("p.work.tasks.preset.mine"),
      active: params.get("mine") === "true",
      toggle: () => setParam("mine", params.get("mine") === "true" ? null : "true"),
    },
    {
      id: "overdue",
      label: t("p.work.tasks.preset.overdue"),
      active: params.get("overdue") === "true",
      toggle: () => setParam("overdue", params.get("overdue") === "true" ? null : "true"),
    },
    {
      id: "today",
      label: t("p.work.tasks.preset.today"),
      active:
        params.get("due_after") === todayStr && params.get("due_before") === todayStr,
      toggle: () => {
        const next = new URLSearchParams(params);
        const on =
          params.get("due_after") === todayStr && params.get("due_before") === todayStr;
        if (on) {
          next.delete("due_after");
          next.delete("due_before");
        } else {
          next.set("due_after", todayStr);
          next.set("due_before", todayStr);
        }
        setParams(next);
      },
    },
    {
      id: "week",
      label: t("p.work.tasks.preset.week"),
      active:
        params.get("due_after") === todayStr && params.get("due_before") === weekEndStr,
      toggle: () => {
        const next = new URLSearchParams(params);
        const on =
          params.get("due_after") === todayStr && params.get("due_before") === weekEndStr;
        if (on) {
          next.delete("due_after");
          next.delete("due_before");
        } else {
          next.set("due_after", todayStr);
          next.set("due_before", weekEndStr);
        }
        setParams(next);
      },
    },
    {
      id: "no_due",
      label: t("p.work.tasks.preset.noDate"),
      active: params.get("no_due") === "true",
      toggle: () => setParam("no_due", params.get("no_due") === "true" ? null : "true"),
    },
    {
      id: "milestones",
      label: t("p.work.tasks.preset.milestones"),
      active: params.get("is_milestone") === "true",
      toggle: () =>
        setParam("is_milestone", params.get("is_milestone") === "true" ? null : "true"),
    },
  ];

  const {
    data: tasksData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["tasks", filters],
    queryFn: () => tasksApi.list(filters),
  });
  const tasks = useMemo(() => (Array.isArray(tasksData) ? tasksData : []), [tasksData]);

  const { data: tagsData } = useQuery({
    queryKey: ["tags"],
    queryFn: tagsApi.list,
  });
  const tags = Array.isArray(tagsData) ? tagsData : [];

  const { data: sprintsData } = useQuery({
    queryKey: ["sprints"],
    queryFn: () => sprintsApi.list(),
  });
  const sprints: Sprint[] = Array.isArray(sprintsData)
    ? sprintsData
    : (sprintsData as { results?: Sprint[] } | undefined)?.results || [];

  const { data: epicsData } = useQuery({
    queryKey: ["epics"],
    queryFn: epicsApi.list,
  });
  const epics: Epic[] = Array.isArray(epicsData)
    ? epicsData
    : (epicsData as { results?: Epic[] } | undefined)?.results || [];

  const { data: savedSearches } = useQuery({
    queryKey: ["saved-searches"],
    queryFn: savedSearchesApi.list,
  });
  const savedSearchList = Array.isArray(savedSearches) ? savedSearches : [];

  // Agrupación por secciones: ?group=sections en la URL (consistente con el
  // resto de estado URL-driven). Solo aplica a la vista lista de un proyecto.
  const groupBySections =
    params.get("group") === "sections" && view === "list" && !!effectiveProjectId;

  const { data: sectionsData } = useQuery({
    queryKey: ["project-sections", effectiveProjectId],
    queryFn: () => sectionsApi.list(effectiveProjectId!),
    enabled: !!effectiveProjectId && (groupBySections || sectionsDialog),
  });
  const sections: ProjectSection[] = useMemo(
    () => [...(sectionsData ?? [])].sort((a, b) => a.order - b.order),
    [sectionsData],
  );

  // Proyectos para el token #nombre de la captura rápida
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });
  const projects = Array.isArray(projectsData) ? projectsData : [];

  const quickAddMut = useMutation({
    mutationFn: (text: string) => {
      const parsed = parseQuickAdd(text, { projects });
      if (!parsed) return Promise.reject(new Error("empty-title"));
      return createFromQuickAdd(parsed, tags);
    },
    onSuccess: () => {
      notify.success(t("p.taskx.quickAdd.created"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["tags"] });
      setQuickAddText("");
    },
    onError: (e) =>
      notify.error(
        e instanceof Error && e.message === "empty-title"
          ? t("p.taskx.quickAdd.emptyTitle")
          : t("p.taskx.quickAdd.error"),
      ),
  });

  const bulkUpdateMut = useMutation({
    mutationFn: ({ ids, updates }: { ids: number[]; updates: ApiPayload }) =>
      bulkOpsApi.update(ids, updates),
    onSuccess: () => {
      notify.success(t("p.work.tasks.bulkUpdated", { count: selected.size }));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setBulkDialog(null);
      setSelected(new Set());
    },
    onError: () => notify.error(t("p.work.tasks.bulkUpdateError")),
  });

  const bulkDeleteMut = useMutation({
    mutationFn: (ids: number[]) => bulkOpsApi.delete(ids),
    onSuccess: () => {
      notify.success(t("p.work.tasks.bulkDeleted", { count: selected.size }));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      setSelected(new Set());
    },
    onError: () => notify.error(t("p.work.tasks.bulkDeleteError")),
  });

  const bulkMoveSprintMut = useMutation({
    mutationFn: ({ ids, sprintId }: { ids: number[]; sprintId: number }) =>
      bulkOpsApi.moveSprint(ids, sprintId),
    onSuccess: () => {
      notify.success(t("p.work.tasks.bulkMovedSprint", { count: selected.size }));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      setBulkDialog(null);
      setSelected(new Set());
    },
    onError: () => notify.error(t("p.work.tasks.bulkMoveSprintError")),
  });

  const saveSearchMut = useMutation({
    mutationFn: (data: ApiPayload) => savedSearchesApi.create(data),
    onSuccess: () => {
      notify.success(t("p.work.tasks.searchSaved"));
      qc.invalidateQueries({ queryKey: ["saved-searches"] });
      setSaveSearchDialog(false);
      setSearchName("");
    },
    onError: () => notify.error(t("p.work.tasks.searchSaveError")),
  });

  const deleteSearchMut = useMutation({
    mutationFn: (id: number) => savedSearchesApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["saved-searches"] });
      notify.success(t("p.work.tasks.searchDeleted"));
    },
  });

  const updateSearchMut = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      savedSearchesApi.update(id, { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["saved-searches"] });
      notify.success(t("p.work.tasks.searchRenamed"));
      setEditSearchId(null);
      setEditSearchName("");
    },
    onError: () => notify.error(t("p.work.tasks.searchRenameError")),
  });

  // --- Secciones del proyecto (CRUD + reorder desde el diálogo "Secciones") ---
  const invalidateSections = () => {
    qc.invalidateQueries({ queryKey: ["project-sections", effectiveProjectId] });
    // section_name de las tareas puede quedar obsoleto tras renombrar/borrar
    qc.invalidateQueries({ queryKey: ["tasks"] });
  };

  const createSectionMut = useMutation({
    mutationFn: (name: string) =>
      sectionsApi.create({ project: effectiveProjectId!, name }),
    onSuccess: () => {
      invalidateSections();
      setNewSectionName("");
    },
    onError: () => notify.error(t("p.taskx.sections.createError")),
  });

  const renameSectionMut = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      sectionsApi.update(id, { name }),
    onSuccess: () => {
      invalidateSections();
      setRenamingSection(null);
    },
    onError: () => notify.error(t("p.taskx.sections.updateError")),
  });

  const deleteSectionMut = useMutation({
    mutationFn: (id: number) => sectionsApi.remove(id),
    onSuccess: invalidateSections,
    onError: () => notify.error(t("p.taskx.sections.deleteError")),
  });

  const reorderSectionsMut = useMutation({
    mutationFn: (sectionIds: number[]) =>
      sectionsApi.reorder(effectiveProjectId!, sectionIds),
    onSuccess: invalidateSections,
    onError: () => notify.error(t("p.taskx.sections.reorderError")),
  });

  /** Reorden por flechas ↑↓: swap del índice y POST del orden completo. */
  const moveSection = (index: number, dir: -1 | 1) => {
    const ids = sections.map((s) => s.id);
    const target = index + dir;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target]!, ids[index]!];
    reorderSectionsMut.mutate(ids);
  };

  const commitRename = (section: ProjectSection) => {
    const name = renameValue.trim();
    if (name && name !== section.name) renameSectionMut.mutate({ id: section.id, name });
    else setRenamingSection(null);
  };

  const searchMut = useMutation({
    mutationFn: (q: string) => searchApi.tasks(q),
    onSuccess: (data) => {
      const results = Array.isArray(data) ? data : data?.results || [];
      notify.info(t("p.work.tasks.advSearchResults", { count: results.length }));
      qc.setQueryData(["tasks", params.toString()], results);
    },
    onError: () => notify.error(t("p.work.tasks.advSearchError")),
  });

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
    setParams(next);
    if (key === "view" && value) setTaskView(viewContext, value as "list");
  };

  // El botón global "Crear" navega con ?new=1 → el diálogo se deriva del
  // param (sin setState en effect). Al cerrarse se limpia la URL.
  const wantsNew = params.get("new") === "1";
  const dialogVisible = dialogOpen || wantsNew;
  const closeDialog = () => {
    setDialogOpen(false);
    if (wantsNew) {
      const next = new URLSearchParams(params);
      next.delete("new");
      setParams(next, { replace: true });
    }
  };

  // Deep link /app/tasks/:id → abre el panel de la tarea
  useEffect(() => {
    if (!openTaskId) return;
    let cancelled = false;
    tasksApi
      .get(openTaskId)
      .then((t) => {
        if (!cancelled) {
          setEditing(t);
          setDialogOpen(true);
        }
      })
      .catch(() => {
        if (!cancelled) notify.error(t("p.work.tasks.openTaskError"));
      });
    return () => {
      cancelled = true;
    };
  }, [openTaskId, t]);

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
    closeDialog();
  };

  /**
   * Selección individual; con Shift+clic selecciona el rango inclusivo
   * entre el último id clicado y el actual (unión sobre `selected`),
   * siguiendo el orden visible de `tasks`.
   */
  const toggleSelect = (id: number, shiftKey = false) => {
    if (shiftKey && lastSelectedRef.current !== null) {
      const ids = tasks.map((task) => task.id);
      const from = ids.indexOf(lastSelectedRef.current);
      const to = ids.indexOf(id);
      if (from >= 0 && to >= 0) {
        const [lo, hi] = from < to ? [from, to] : [to, from];
        setSelected((prev) => {
          const next = new Set(prev);
          for (const rangeId of ids.slice(lo, hi + 1)) next.add(rangeId);
          return next;
        });
      }
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
    }
    lastSelectedRef.current = id;
  };

  const toggleSelectAll = () => {
    if (selected.size === tasks.length) setSelected(new Set());
    else setSelected(new Set(tasks.map((t) => t.id)));
  };

  const clearSelection = () => setSelected(new Set());

  const [exportAnchor, setExportAnchor] = useState<HTMLElement | null>(null);

  const exportCsv = () => {
    const csv = Papa.unparse(
      tasks.map((t) => ({
        id: t.id,
        titulo: t.title,
        estado: t.state,
        prioridad: t.priority,
        proyecto: t.project ?? "",
        sprint: t.sprint_name ?? "",
        asignado: t.assignee_email ?? "",
        vencimiento: t.due_date ?? "",
        creada: t.created_at ?? "",
      })),
    );
    saveAs(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
      `tareas-${new Date().toISOString().slice(0, 10)}.csv`,
    );
    setExportAnchor(null);
    notify.success(t("p.work.tasks.exportedCsv", { count: tasks.length }));
  };

  const exportIcal = () => {
    window.open("/api/tasks/calendar.ics/", "_blank");
    setExportAnchor(null);
  };

  const selectedIds = Array.from(selected);

  const handleBulkUpdate = () => {
    const updates: ApiPayload = {};
    if (bulkState) updates.state = bulkState;
    if (bulkDate) updates.due_date = bulkDate;
    if (bulkPriority) updates.priority = Number(bulkPriority);
    if (Object.keys(updates).length === 0) {
      notify.warning(t("p.work.tasks.selectFieldWarning"));
      return;
    }
    bulkUpdateMut.mutate({ ids: selectedIds, updates });
  };

  const handleBulkMoveSprint = () => {
    if (bulkSprint === "") {
      notify.warning(t("p.work.tasks.selectSprintWarning"));
      return;
    }
    bulkMoveSprintMut.mutate({ ids: selectedIds, sprintId: Number(bulkSprint) });
  };

  const handleBulkDelete = async () => {
    if (
      !(await confirm(t("p.work.tasks.confirmBulkDelete", { count: selected.size }), {
        confirmLabel: t("p.work.tasks.confirmBulkDeleteLabel"),
      }))
    )
      return;
    bulkDeleteMut.mutate(selectedIds);
  };

  const handleSaveSearch = () => {
    if (!searchName.trim()) return;
    const filters: Record<string, unknown> = {};
    if (params.get("state")) filters.state = params.get("state");
    if (params.get("priority")) filters.priority = params.get("priority");
    if (params.get("tag")) filters.tag = params.get("tag");
    if (params.get("sprint")) filters.sprint = params.get("sprint");
    if (params.get("epic")) filters.epic = params.get("epic");
    if (params.get("q")) filters.search = params.get("q");
    saveSearchMut.mutate({ name: searchName, filters: JSON.stringify(filters) });
  };

  const loadSavedSearch = (ss: SavedSearch) => {
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
    } catch {
      notify.error(t("p.work.tasks.invalidFilters"));
    }
  };

  // Filtros activos como chips removibles (no controles permanentes)
  const activeFilters: { key: string; label: string }[] = [];
  if (params.get("state")) {
    const stateParam = params.get("state")!;
    const stateKey = STATE_I18N_KEYS[stateParam as TaskState];
    activeFilters.push({
      key: "state",
      label: t("p.work.tasks.filterState", {
        value: stateKey ? t(stateKey) : stateParam,
      }),
    });
  }
  if (params.get("priority")) {
    const prParam = Number(params.get("priority")) as TaskPriority;
    activeFilters.push({
      key: "priority",
      label: t("p.work.tasks.filterPriority", {
        value:
          prParam >= 0 && prParam <= 5
            ? t(`p.work.priority.p${prParam}`)
            : String(params.get("priority")),
      }),
    });
  }
  if (params.get("tag")) {
    const tag = tags.find((x) => x.id === Number(params.get("tag")));
    activeFilters.push({
      key: "tag",
      label: t("p.work.tasks.filterTag", {
        value: tag?.name ?? params.get("tag"),
      }),
    });
  }
  if (params.get("sprint")) {
    const sp = sprints.find((s) => s.id === Number(params.get("sprint")));
    activeFilters.push({
      key: "sprint",
      label: t("p.work.tasks.filterSprint", {
        value: sp?.name ?? params.get("sprint"),
      }),
    });
  }
  if (params.get("epic")) {
    const ep = epics.find((e) => e.id === Number(params.get("epic")));
    activeFilters.push({
      key: "epic",
      label: t("p.work.tasks.filterEpic", {
        value: ep?.title ?? params.get("epic"),
      }),
    });
  }
  if (params.get("q")) {
    activeFilters.push({
      key: "q",
      label: t("p.work.tasks.filterQuery", { value: params.get("q") }),
    });
  }

  const clearAllFilters = () => {
    const next = new URLSearchParams();
    if (params.get("view")) next.set("view", params.get("view")!);
    setParams(next);
  };

  const advancedCount = [
    params.get("tag"),
    params.get("sprint"),
    params.get("epic"),
  ].filter(Boolean).length;

  // Agrupación por sección (vista lista de un proyecto): "Sin sección"
  // primero — patrón bandeja de Todoist — luego las secciones en `order`.
  const sectionGroups = useMemo<TaskGroup[] | undefined>(() => {
    if (!groupBySections) return undefined;
    const bySection = new Map<number, Task[]>();
    const unsectioned: Task[] = [];
    for (const task of tasks) {
      if (task.section != null) {
        const arr = bySection.get(task.section);
        if (arr) arr.push(task);
        else bySection.set(task.section, [task]);
      } else {
        unsectioned.push(task);
      }
    }
    const groups: TaskGroup[] = [
      { id: null, name: t("p.taskx.sections.noSection"), tasks: unsectioned },
    ];
    for (const s of sections) {
      groups.push({ id: s.id, name: s.name, tasks: bySection.get(s.id) ?? [] });
      bySection.delete(s.id);
    }
    // Tareas que referencian una sección que ya no existe en el proyecto
    // (datos obsoletos): se muestran en un grupo residual con su nombre.
    for (const [sid, arr] of bySection) {
      groups.push({
        id: sid,
        name: arr[0]?.section_name ?? `#${sid}`,
        tasks: arr,
      });
    }
    return groups;
  }, [groupBySections, tasks, sections, t]);

  // Navegación por teclado en la vista lista (patrón Linear/Todoist):
  // j/k (o ↑/↓) mueven el foco entre filas, x alterna selección, e/Enter
  // abren la tarea, c crea una nueva, Esc quita el foco. Se desactiva
  // cuando el target es un control editable o hay un diálogo abierto.
  const flatTasks = useMemo(
    () =>
      groupBySections && sectionGroups ? sectionGroups.flatMap((g) => g.tasks) : tasks,
    [groupBySections, sectionGroups, tasks],
  );
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const focusedTask =
    focusedIdx >= 0 && focusedIdx < flatTasks.length ? flatTasks[focusedIdx] : undefined;

  useEffect(() => {
    if (view !== "list") return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (
        el?.closest(
          'input, textarea, select, [contenteditable="true"], .MuiDialog-root, .MuiMenu-root, .MuiPopover-root',
        )
      )
        return;
      if (dialogVisible || bulkDialog || !flatTasks.length) return;
      const clamped = Math.min(Math.max(focusedIdx, -1), flatTasks.length - 1);
      const cur = clamped >= 0 ? flatTasks[clamped] : undefined;
      switch (e.key) {
        case "j":
        case "ArrowDown":
          e.preventDefault();
          setFocusedIdx(Math.min(flatTasks.length - 1, clamped + 1));
          break;
        case "k":
        case "ArrowUp":
          e.preventDefault();
          setFocusedIdx(Math.max(0, clamped - 1));
          break;
        case "x":
          if (cur) toggleSelect(cur.id);
          break;
        case "e":
        case "Enter":
          if (cur) {
            e.preventDefault();
            openEdit(cur);
          }
          break;
        case "c":
          e.preventDefault();
          openNew();
          break;
        case "Escape":
          setFocusedIdx(-1);
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Mantener la fila enfocada visible al navegar con j/k.
  useEffect(() => {
    const id = focusedTask?.id;
    if (id == null) return;
    document
      .querySelector(`[data-task-id="${id}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [focusedTask]);

  return (
    <Box>
      <PageHeader
        title={inbox ? t("nav.inbox") : title || t("p.taskx.palette.navTasks")}
        description={t("p.work.tasks.count", { count: tasks.length })}
        breadcrumbs={
          effectiveProjectId && ctxProject
            ? [
                { label: t("nav.projects"), to: "/app/projects" },
                { label: ctxProject.name },
                { label: t("p.work.tasks.breadcrumbTasks") },
              ]
            : undefined
        }
        actions={
          <>
            {effectiveProjectId != null && (
              <Tooltip title={t("p.taskx.sections.manage")}>
                <IconButton
                  onClick={() => setSectionsDialog(true)}
                  aria-label={t("p.taskx.sections.manage")}
                >
                  <LayoutList size={18} />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title={t("p.work.tasks.export")}>
              <IconButton
                onClick={(e) => setExportAnchor(e.currentTarget)}
                aria-label={t("p.work.tasks.export")}
              >
                <Download size={18} />
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={exportAnchor}
              open={!!exportAnchor}
              onClose={() => setExportAnchor(null)}
            >
              <MenuItem onClick={exportCsv}>
                <ListItemText>
                  {t("p.work.tasks.exportCsv", { count: tasks.length })}
                </ListItemText>
              </MenuItem>
              <MenuItem onClick={exportIcal}>
                <ListItemText>{t("p.work.tasks.exportIcal")}</ListItemText>
              </MenuItem>
            </Menu>
            <Button variant="contained" startIcon={<Plus size={18} />} onClick={openNew}>
              {t("p.work.tasks.newTask")}
            </Button>
          </>
        }
      />

      {/* Captura rápida: título + fecha/prioridad/proyecto/etiquetas en lenguaje natural */}
      <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Zap size={18} color={theme.palette.primary.main} />
          <TextField
            size="small"
            fullWidth
            placeholder={t("p.taskx.quickAdd.placeholder")}
            aria-label={t("p.taskx.quickAdd.aria")}
            value={quickAddText}
            onChange={(e) => setQuickAddText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (quickAddText.trim() && !quickAddMut.isPending)
                  quickAddMut.mutate(quickAddText.trim());
              }
            }}
            disabled={quickAddMut.isPending}
          />
        </Stack>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: "block", mt: 0.5 }}
        >
          {t("p.taskx.quickAdd.hint")}
        </Typography>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack
          direction="row"
          spacing={1.5}
          flexWrap="wrap"
          useFlexGap
          alignItems="center"
        >
          <TextField
            size="small"
            placeholder={t("p.work.tasks.searchPlaceholder")}
            aria-label={t("p.work.tasks.searchAria")}
            value={params.get("q") || ""}
            onChange={(e) => setParam("q", e.target.value)}
            sx={{ minWidth: 220 }}
            InputProps={{
              startAdornment: (
                <Search
                  size={16}
                  style={{ marginRight: 6, color: theme.palette.text.secondary }}
                />
              ),
            }}
          />
          <Tooltip title={t("p.work.tasks.advSearchTooltip")}>
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
          {/* Filtros principales siempre visibles */}
          <TextField
            select
            size="small"
            label={t("p.work.tasks.state")}
            value={params.get("state") || ""}
            onChange={(e) => setParam("state", e.target.value)}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="">{t("p.work.tasks.allM")}</MenuItem>
            {(Object.keys(STATE_I18N_KEYS) as TaskState[]).map((s) => (
              <MenuItem key={s} value={s}>
                {t(STATE_I18N_KEYS[s]!)}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label={t("p.work.tasks.priority")}
            value={params.get("priority") || ""}
            onChange={(e) => setParam("priority", e.target.value)}
            sx={{ minWidth: 130 }}
          >
            <MenuItem value="">{t("p.work.tasks.allF")}</MenuItem>
            {([0, 1, 2, 3, 4, 5] as TaskPriority[]).map((p) => (
              <MenuItem key={p} value={p}>
                {t(`p.work.priority.p${p}`)}
              </MenuItem>
            ))}
          </TextField>
          {/* Ordenación: "Manual" (position) activa drag & drop en la lista */}
          <TextField
            select
            size="small"
            label={t("p.taskx.ordering.label")}
            value={params.get("ordering") || "-created_at"}
            onChange={(e) => setParam("ordering", e.target.value)}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="-created_at">{t("p.taskx.ordering.created")}</MenuItem>
            <MenuItem value="due_date">{t("p.taskx.ordering.dueDate")}</MenuItem>
            <MenuItem value="priority">{t("p.taskx.ordering.priority")}</MenuItem>
            <MenuItem value="title">{t("p.taskx.ordering.title")}</MenuItem>
            <MenuItem value="position">{t("p.taskx.ordering.manual")}</MenuItem>
          </TextField>
          {/* Agrupar por sección: solo en vista lista dentro de un proyecto */}
          {effectiveProjectId != null && view === "list" && (
            <Tooltip title={t("p.taskx.sections.groupBy")}>
              <ToggleButton
                size="small"
                value="sections"
                selected={groupBySections}
                onChange={() => setParam("group", groupBySections ? null : "sections")}
                aria-label={t("p.taskx.sections.groupBy")}
                sx={{ px: 1 }}
              >
                <ListTree size={16} />
              </ToggleButton>
            </Tooltip>
          )}
          {/* Filtros avanzados bajo "Más filtros" */}
          <Badge
            badgeContent={advancedCount}
            color="primary"
            invisible={advancedCount === 0}
          >
            <Button
              size="small"
              variant="outlined"
              onClick={() => setShowMoreFilters((v) => !v)}
              aria-expanded={showMoreFilters}
              sx={{ textTransform: "none" }}
            >
              {t("p.work.tasks.moreFilters")}
            </Button>
          </Badge>
          <Box sx={{ flex: 1 }} />
          <ToggleButtonGroup
            size="small"
            value={view}
            exclusive
            onChange={(_, v) => v && setParam("view", v)}
          >
            <ToggleButton value="list" aria-label={t("p.work.tasks.viewList")}>
              <ListIcon size={16} />
            </ToggleButton>
            <ToggleButton value="table" aria-label={t("p.work.tasks.viewTable")}>
              <TableIcon size={16} />
            </ToggleButton>
            <ToggleButton value="kanban" aria-label={t("p.work.tasks.viewKanban")}>
              <Columns size={16} />
            </ToggleButton>
            <ToggleButton value="calendar" aria-label={t("p.work.tasks.viewCalendar")}>
              <Calendar size={16} />
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>

        {/* Presets rápidos (Todoist): chips de un clic */}
        <Stack direction="row" spacing={1} mt={1.5} flexWrap="wrap" useFlexGap>
          {presets.map((p) => (
            <Chip
              key={p.id}
              label={p.label}
              size="small"
              variant={p.active ? "filled" : "outlined"}
              color={p.active ? "primary" : "default"}
              onClick={p.toggle}
            />
          ))}
        </Stack>

        {/* Filtros avanzados — divulgación progresiva */}
        <Collapse in={showMoreFilters}>
          <Stack direction="row" spacing={1.5} mt={2} flexWrap="wrap" useFlexGap>
            <TextField
              select
              size="small"
              label={t("p.work.tasks.tag")}
              value={params.get("tag") || ""}
              onChange={(e) => setParam("tag", e.target.value)}
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="">{t("p.work.tasks.allF")}</MenuItem>
              {tags.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label={t("p.work.tasks.sprint")}
              value={params.get("sprint") || ""}
              onChange={(e) => setParam("sprint", e.target.value)}
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="">{t("p.work.tasks.allM")}</MenuItem>
              {sprints.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label={t("p.work.tasks.epic")}
              value={params.get("epic") || ""}
              onChange={(e) => setParam("epic", e.target.value)}
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="">{t("p.work.tasks.allF")}</MenuItem>
              {epics.map((e) => (
                <MenuItem key={e.id} value={e.id}>
                  {e.title}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </Collapse>

        {/* Chips de filtros activos — removibles individualmente */}
        {activeFilters.length > 0 && (
          <Stack
            direction="row"
            spacing={1}
            mt={2}
            flexWrap="wrap"
            useFlexGap
            alignItems="center"
          >
            {activeFilters.map((f) => (
              <Chip
                key={f.key}
                size="small"
                label={f.label}
                onDelete={() => setParam(f.key, null)}
                variant="outlined"
              />
            ))}
            <Button
              size="small"
              variant="text"
              onClick={clearAllFilters}
              sx={{ textTransform: "none" }}
            >
              {t("p.work.tasks.clearAll")}
            </Button>
          </Stack>
        )}
      </Paper>

      {/* Saved searches */}
      {savedSearchList.length > 0 && (
        <Stack direction="row" spacing={1} mb={2} flexWrap="wrap" useFlexGap>
          <Typography variant="caption" color="text.secondary" sx={{ pt: 0.5 }}>
            {t("p.work.tasks.savedSearches")}
          </Typography>
          {savedSearchList.map((ss: SavedSearch) => (
            <Chip
              key={ss.id}
              size="small"
              label={ss.name}
              onClick={() => loadSavedSearch(ss)}
              onDelete={async () => {
                if (
                  await confirm(t("p.work.tasks.confirmDeleteSearch", { name: ss.name }))
                )
                  deleteSearchMut.mutate(ss.id);
              }}
              deleteIcon={<Trash2 size={14} />}
              avatar={
                <Edit3
                  size={14}
                  style={{ cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditSearchId(ss.id);
                    setEditSearchName(ss.name);
                  }}
                />
              }
              variant="outlined"
            />
          ))}
        </Stack>
      )}

      {/* Bulk actions bar */}
      {selected.size > 0 && (
        <Paper
          sx={{
            p: 1.5,
            mb: 2,
            display: "flex",
            alignItems: "center",
            gap: 1,
            bgcolor: "primary.main",
            color: "primary.contrastText",
          }}
        >
          <Typography variant="body2" fontWeight={600}>
            {t("p.work.tasks.selected", { count: selected.size })}
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button
            size="small"
            color="inherit"
            startIcon={<Edit3 size={14} />}
            onClick={() => setBulkDialog("update")}
          >
            {t("p.work.tasks.changeState")}
          </Button>
          <Button
            size="small"
            color="inherit"
            startIcon={<FolderInput size={14} />}
            onClick={() => setBulkDialog("moveSprint")}
          >
            {t("p.work.tasks.moveToSprint")}
          </Button>
          <Button
            size="small"
            color="inherit"
            startIcon={<Trash2 size={14} />}
            onClick={handleBulkDelete}
          >
            {t("common.delete")}
          </Button>
          <Tooltip title={t("p.work.tasks.clearSelection")}>
            <IconButton
              size="small"
              color="inherit"
              onClick={clearSelection}
              aria-label={t("p.work.tasks.clearSelection")}
            >
              <X size={16} />
            </IconButton>
          </Tooltip>
        </Paper>
      )}

      {/* Save search button */}
      {(params.get("state") ||
        params.get("priority") ||
        params.get("tag") ||
        params.get("q")) && (
        <Box mb={2}>
          <Button
            size="small"
            startIcon={<Bookmark size={14} />}
            variant="text"
            onClick={() => setSaveSearchDialog(true)}
          >
            {t("p.work.tasks.saveSearch")}
          </Button>
        </Box>
      )}

      {isLoading ? (
        // Skeleton con la forma de la vista activa (patrón Linear/Todoist)
        view === "kanban" ? (
          <KanbanSkeleton />
        ) : view === "table" || view === "calendar" ? (
          <TableSkeleton rows={10} cols={view === "calendar" ? 7 : 6} />
        ) : (
          <TaskListSkeleton />
        )
      ) : error ? (
        <Alert severity="error">{t("p.work.tasks.loadError")}</Alert>
      ) : tasks.length === 0 ? (
        activeFilters.length > 0 ? (
          <EmptyFilterState
            action={
              <Button variant="outlined" onClick={clearAllFilters}>
                {t("p.work.tasks.clearFilters")}
              </Button>
            }
          />
        ) : (
          <EmptyState
            title={t("p.work.tasks.emptyTitle")}
            description={t("p.work.tasks.emptyDesc")}
            action={
              <Button
                variant="contained"
                startIcon={<Plus size={16} />}
                onClick={openNew}
              >
                {t("p.work.tasks.newTask")}
              </Button>
            }
          />
        )
      ) : view === "kanban" ? (
        <KanbanBoard tasks={tasks} onEdit={openEdit} projectId={effectiveProjectId} />
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
                {selected.size > 0
                  ? t("p.work.tasks.selectedHint", { count: selected.size })
                  : t("p.work.tasks.selectAllHint")}
              </Typography>
            </Box>
          )}
          <TaskRows
            tasks={tasks}
            selected={selected}
            toggleSelect={toggleSelect}
            onEdit={openEdit}
            focusedId={focusedTask?.id}
            reorderable={
              view === "list" && params.get("ordering") === "position" && !groupBySections
            }
            groups={sectionGroups}
          />
        </Stack>
      )}

      <TaskDialog
        open={dialogVisible}
        task={wantsNew ? null : editing}
        defaultProjectId={effectiveProjectId}
        onClose={closeDialog}
        onSaved={onSaved}
      />

      {/* Bulk: Editar campos (estado y/o fecha límite) */}
      <Dialog
        open={bulkDialog === "update"}
        onClose={() => setBulkDialog(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>
          {t("p.work.tasks.changeStateCount", { count: selected.size })}
        </DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel>{t("p.work.tasks.newState")}</InputLabel>
            <Select
              value={bulkState}
              label={t("p.work.tasks.newState")}
              onChange={(e) => setBulkState(e.target.value)}
            >
              <MenuItem value="">{t("p.work.tasks.keepCurrent")}</MenuItem>
              <MenuItem value="pending">{t("task.state.pending")}</MenuItem>
              <MenuItem value="in_progress">{t("task.state.in_progress")}</MenuItem>
              <MenuItem value="blocked">{t("task.state.blocked")}</MenuItem>
              <MenuItem value="completed">{t("task.state.completed")}</MenuItem>
              <MenuItem value="cancelled">{t("task.state.cancelled")}</MenuItem>
              <MenuItem value="archived">{t("task.state.archived")}</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>{t("p.work.tasks.priority")}</InputLabel>
            <Select
              value={bulkPriority}
              label={t("p.work.tasks.priority")}
              onChange={(e) => setBulkPriority(e.target.value)}
            >
              <MenuItem value="">{t("p.work.tasks.keepCurrent")}</MenuItem>
              {([0, 1, 2, 3, 4, 5] as TaskPriority[]).map((p) => (
                <MenuItem key={p} value={p}>
                  {t(`p.work.priority.p${p}`)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Box sx={{ mt: 2 }}>
            <DateField
              label={t("p.work.tasks.newDueDate")}
              value={bulkDate}
              onChange={setBulkDate}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkDialog(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleBulkUpdate}
            disabled={bulkUpdateMut.isPending}
          >
            {t("p.work.tasks.apply")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk: Mover a sprint */}
      <Dialog
        open={bulkDialog === "moveSprint"}
        onClose={() => setBulkDialog(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>
          {t("p.work.tasks.moveToSprintCount", { count: selected.size })}
        </DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel>{t("p.work.tasks.sprint")}</InputLabel>
            <Select
              value={bulkSprint}
              label={t("p.work.tasks.sprint")}
              onChange={(e) => setBulkSprint(e.target.value as number | "")}
            >
              <MenuItem value="">{t("p.work.tasks.noSprint")}</MenuItem>
              {sprints.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkDialog(null)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleBulkMoveSprint}
            disabled={bulkMoveSprintMut.isPending}
          >
            {t("p.work.tasks.move")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Guardar búsqueda */}
      <Dialog
        open={saveSearchDialog}
        onClose={() => setSaveSearchDialog(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>{t("p.work.tasks.saveSearch")}</DialogTitle>
        <DialogContent>
          <TextField
            label={t("common.name")}
            fullWidth
            autoFocus
            sx={{ mt: 1 }}
            value={searchName}
            onChange={(e) => setSearchName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSaveSearch();
              }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveSearchDialog(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={handleSaveSearch}
            disabled={!searchName.trim() || saveSearchMut.isPending}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit saved search dialog */}
      <Dialog
        open={editSearchId !== null}
        onClose={() => {
          setEditSearchId(null);
          setEditSearchName("");
        }}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>{t("p.work.tasks.renameSearch")}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            label={t("p.work.tasks.newName")}
            fullWidth
            sx={{ mt: 1 }}
            value={editSearchName}
            onChange={(e) => setEditSearchName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (editSearchName.trim() && editSearchId !== null)
                  updateSearchMut.mutate({
                    id: editSearchId,
                    name: editSearchName.trim(),
                  });
              }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setEditSearchId(null);
              setEditSearchName("");
            }}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="contained"
            disabled={!editSearchName.trim() || updateSearchMut.isPending}
            onClick={() => {
              if (editSearchId !== null)
                updateSearchMut.mutate({ id: editSearchId, name: editSearchName.trim() });
            }}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Diálogo "Secciones": renombrar inline, eliminar, crear y reordenar
          con flechas ↑↓ (POST /project-sections/reorder/). */}
      <Dialog
        open={sectionsDialog}
        onClose={() => setSectionsDialog(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{t("p.taskx.sections.title")}</DialogTitle>
        <DialogContent>
          {sections.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t("p.taskx.sections.empty")}
            </Typography>
          )}
          <List dense disablePadding>
            {sections.map((s, i) => (
              <ListItem
                key={s.id}
                disableGutters
                secondaryAction={
                  <Stack direction="row" spacing={0}>
                    <IconButton
                      size="small"
                      disabled={i === 0 || reorderSectionsMut.isPending}
                      onClick={() => moveSection(i, -1)}
                      aria-label={t("p.taskx.sections.moveUp")}
                    >
                      <ArrowUp size={14} />
                    </IconButton>
                    <IconButton
                      size="small"
                      disabled={i === sections.length - 1 || reorderSectionsMut.isPending}
                      onClick={() => moveSection(i, 1)}
                      aria-label={t("p.taskx.sections.moveDown")}
                    >
                      <ArrowDown size={14} />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => {
                        setRenamingSection(s.id);
                        setRenameValue(s.name);
                      }}
                      aria-label={t("p.taskx.sections.rename")}
                    >
                      <Pencil size={14} />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={async () => {
                        if (
                          await confirm(
                            t("p.taskx.sections.deleteConfirm", { name: s.name }),
                            { confirmLabel: t("common.delete") },
                          )
                        )
                          deleteSectionMut.mutate(s.id);
                      }}
                      aria-label={t("p.taskx.sections.delete")}
                    >
                      <Trash2 size={14} />
                    </IconButton>
                  </Stack>
                }
              >
                {renamingSection === s.id ? (
                  <TextField
                    size="small"
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => commitRename(s)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        commitRename(s);
                      } else if (e.key === "Escape") {
                        setRenamingSection(null);
                      }
                    }}
                    sx={{ mr: 2 }}
                  />
                ) : (
                  <ListItemText primary={s.name} />
                )}
              </ListItem>
            ))}
          </List>
          <Stack direction="row" spacing={1} mt={2}>
            <TextField
              size="small"
              fullWidth
              label={t("p.taskx.sections.newName")}
              value={newSectionName}
              onChange={(e) => setNewSectionName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  if (newSectionName.trim() && !createSectionMut.isPending)
                    createSectionMut.mutate(newSectionName.trim());
                }
              }}
            />
            <Button
              variant="contained"
              disabled={!newSectionName.trim() || createSectionMut.isPending}
              onClick={() => createSectionMut.mutate(newSectionName.trim())}
            >
              {t("p.taskx.sections.add")}
            </Button>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSectionsDialog(false)}>{t("common.close")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
