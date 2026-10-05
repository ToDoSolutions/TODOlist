// Modelo de resultados de la CommandPalette (Ctrl+K) y transformación
// de la respuesta de /api/tasks/global-search/ en entradas accionables.
import type { ReactNode } from "react";
import {
  BookOpen,
  CheckSquare,
  Folder,
  MessageSquare,
} from "lucide-react";
import i18n from "../i18n";

export interface Result {
  key: string;
  icon: ReactNode;
  primary: string;
  secondary?: string;
  group: string;
  path: string;
  action?: () => void;
}

/** Ítem de la respuesta de global-search (shape laxo: el backend devuelve
 * campos extra según el tipo). */
export interface SearchItem {
  type: string;
  id: number;
  title: string;
  state?: string;
  priority?: number;
  project?: string | null;
  is_archived?: boolean;
  task?: { id: number; title: string };
}

export interface SearchResultsInput {
  tasks?: SearchItem[];
  comments?: SearchItem[];
  wiki?: SearchItem[];
  projects?: SearchItem[];
}

const PER_GROUP = 8;

/**
 * Convierte la respuesta de búsqueda global en resultados de la paleta:
 * tareas y comentarios navegan al deep-link de la tarea, wiki a /app/wiki
 * y proyectos a su vista. Máx. PER_GROUP por grupo.
 */
export function buildResults(data?: SearchResultsInput | null): Result[] {
  if (!data) return [];
  const t = i18n.t.bind(i18n);
  const out: Result[] = [];

  for (const task of (data.tasks ?? []).slice(0, PER_GROUP)) {
    out.push({
      key: `task-${task.id}`,
      icon: <CheckSquare size={16} />,
      primary: task.title,
      secondary: [task.state, task.priority !== undefined ? `P${task.priority}` : null, task.project]
        .filter(Boolean)
        .join(" · "),
      group: t("p.work.search.tabs.tasks"),
      path: `/app/tasks/${task.id}`,
    });
  }

  for (const c of (data.comments ?? []).slice(0, PER_GROUP)) {
    out.push({
      key: `comment-${c.id}`,
      icon: <MessageSquare size={16} />,
      primary: c.title,
      secondary: c.task?.title
        ? t("p.work.search.inTask", { title: c.task.title })
        : undefined,
      group: t("p.work.search.tabs.comments"),
      path: c.task ? `/app/tasks/${c.task.id}` : "/app",
    });
  }

  for (const w of (data.wiki ?? []).slice(0, PER_GROUP)) {
    out.push({
      key: `wiki-${w.id}`,
      icon: <BookOpen size={16} />,
      primary: w.title,
      secondary: w.project ?? undefined,
      group: t("nav.wiki"),
      path: "/app/wiki",
    });
  }

  for (const p of (data.projects ?? []).slice(0, PER_GROUP)) {
    out.push({
      key: `project-${p.id}`,
      icon: <Folder size={16} />,
      primary: p.title,
      group: t("nav.projects"),
      path: `/app/project/${p.id}`,
    });
  }

  return out;
}
