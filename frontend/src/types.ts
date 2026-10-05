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
  "bug" | "feature" | "improvement" | "task" | "research" | "tech_debt" | "docs" | "ops";

export type TaskSize = "xs" | "s" | "m" | "l" | "xl";

export type RelationType =
  "blocks" | "related" | "duplicates" | "replaces" | "depends_on" | "requirement";

export interface User {
  id: number;
  username: string;
  email: string;
  avatar: string | null;
  timezone: string;
  locale: string;
  email_verified?: boolean;
  email_verified_at?: string | null;
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
  /** Prefijo para las referencias de tarea (p.ej. "MP" → "MP-42"); writable. */
  issue_prefix?: string;
  tasks_count: number;
  completed_tasks_count?: number;
  sprints_count?: number;
  epics_count?: number;
  /** Marcado como favorito por el usuario actual (estrella). */
  is_favorite?: boolean;
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
  reactions?: Record<string, number[]>;
  replies_count?: number;
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
  /** Multi-homing (Asana): hogares extra donde también aparece la tarea. */
  extra_projects?: number[];
  project_color?: string; // solo en respuestas enriquecidas (gantt)
  tags: number[];
  tags_ids: number[];
  parent: number | null;
  parent_title: string | null;
  sprint: number | null;
  sprint_name: string | null;
  epic: number | null;
  epic_title: string | null;
  assignee: number | null;
  assignee_email: string | null;
  /** Sección del proyecto (writable en create/PATCH; null = sin sección). */
  section?: number | null;
  /** Nombre de la sección (solo lectura). */
  section_name?: string;
  /** Referencia legible "PREFIX-N" cuando el proyecto define issue_prefix
   *  (solo lectura; sin proyecto cae al id plano). */
  ref?: string;
  subtask_done: number;
  subtask_total: number;
  subtasks: Subtask[];
  comments: Comment[];
  recurrence: {
    id: number;
    frequency: string;
    interval: number;
    until: string | null;
    count: number | null;
    occurrences_generated: number;
  } | null;
  /** Solo lectura: posición para ordenación manual (`ordering=position`). */
  position?: number;
  /** Tarea fijada: ordena antes que el resto en la vista lista. */
  is_pinned?: boolean;
  /** Hito (Asana): marcador de roadmap con fecha, sin trabajo propio. */
  is_milestone?: boolean;
  /** Marcada como favorita por el usuario actual (estrella). */
  is_favorite?: boolean;
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
  /** Multi-homing: hogares adicionales (writable en create/PATCH). */
  extra_projects?: number[];
  tags?: number[];
  parent?: number | null;
  sprint?: number | null;
  epic?: number | null;
  assignee?: number | null;
  section?: number | null;
  is_pinned?: boolean;
  is_milestone?: boolean;
  recurrence_data?: {
    frequency: string;
    interval: number;
    until?: string | null;
    count?: number | null;
  } | null;
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

// --- Entidades secundarias (usadas por TeamsPage, WebhooksPage, CustomFieldsPage) ---
export interface Team {
  id: number;
  name: string;
  description?: string;
  member_count?: number;
  created_at?: string;
}
export interface TeamMember {
  id: number;
  user: number;
  user_email?: string;
  user_display?: string;
  role: string;
  joined_at?: string;
  created_at?: string;
}
export interface MentionItem {
  id: number;
  author: number;
  author_email?: string;
  author_display?: string;
  task: number;
  task_title?: string;
  content?: string;
  is_read?: boolean;
  created_at?: string;
}
export interface ProjectMember {
  id: number;
  user: number;
  user_email?: string;
  user_display?: string;
  email?: string;
  role: string;
  joined_at?: string;
  created_at?: string;
}
export interface Invitation {
  id: number;
  email: string;
  role?: string;
  status: string;
  target_type?: "team" | "project";
  target_id?: number;
  target_name?: string;
  invited_by_email?: string;
  created_at?: string;
}
export interface OutgoingWebhook {
  id: number;
  name?: string;
  url: string;
  events: string | string[];
  is_active: boolean;
  secret?: string;
  last_triggered?: string;
  created_at?: string;
}
export interface WebhookDelivery {
  id: number;
  webhook?: number;
  event?: string;
  event_type?: string;
  repo_full_name?: string;
  action?: string;
  status?: string;
  status_code?: number | null;
  error_message?: string;
  retry_count?: number;
  max_retries?: number;
  created_at?: string;
  response_body?: string;
}
export interface CustomField {
  id: number;
  name: string;
  field_type?: string;
  type?: string;
  project: number;
  options?: string[];
}
export interface CustomFieldValue {
  id: number;
  field: number;
  task: number;
  value?: unknown;
  value_text?: string;
}
export interface TimeEntry {
  id: number;
  task: number;
  task_title?: string;
  duration_seconds: number;
  started_at: string;
  description?: string;
}
export interface SyncOperation {
  id: number;
  op_id?: string;
  entity?: string;
  action?: string;
  status?: string;
  created_at?: string;
}
export interface FeatureFlag {
  id: number;
  key: string;
  name?: string;
  description?: string;
  is_enabled?: boolean;
  enabled_percentage?: number;
  enabled_users?: number[];
}
export interface ChatIntegration {
  id: number;
  provider: string;
  name?: string;
  webhook_url: string;
  events: string | string[];
  is_active: boolean;
}
export interface AiSuggestion {
  id: number;
  task: number | { id: number };
  suggestion_type: string;
  payload?: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  confidence?: number;
  status: string;
  created_at?: string;
}

export interface GitHubPR {
  id: number;
  pr_number: number;
  title: string;
  state: string;
  is_merged?: boolean;
  html_url?: string;
  author?: string;
  head_branch?: string;
  base_branch?: string;
  approvals_count?: number;
  ci_status?: string;
}
export interface GitHubCommit {
  sha: string;
  html_url?: string;
  message: string;
  author?: string;
  author_name?: string;
  author_date?: string;
}
export interface GitHubRelease {
  id: number;
  tag_name: string;
  name?: string;
  html_url?: string;
  body?: string;
  author?: string;
  published_at?: string;
  is_prerelease?: boolean;
}
export interface GitHubCheckRun {
  id: number;
  name: string;
  status: string;
  conclusion?: string;
  started_at?: string;
  completed_at?: string;
  html_url?: string;
}
export interface AiBlocker {
  blocker_type?: string;
  task_id?: number;
  task_title?: string;
  detail?: string;
  blocking_task_id?: number;
  blocking_task_title?: string;
  severity?: string;
}
export interface OfflineDevice {
  id: number;
  device_name?: string;
  device_id?: string;
  is_active?: boolean;
  last_seen?: string;
  created_at?: string;
}
export interface SyncFieldConflict {
  field: string;
  base?: unknown;
  server?: unknown;
  client?: unknown;
}
export interface SyncOperationItem {
  id: number;
  op_type?: string;
  entity_type?: string;
  entity_id?: number | string;
  server_entity_id?: number | string | null;
  status?: string;
  conflict_status?: string;
  payload?: Record<string, unknown>;
  conflict_data?: {
    server?: Record<string, unknown>;
    conflicting_fields?: SyncFieldConflict[];
  } | null;
  base_version?: number;
  client_timestamp?: string;
  created_at?: string;
  applied_at?: string | null;
}
export interface PullResult {
  changes?: SyncOperationItem[];
  results?: SyncOperationItem[];
  devices?: OfflineDevice[];
}

export interface AutomationRule {
  id: number;
  name: string;
  description?: string;
  trigger: string;
  action: string;
  action_params?: Record<string, unknown>;
  conditions?: { field?: string; operator?: string; value?: unknown }[];
  enabled: boolean;
  trigger_count?: number;
  last_triggered_at?: string;
  schedule_hours?: number;
}
export interface AutomationLog {
  id: number;
  status?: string;
  error_message?: string;
  created_at?: string;
}
export interface ChatMessageLog {
  id: number;
  integration?: number;
  event?: string;
  success?: boolean;
  status_code?: number;
  error?: string;
  created_at?: string;
}
export interface AppNotification {
  id: number;
  read: boolean;
  title?: string;
  body?: string;
  type?: string;
  action_url?: string;
  created_at?: string;
}
export interface EncryptedTaskItem {
  id: number;
  encrypted_data?: string;
  encryptedData?: string;
  encrypted?: boolean;
  created_at?: string;
  shared_by?: number;
  shared_by_email?: string;
  shared_by_display?: string;
}
export interface KeyResult {
  id: number;
  title: string;
  target_value: number;
  current_value: number;
  unit?: string;
  updates?: KeyResultUpdate[];
}
export interface KeyResultUpdate {
  id: number;
  value: number;
  note?: string;
  created_at?: string;
}

export interface ApiKeyItem {
  id: number;
  name: string;
  key_prefix: string;
  scopes?: string[];
  is_active?: boolean;
  last_used_at?: string;
  created_at?: string;
}
export interface AuditLogEntry {
  id: number;
  action: string;
  resource_type?: string;
  resource_id?: number;
  resource_name?: string;
  old_values?: Record<string, unknown>;
  new_values?: Record<string, unknown>;
  ip_address?: string;
  created_at?: string;
}
export interface CapacityEntry {
  project: string;
  project_color?: string;
  total_points: number;
  open_tasks: number;
  in_progress: number;
  blocked: number;
}
export interface NotificationPreference {
  id: number;
  notification_type: string;
  in_app_enabled?: boolean;
  email_enabled?: boolean;
  digest_enabled?: boolean;
}
export interface RecurrenceRuleItem {
  id: number;
  frequency: string;
  interval: number;
  occurrences_generated?: number;
  created_at?: string;
}
export interface TaskTemplateItem {
  id: number;
  name: string;
  description?: string;
  project?: number;
  default_project?: number;
  default_project_name?: string;
  default_priority?: number;
  template_data?: Record<string, unknown>;
}
export interface AttachmentItem {
  id: number;
  filename: string;
  file_size?: number;
  external_url?: string;
  uploaded_at?: string;
}
