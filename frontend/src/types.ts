export type TaskState =
  | "backlog"
  | "pending"
  | "in_progress"
  | "blocked"
  | "review"
  | "completed"
  | "cancelled"
  | "archived";

export type TaskPriority = 0 | 1 | 2 | 3 | 4 | 5;

export type TaskType =
  | "bug"
  | "feature"
  | "improvement"
  | "task"
  | "research"
  | "tech_debt"
  | "docs"
  | "ops";

export type TaskSize = "xs" | "s" | "m" | "l" | "xl";

export type RelationType =
  | "blocks"
  | "related"
  | "duplicates"
  | "replaces"
  | "depends_on"
  | "requirement";

export interface User {
  id: number;
  username: string;
  email: string;
  avatar: string | null;
  timezone: string;
  locale: string;
}

export interface Tag {
  id: number;
  name: string;
  color: string;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  description: string;
  color: string;
  is_archived: boolean;
  tasks_count: number;
  sprints_count?: number;
  epics_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Subtask {
  id: number;
  title: string;
  is_done: boolean;
  order: number;
  created_at: string;
}

export interface Comment {
  id: number;
  body: string;
  author_email: string;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: number;
  title: string;
  description: string;
  state: TaskState;
  priority: TaskPriority;
  task_type: TaskType;
  due_date: string | null;
  start_date: string | null;
  completed_at: string | null;
  story_points: number | null;
  estimate_hours: number | null;
  size: TaskSize | "";
  project: number | null;
  tags: number[];
  tags_ids: number[];
  parent: number | null;
  parent_title: string | null;
  sprint: number | null;
  sprint_name: string | null;
  epic: number | null;
  epic_title: string | null;
  subtask_done: number;
  subtask_total: number;
  subtasks: Subtask[];
  comments: Comment[];
  recurrence: { id: number; frequency: string; interval: number; until: string | null; count: number | null; occurrences_generated: number } | null;
  created_at: string;
  updated_at: string;
}

export interface TaskInput {
  title: string;
  description?: string;
  state?: TaskState;
  priority?: TaskPriority;
  task_type?: TaskType;
  due_date?: string | null;
  start_date?: string | null;
  story_points?: number | null;
  estimate_hours?: number | null;
  size?: TaskSize | "";
  project?: number | null;
  tags?: number[];
  parent?: number | null;
  sprint?: number | null;
  epic?: number | null;
  recurrence_data?: { frequency: string; interval: number; until?: string | null; count?: number | null } | null;
}

export interface Activity {
  id: number;
  actor: number | null;
  actor_email: string;
  action: string;
  field: string;
  old_value: string;
  new_value: string;
  created_at: string;
}

export interface TaskRelation {
  id: number;
  source: number;
  source_title: string;
  target: number;
  target_title: string;
  relation_type: RelationType;
  created_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export const STATE_LABELS: Record<TaskState, string> = {
  backlog: "Backlog",
  pending: "Pendiente",
  in_progress: "En progreso",
  blocked: "Bloqueada",
  review: "En revisión",
  completed: "Completada",
  cancelled: "Cancelada",
  archived: "Archivada",
};

export const STATE_COLORS: Record<TaskState, string> = {
  backlog: "#9e9e9e",
  pending: "#757575",
  in_progress: "#1976d2",
  blocked: "#e53935",
  review: "#fb8c00",
  completed: "#43a047",
  cancelled: "#6d4c41",
  archived: "#607d8b",
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  0: "P0 Crítica",
  1: "P1 Muy alta",
  2: "P2 Alta",
  3: "P3 Media",
  4: "P4 Baja",
  5: "P5 Algún día",
};

export const PRIORITY_COLORS: Record<TaskPriority, string> = {
  0: "#d32f2f",
  1: "#ef6c00",
  2: "#f9a825",
  3: "#1976d2",
  4: "#7986cb",
  5: "#9e9e9e",
};

export const KANBAN_COLUMNS: TaskState[] = [
  "backlog",
  "pending",
  "in_progress",
  "blocked",
  "review",
  "completed",
];

export const TYPE_LABELS: Record<TaskType, string> = {
  bug: "Bug",
  feature: "Funcionalidad",
  improvement: "Mejora",
  task: "Tarea",
  research: "Investigación",
  tech_debt: "Deuda técnica",
  docs: "Documentación",
  ops: "Incidencia operativa",
};

export const TYPE_COLORS: Record<TaskType, string> = {
  bug: "#d32f2f",
  feature: "#1976d2",
  improvement: "#7b1fa2",
  task: "#388e3c",
  research: "#f57c00",
  tech_debt: "#5d4037",
  docs: "#0288d1",
  ops: "#c2185b",
};

export const SIZE_LABELS: Record<TaskSize, string> = {
  xs: "XS",
  s: "S",
  m: "M",
  l: "L",
  xl: "XL",
};

export const RELATION_LABELS: Record<RelationType, string> = {
  blocks: "Bloquea",
  related: "Relacionada con",
  duplicates: "Duplica",
  replaces: "Sustituye",
  depends_on: "Depende de",
  requirement: "Es requisito de",
};
