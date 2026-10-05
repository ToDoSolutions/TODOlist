import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Fuse from "fuse.js";
import type { Task } from "../types";
import {
  Dialog,
  DialogTitle,
  Box,
  TextField,
  InputAdornment,
  List,
  ListItemButton,
  Typography,
  Chip,
  Divider,
} from "@mui/material";
import { visuallyHidden } from "@mui/utils";
import {
  Search,
  CheckSquare,
  CornerDownLeft,
  Plus,
  Briefcase,
  Moon,
  Sun,
  Folder,
  Inbox,
  LayoutDashboard,
  BarChart3,
  Rocket,
  Map,
  CalendarDays,
  CalendarClock,
  Bell,
  User,
  Users,
  Clock,
  BookOpen,
  Target,
  Timer,
  HelpCircle,
  ClipboardList,
  Star,
  CheckCircle2,
} from "lucide-react";
import { tasksApi } from "../api/resources";
import { buildResults, type Result } from "../lib/commandPalette";
import { useThemeMode } from "../theme-context";

export default function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { mode: themeMode, toggle: toggleTheme } = useThemeMode();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounce 250ms
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);

  // Reset al abrir: ajuste de estado durante render (patrón React:
  // "adjusting state when props change", sin effect en cascada).
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setQuery("");
      setDebounced("");
      setIndex(0);
    }
  }
  // El efecto solo sincroniza con el DOM (focus), no toca state.
  useEffect(() => {
    if (!open) return;
    const id = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(id);
  }, [open]);

  const qc = useQueryClient();
  const { data, isError } = useQuery({
    queryKey: ["global-search", debounced],
    queryFn: () => tasksApi.globalSearch(debounced),
    // Búsqueda en vivo solo a partir de 2 caracteres (ruido de 1 char).
    enabled: open && debounced.length >= 2,
    staleTime: 15_000,
  });

  // Fallback offline: si la búsqueda global falla, fuzzy-search sobre
  // la caché local de tareas con fuse.js.
  const cachedTasks = useMemo(() => {
    if (!isError) return [];
    const all = qc.getQueryCache().findAll({ queryKey: ["tasks"] });
    const list = all.find((q) => Array.isArray(q.state.data))?.state.data;
    return (list as Task[] | undefined) || [];
  }, [isError, qc]);
  const fuse = useMemo(
    () =>
      new Fuse((cachedTasks as Task[] | undefined) || [], {
        keys: ["title", "description"],
        threshold: 0.35,
      }),
    [cachedTasks],
  );

  // Acciones del palette: lanzador de comandos, no solo buscador.
  // Se filtran por coincidencia de texto y se anteponen a los resultados.
  const actions: Result[] = useMemo(
    () => [
      {
        key: "act-new-task",
        icon: <Plus size={16} />,
        primary: t("p.board.palette.newTask"),
        secondary: t("p.board.palette.newTaskDesc"),
        group: t("p.board.palette.actions"),
        path: "/app?new=1",
      },
      {
        key: "act-new-project",
        icon: <Folder size={16} />,
        primary: t("p.board.palette.newProject"),
        secondary: t("p.board.palette.newProjectDesc"),
        group: t("p.board.palette.actions"),
        path: "/app/projects?new=1",
      },
      {
        key: "act-mywork",
        icon: <Briefcase size={16} />,
        primary: t("p.board.palette.myWork"),
        secondary: t("p.board.palette.myWorkDesc"),
        group: t("p.board.palette.actions"),
        path: "/app/my-work",
      },
      {
        key: "act-theme",
        icon: themeMode === "dark" ? <Sun size={16} /> : <Moon size={16} />,
        primary:
          themeMode === "dark"
            ? t("p.board.palette.toLight")
            : t("p.board.palette.toDark"),
        secondary: t("p.board.palette.appearance"),
        group: t("p.board.palette.actions"),
        path: "#theme",
        action: toggleTheme,
      },
    ],
    [themeMode, toggleTheme, t],
  );

  // Navegación rápida: destinos principales de la app (labels nav.*).
  const navEntries: Result[] = useMemo(() => {
    const group = t("p.taskx.palette.navGroup");
    const e = (
      key: string,
      labelKey: string,
      path: string,
      icon: React.ReactNode,
    ): Result => ({ key: `nav-${key}`, icon, primary: t(labelKey), group, path });
    return [
      e("inbox", "nav.inbox", "/app/inbox", <Inbox size={16} />),
      e("mywork", "nav.myWork", "/app/my-work", <Briefcase size={16} />),
      e("favorites", "nav.favorites", "/app/favorites", <Star size={16} />),
      e("completed", "nav.completed", "/app/completed", <CheckCircle2 size={16} />),
      e("projects", "nav.projects", "/app/projects", <Folder size={16} />),
      e("tasks", "p.taskx.palette.navTasks", "/app/tasks", <CheckSquare size={16} />),
      e("search", "p.taskx.palette.navSearch", "/app/search", <Search size={16} />),
      e("dashboard", "nav.dashboard", "/app/dashboard", <LayoutDashboard size={16} />),
      e(
        "dashboards",
        "p.taskx.palette.navDashboards",
        "/app/dashboards",
        <BarChart3 size={16} />,
      ),
      e("sprints", "nav.sprints", "/app/sprints", <Rocket size={16} />),
      e("roadmap", "nav.roadmap", "/app/roadmap", <Map size={16} />),
      e("gantt", "nav.gantt", "/app/gantt", <CalendarDays size={16} />),
      e(
        "calendar",
        "p.taskx.palette.navCalendar",
        "/app/calendars",
        <CalendarClock size={16} />,
      ),
      e("meetings", "p.taskx.palette.navMeetings", "/app/meetings", <Users size={16} />),
      e("okrs", "nav.okrs", "/app/okrs", <Target size={16} />),
      e(
        "intake",
        "p.taskx.palette.navIntake",
        "/app/intake-forms",
        <ClipboardList size={16} />,
      ),
      e("time", "nav.timeTracking", "/app/time-entries", <Clock size={16} />),
      e("focus", "nav.focus", "/app/focus", <Timer size={16} />),
      e("notifications", "nav.notifications", "/app/notifications", <Bell size={16} />),
      e("teams", "nav.teams", "/app/teams", <Users size={16} />),
      e("wiki", "nav.wiki", "/app/wiki", <BookOpen size={16} />),
      e("profile", "nav.profile", "/app/profile", <User size={16} />),
      e("help", "p.taskx.palette.navHelp", "/app/help", <HelpCircle size={16} />),
    ];
  }, [t]);

  // Comandos completos = acciones + navegación; se filtran por texto.
  const commands = useMemo(() => [...actions, ...navEntries], [actions, navEntries]);

  const matchingCommands = useMemo(() => {
    if (!debounced) return commands;
    const q = debounced.toLowerCase();
    return commands.filter(
      (a) =>
        a.primary.toLowerCase().includes(q) ||
        (a.secondary ?? "").toLowerCase().includes(q),
    );
  }, [commands, debounced]);

  const results = useMemo(() => {
    const base = !isError || !debounced ? buildResults(data) : null;
    if (base !== null) return [...matchingCommands, ...base];
    return [
      ...matchingCommands,
      ...fuse
        .search(debounced)
        .slice(0, 10)
        .map(({ item: task }) => ({
          key: `task-${task.id}`,
          icon: <CheckSquare size={16} />,
          primary: task.title,
          secondary: `${task.state} · offline`,
          group: t("p.board.palette.tasksOffline"),
          path: "/app",
        })),
    ];
  }, [data, isError, debounced, fuse, matchingCommands, t]);
  // Reset del índice cuando cambia el conjunto de resultados
  // (mismo patrón de ajuste en render, sin effect).
  const [prevLen, setPrevLen] = useState(results.length);
  if (results.length !== prevLen) {
    setPrevLen(results.length);
    setIndex(0);
  }

  const select = useCallback(
    (r: Result) => {
      onClose();
      if (r.action) {
        r.action();
      } else {
        navigate(r.path);
      }
    },
    [navigate, onClose],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[index]) {
      e.preventDefault();
      select(results[index]);
    }
  };

  // Lista agrupada con cabeceras por `group` (acciones, navegación,
  // resultados de búsqueda). Compartida por el estado vacío y con query.
  const renderGrouped = (list: Result[]) => (
    <List dense disablePadding component="div">
      {list.map((r, i) => {
        const showHeader = i === 0 || list[i - 1]!.group !== r.group;
        return (
          <Box key={r.key}>
            {showHeader && (
              <>
                {i > 0 && <Divider />}
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    px: 2,
                    pt: 1,
                    pb: 0.5,
                    display: "block",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  {r.group}
                </Typography>
              </>
            )}
            <ListItemButton
              selected={i === index}
              onClick={() => select(r)}
              sx={{ px: 2, py: 1 }}
            >
              <Box sx={{ color: "text.secondary", mr: 1.5, display: "flex" }}>
                {r.icon}
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                  variant="body2"
                  fontWeight={600}
                  sx={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {r.primary}
                </Typography>
                {r.secondary && (
                  <Typography variant="caption" color="text.secondary">
                    {r.secondary}
                  </Typography>
                )}
              </Box>
              {i === index && (
                <Box sx={{ color: "text.secondary", display: "flex" }}>
                  <CornerDownLeft size={14} color="currentColor" />
                </Box>
              )}
            </ListItemButton>
          </Box>
        );
      })}
    </List>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          position: "fixed",
          top: "12vh",
          m: 0,
          borderRadius: 3,
          overflow: "hidden",
        },
      }}
    >
      <DialogTitle sx={visuallyHidden}>{t("p.board.palette.title")}</DialogTitle>
      <TextField
        inputRef={inputRef}
        fullWidth
        placeholder={t("p.board.palette.placeholder")}
        inputProps={{ "aria-label": t("p.board.palette.placeholder") }}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
        variant="outlined"
        sx={{ "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start" sx={{ color: "text.secondary" }}>
              <Search size={18} color="currentColor" />
            </InputAdornment>
          ),
        }}
      />
      <Box sx={{ maxHeight: "55vh", overflow: "auto" }}>
        {debounced === "" ? (
          <>
            {renderGrouped(commands)}
            <Box sx={{ p: 2, borderTop: 1, borderColor: "divider" }}>
              <Typography variant="caption" color="text.secondary">
                {t("p.board.palette.syntax")} <code>assigned:me</code>{" "}
                <code>status:open</code> <code>tag:nombre</code>{" "}
                <code>project:nombre</code> <code>due:overdue</code>{" "}
                <code>updated:7d</code> <code>"frase literal"</code>
              </Typography>
            </Box>
          </>
        ) : results.length === 0 && data ? (
          <Box sx={{ p: 3 }}>
            <Typography variant="body2" color="text.secondary">
              {t("p.board.palette.noResults", { query: debounced })}
            </Typography>
          </Box>
        ) : (
          renderGrouped(results)
        )}
      </Box>
      <Box
        sx={{
          px: 2,
          py: 1,
          borderTop: 1,
          borderColor: "divider",
          display: "flex",
          gap: 2,
        }}
      >
        <Typography variant="caption" color="text.secondary">
          {t("p.board.palette.hints")}
        </Typography>
        <Chip
          label="Ctrl K"
          size="small"
          variant="outlined"
          sx={{ ml: "auto", height: 20 }}
        />
      </Box>
    </Dialog>
  );
}
