import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Paper,
  Stack,
  Chip,
  TextField,
  Tabs,
  Tab,
  InputAdornment,
} from "@mui/material";
import { Search, CheckSquare, MessageSquare, BookOpen, Folder } from "lucide-react";
import PageHeader from "../components/ui/PageHeader";
import { EmptyState, ErrorState } from "../components/ui/states";
import { TaskListSkeleton } from "../components/ui/skeletons";
import { TASK_STATE_I18N_KEYS } from "../i18n/batchTaskUi";
import type { TaskState } from "../types";
import { tasksApi, type GlobalSearchResults } from "../api/resources";

type TabKey = "all" | "tasks" | "comments" | "wiki" | "projects";

const TABS: { key: TabKey; labelKey: string; icon: React.ReactNode }[] = [
  { key: "all", labelKey: "p.work.search.tabs.all", icon: <Search size={15} /> },
  { key: "tasks", labelKey: "p.work.search.tabs.tasks", icon: <CheckSquare size={15} /> },
  {
    key: "comments",
    labelKey: "p.work.search.tabs.comments",
    icon: <MessageSquare size={15} />,
  },
  { key: "wiki", labelKey: "nav.wiki", icon: <BookOpen size={15} /> },
  { key: "projects", labelKey: "nav.projects", icon: <Folder size={15} /> },
];

/** Centro de búsqueda: resultados completos con tabs por entidad.
 *  El CommandPalette (Ctrl+K) sigue siendo el acceso rápido; esta página
 *  ofrece resultados completos, filtros y una URL compartible. */
export default function SearchPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [q, setQ] = useState(params.get("q") || "");
  const [tab, setTab] = useState<TabKey>("all");
  const query = params.get("q") || "";

  // Debounce: actualiza la URL 300ms después de escribir
  useEffect(() => {
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params);
      if (q.trim()) next.set("q", q.trim());
      else next.delete("q");
      setParams(next, { replace: true });
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { data, isLoading, isError, refetch } = useQuery<GlobalSearchResults>({
    queryKey: ["global-search", query],
    queryFn: () => tasksApi.globalSearch(query),
    enabled: query.length >= 2,
  });

  // El esquema zod usa passthrough (campos extra `unknown`): casteamos a
  // los tipos concretos del endpoint para que TS los compruebe.
  const tasks = (data?.tasks ?? []) as {
    id: number;
    title: string;
    state: string;
    priority: number;
    project: string | null;
  }[];
  const comments = (data?.comments ?? []) as {
    id: number;
    title: string;
    task: { id: number; title: string };
  }[];
  const wiki = (data?.wiki ?? []) as {
    id: number;
    title: string;
    project: string | null;
  }[];
  const projects = (data?.projects ?? []) as {
    id: number;
    title: string;
    is_archived: boolean;
  }[];

  const counts = {
    tasks: tasks.length,
    comments: comments.length,
    wiki: wiki.length,
    projects: projects.length,
  };
  const total = counts.tasks + counts.comments + counts.wiki + counts.projects;

  const openTask = (id: number) => navigate(`/app/tasks/${id}`);

  const sections: { key: TabKey; title: string; items: React.ReactNode }[] = [];

  if (data && (tab === "all" || tab === "tasks") && counts.tasks > 0) {
    sections.push({
      key: "tasks",
      title: t("p.work.search.tabs.tasks"),
      items: tasks.map((task) => (
        <Paper
          key={task.id}
          variant="outlined"
          sx={{ p: 1.5, cursor: "pointer" }}
          onClick={() => openTask(task.id)}
        >
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
          >
            <CheckSquare size={15} />
            <Typography variant="body2" fontWeight={600} sx={{ flex: 1 }}>
              {task.title}
            </Typography>
            <Chip
              size="small"
              variant="outlined"
              label={t(
                TASK_STATE_I18N_KEYS[task.state as TaskState] ??
                  `task.state.${task.state}`,
                String(task.state ?? ""),
              )}
            />
            <Chip size="small" variant="outlined" label={`P${task.priority}`} />
            {task.project ? <Chip size="small" label={String(task.project)} /> : null}
          </Stack>
        </Paper>
      )),
    });
  }
  if (data && (tab === "all" || tab === "comments") && counts.comments > 0) {
    sections.push({
      key: "comments",
      title: t("p.work.search.tabs.comments"),
      items: comments.map((c) => (
        <Paper
          key={c.id}
          variant="outlined"
          sx={{ p: 1.5, cursor: "pointer" }}
          onClick={() => openTask(c.task.id)}
        >
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
          >
            <MessageSquare size={15} />
            <Typography variant="body2" sx={{ flex: 1 }}>
              {c.title}
            </Typography>
            <Chip
              size="small"
              variant="outlined"
              label={t("p.work.search.inTask", { title: c.task.title })}
            />
          </Stack>
        </Paper>
      )),
    });
  }
  if (data && (tab === "all" || tab === "wiki") && counts.wiki > 0) {
    sections.push({
      key: "wiki",
      title: t("nav.wiki"),
      items: wiki.map((w) => (
        <Paper
          key={w.id}
          variant="outlined"
          sx={{ p: 1.5, cursor: "pointer" }}
          onClick={() => navigate("/app/wiki")}
        >
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
          >
            <BookOpen size={15} />
            <Typography variant="body2" fontWeight={600} sx={{ flex: 1 }}>
              {w.title}
            </Typography>
            {w.project ? <Chip size="small" label={String(w.project)} /> : null}
          </Stack>
        </Paper>
      )),
    });
  }
  if (data && (tab === "all" || tab === "projects") && counts.projects > 0) {
    sections.push({
      key: "projects",
      title: t("nav.projects"),
      items: projects.map((p) => (
        <Paper
          key={p.id}
          variant="outlined"
          sx={{ p: 1.5, cursor: "pointer" }}
          onClick={() => navigate(`/app/project/${p.id}`)}
        >
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
          >
            <Folder size={15} />
            <Typography variant="body2" fontWeight={600} sx={{ flex: 1 }}>
              {p.title}
            </Typography>
            {p.is_archived && (
              <Chip size="small" color="warning" label={t("p.work.search.archived")} />
            )}
          </Stack>
        </Paper>
      )),
    });
  }

  return (
    <Box maxWidth={860} mx="auto">
      <PageHeader
        title={t("p.work.search.title")}
        description={t("p.work.search.desc")}
      />

      <TextField
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("p.work.tasks.searchPlaceholder")}
        inputProps={{ "aria-label": t("p.work.tasks.searchPlaceholder") }}
        fullWidth
        autoFocus
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <Search size={18} />
            </InputAdornment>
          ),
        }}
        sx={{ mb: 2 }}
      />

      {query.length >= 2 && (
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ mb: 2 }}
        >
          {TABS.map((item) => (
            <Tab
              key={item.key}
              value={item.key}
              icon={item.icon as React.ReactElement}
              iconPosition="start"
              label={
                item.key === "all"
                  ? `${t(item.labelKey)} (${total})`
                  : `${t(item.labelKey)} (${counts[item.key as keyof typeof counts]})`
              }
            />
          ))}
        </Tabs>
      )}

      {query.length < 2 ? (
        <EmptyState
          title={t("p.work.search.typeToSearch")}
          description={t("p.work.search.typeToSearchDesc")}
        />
      ) : isLoading ? (
        <TaskListSkeleton rows={6} />
      ) : isError ? (
        <ErrorState
          title={t("p.work.search.error")}
          onRetry={() => void refetch()}
        />
      ) : total === 0 ? (
        <EmptyState
          title={t("p.work.search.noResultsFor", { query })}
          description={t("p.work.search.noResultsDesc")}
        />
      ) : (
        <Stack spacing={2.5}>
          {sections.map((s) => (
            <Box key={s.key}>
              <Typography variant="subtitle2" fontWeight={700} mb={1}>
                {s.title}
              </Typography>
              <Stack spacing={0.75}>{s.items}</Stack>
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  );
}
