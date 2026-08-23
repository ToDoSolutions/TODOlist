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
  due_date: string | null;
  completed_at: string | null;
  project: number | null;
  tags: number[];
  tags_ids: number[];
  subtasks: Subtask[];
  comments: Comment[];
  created_at: string;
  updated_at: string;
}

export interface TaskInput {
  title: string;
  description?: string;
  state?: TaskState;
  priority?: TaskPriority;
  due_date?: string | null;
  project?: number | null;
  tags?: number[];
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
