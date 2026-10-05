export interface ApiError {
  response?: {
    data?: {
      error?: string;
      detail?: string;
      requires_2fa?: boolean;
      totp_code?: string;
    } & Record<string, unknown>;
  };
}
import type {
  SyncOperationItem,
  GitHubPR,
  GitHubCommit,
  GitHubRelease,
  GitHubCheckRun,
  ChatMessageLog,
  AttachmentItem,
  RecurrenceRuleItem,
  TaskPriority,
} from "../types";
export type ApiPayload = Record<string, unknown>;
export type ApiParams = Record<string, string | number | boolean | undefined>;

/** Desenvuelve respuestas de listado: array plano o sobre paginado
 * DRF ({count,next,results} / cursor {next,results}). */
function unwrapList<T>(data: T[] | { results?: T[] }): T[] {
  return Array.isArray(data) ? data : data.results ?? [];
}

import { z } from "zod";
import { api } from "./client";
import type {
  Project,
  Tag,
  Task,
  TaskInput,
  Subtask,
  Comment,
  Paginated,
  Activity,
  TaskRelation,
  AppNotification,
  NotificationPreference,
  AutomationRule,
  AutomationLog,
  Team,
  TeamMember,
  ProjectMember,
  MentionItem,
  AuditLogEntry,
  ApiKeyItem,
  TimeEntry,
  CustomFieldValue,
  ChatIntegration,
  AiSuggestion,
} from "../types";

export const projectsApi = {
  list: () =>
    api.get<Project[] | Paginated<Project>>("/projects/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (p: Partial<Project>) => api.post<Project>("/projects/", p).then((r) => r.data),
  update: (id: number, p: Partial<Project>) =>
    api.patch<Project>(`/projects/${id}/`, p).then((r) => r.data),
  remove: (id: number) => api.delete(`/projects/${id}/`),
  favorite: (id: number) => api.post(`/projects/${id}/favorite/`).then((r) => r.data),
  unfavorite: (id: number) => api.post(`/projects/${id}/unfavorite/`).then((r) => r.data),
};

export const tagsApi = {
  list: () =>
    api.get<Tag[] | Paginated<Tag>>("/tags/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (t: Partial<Tag>) => api.post<Tag>("/tags/", t).then((r) => r.data),
  update: (id: number, t: Partial<Tag>) =>
    api.patch<Tag>(`/tags/${id}/`, t).then((r) => r.data),
  remove: (id: number) => api.delete(`/tags/${id}/`),
};

export interface TaskFilters {
  state?: string;
  priority?: number;
  project?: number;
  tags?: number;
  sprint?: number;
  epic?: number;
  due_before?: string;
  due_after?: string;
  search?: string;
  ordering?: string;
  /** "true" → solo tareas sin proyecto (bandeja de entrada real). */
  no_project?: string;
  /** "true" → solo vencidas (fecha pasada y no terminadas). */
  overdue?: string;
  /** "true" → solo sin fecha límite. */
  no_due?: string;
  /** "true" → solo asignadas al usuario actual. */
  mine?: string;
  /** "true" → solo tareas marcadas con el tag sla-breached. */
  sla_breached?: string;
  /** "true" → solo favoritas del usuario. */
  favorite?: string;
  /** "true"/"false" → solo hitos / sin hitos. */
  is_milestone?: string;
}

export const tasksApi = {
  list: (filters: TaskFilters = {}) =>
    api.get<Paginated<Task> | Task[]>("/tasks/", { params: filters }).then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  /** Solo el conteo paginado — para badges del sidebar sin traer tareas. */
  count: (filters: TaskFilters = {}) =>
    api
      .get<Paginated<Task> | Task[]>("/tasks/", {
        params: { ...filters, page_size: 1 },
      })
      .then((r) => (Array.isArray(r.data) ? r.data.length : r.data.count)),
  get: (id: number) => api.get<Task>(`/tasks/${id}/`).then((r) => r.data),
  create: (t: TaskInput) => api.post<Task>("/tasks/", t).then((r) => r.data),
  update: (id: number, t: Partial<TaskInput>) =>
    api.patch<Task>(`/tasks/${id}/`, t).then((r) => r.data),
  remove: (id: number) => api.delete(`/tasks/${id}/`),
  addSubtask: (id: number, title: string) =>
    api.post<Subtask>(`/tasks/${id}/subtasks/`, { title }).then((r) => r.data),
  addComment: (id: number, body: string) =>
    api.post<Comment>(`/tasks/${id}/comments/`, { body }).then((r) => r.data),
  updateComment: (id: number, body: string) =>
    api.patch<Comment>(`/comments/${id}/`, { body }).then((r) => r.data),
  removeComment: (id: number) => api.delete(`/comments/${id}/`),
  reactComment: (id: number, emoji: string) =>
    api.post<Comment>(`/comments/${id}/react/`, { emoji }).then((r) => r.data),
  updateSubtask: (id: number, data: Partial<Subtask>) =>
    api.patch<Subtask>(`/subtasks/${id}/`, data).then((r) => r.data),
  removeSubtask: (id: number) => api.delete(`/subtasks/${id}/`),
  reorderSubtasks: (taskId: number, order: number[]) =>
    api.post(`/tasks/${taskId}/subtasks_reorder/`, { order }).then((r) => r.data),
  // Actividad, relaciones, sprint
  getActivities: (id: number) =>
    api.get<Activity[]>(`/tasks/${id}/activities/`).then((r) => r.data),
  getRelations: (id: number) =>
    api.get<TaskRelation[]>(`/tasks/${id}/relations/`).then((r) => r.data),
  addRelation: (id: number, targetId: number, relationType: string) =>
    api
      .post<TaskRelation>(`/tasks/${id}/relations/`, {
        target: targetId,
        relation_type: relationType,
      })
      .then((r) => r.data),
  removeRelation: (id: number) => api.delete(`/task-relations/${id}/`),
  moveToSprint: (id: number, sprintId: number) =>
    api
      .post<{ message: string }>(`/tasks/${id}/move_to_sprint/`, {
        sprint_id: sprintId,
      })
      .then((r) => r.data),
  // Favoritos por usuario (estrella)
  favorite: (id: number) => api.post(`/tasks/${id}/favorite/`).then((r) => r.data),
  unfavorite: (id: number) => api.post(`/tasks/${id}/unfavorite/`).then((r) => r.data),
  // Métricas
  metricsFlow: (days = 30) =>
    api.get(`/tasks/metrics_flow/?days=${days}`).then((r) => r.data),
  metricsBacklog: () => api.get("/tasks/metrics_backlog/").then((r) => r.data),
  metricsDashboard: () => api.get("/tasks/metrics_dashboard/").then((r) => r.data),
  metricsPRs: () => api.get("/tasks/metrics_prs/").then((r) => r.data),
  // Mi trabajo + dependencias + búsqueda global
  myWork: () => api.get<MyWork>("/tasks/my-work/").then((r) => r.data),
  planDay: (data?: {
    date?: string;
    start_hour?: number;
    default_minutes?: number;
    gap_minutes?: number;
    limit?: number;
  }) =>
    api
      .post<DayPlan>("/tasks/plan-day/", data ?? {})
      .then((r) => r.data),
  dependencies: (id: number) =>
    api.get<TaskDependencies>(`/tasks/${id}/dependencies/`).then((r) => r.data),
  globalSearch: (q: string) =>
    api
      .get("/tasks/global-search/", {
        params: { q },
      })
      .then((r) => globalSearchSchema.parse(r.data) as GlobalSearchResults),
};

export interface MyWorkTask {
  id: number;
  title: string;
  state: string;
  priority: number;
  due_date: string | null;
  project: string | null;
  blocked_by?: { id: number; title: string; state: string }[];
}

export interface MyWork {
  overdue: MyWorkTask[];
  due_today: MyWorkTask[];
  in_progress: MyWorkTask[];
  blocked: MyWorkTask[];
  upcoming: MyWorkTask[];
}

export interface DayPlanSlot {
  id: number;
  title: string;
  start: string;
  end: string;
  minutes: number;
}

export interface DayPlan {
  date: string;
  slots: DayPlanSlot[];
}

export interface TaskDependencies {
  task_id: number;
  is_blocked: boolean;
  blocked_by: { task_id: number; title: string; state: string; relation: string }[];
  blocks: { task_id: number; title: string; state: string; relation: string }[];
  related: { task_id: number; title: string; relation: string }[];
}

const searchItemSchema = z
  .object({
    type: z.string(),
    id: z.number(),
    title: z.string(),
  })
  .passthrough();

const globalSearchSchema = z.object({
  query: z.string().default(""),
  filters: z.record(z.array(z.string())).default({}),
  tasks: z.array(searchItemSchema).default([]),
  comments: z.array(searchItemSchema).default([]),
  wiki: z.array(searchItemSchema).default([]),
  projects: z.array(searchItemSchema).default([]),
});

export type GlobalSearchResults = z.infer<typeof globalSearchSchema> & {
  tasks: {
    type: string;
    id: number;
    title: string;
    state: string;
    priority: number;
    project: string | null;
  }[];
  comments: {
    type: string;
    id: number;
    title: string;
    task: { id: number; title: string };
  }[];
  wiki: { type: string; id: number; title: string; project: string | null }[];
  projects: { type: string; id: number; title: string; is_archived: boolean }[];
};

export const notificationsApi = {
  list: () =>
    api
      .get<AppNotification[] | Paginated<AppNotification>>("/notifications/")
      .then((r) => unwrapList(r.data)),
  unreadCount: () =>
    api.get<{ count: number }>("/notifications/unread_count/").then((r) => r.data),
  markAllRead: () => api.post("/notifications/mark_all_read/").then((r) => r.data),
  markRead: (id: number) =>
    api.post(`/notifications/${id}/mark_read/`).then((r) => r.data),
  markUnread: (id: number) =>
    api.post(`/notifications/${id}/mark_unread/`).then((r) => r.data),
  preferences: () =>
    api
      .get<NotificationPreference[] | Paginated<NotificationPreference>>(
        "/notification-preferences/",
      )
      .then((r) => unwrapList(r.data)),
  updatePreference: (id: number, data: ApiPayload) =>
    api.patch(`/notification-preferences/${id}/`, data).then((r) => r.data),
};

export const automationsApi = {
  list: () =>
    api
      .get<AutomationRule[] | Paginated<AutomationRule>>("/automation-rules/")
      .then((r) => unwrapList(r.data)),
  create: (data: ApiPayload) => api.post("/automation-rules/", data).then((r) => r.data),
  update: (id: number, data: ApiPayload) =>
    api.patch(`/automation-rules/${id}/`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/automation-rules/${id}/`).then((r) => r.data),
  test: (id: number) => api.post(`/automation-rules/${id}/test/`).then((r) => r.data),
  logs: (id: number) =>
    api
      .get<AutomationLog[] | Paginated<AutomationLog>>(
        `/automation-rules/${id}/logs/`,
      )
      .then((r) => unwrapList(r.data)),
  allLogs: () =>
    api.get("/automation-logs/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
};

export interface SlaPolicy {
  id: number;
  name: string;
  priority: TaskPriority;
  response_hours: number;
  resolution_hours: number;
  bump_priority: boolean;
  notify_owner: boolean;
  notify_assignee: boolean;
  enabled: boolean;
}

export const slaPoliciesApi = {
  list: () =>
    api.get<Paginated<SlaPolicy> | SlaPolicy[]>("/sla-policies/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (p: Partial<SlaPolicy>) =>
    api.post<SlaPolicy>("/sla-policies/", p).then((r) => r.data),
  update: (id: number, p: Partial<SlaPolicy>) =>
    api.patch<SlaPolicy>(`/sla-policies/${id}/`, p).then((r) => r.data),
  remove: (id: number) => api.delete(`/sla-policies/${id}/`),
};

export interface DashboardWidget {
  id?: string;
  type: string;
  title?: string;
  size?: string;
  config?: Record<string, unknown>;
}

export interface Dashboard {
  id: number;
  name: string;
  widgets: DashboardWidget[];
  is_default: boolean;
  shared_with: { id: number; email: string }[];
  is_owner: boolean;
  created_at: string;
  updated_at: string;
}

export interface ResolvedWidget {
  id?: string;
  type: string;
  title?: string;
  size?: string;
  data: Record<string, unknown> & { error?: string };
}

export const dashboardsApi = {
  list: () =>
    api.get<Paginated<Dashboard> | Dashboard[]>("/dashboards/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  get: (id: number) => api.get<Dashboard>(`/dashboards/${id}/`).then((r) => r.data),
  create: (p: Partial<Dashboard>) =>
    api.post<Dashboard>("/dashboards/", p).then((r) => r.data),
  update: (id: number, p: Partial<Dashboard>) =>
    api.patch<Dashboard>(`/dashboards/${id}/`, p).then((r) => r.data),
  remove: (id: number) => api.delete(`/dashboards/${id}/`),
  data: (id: number) =>
    api
      .get<{ dashboard: string; widgets: ResolvedWidget[] }>(`/dashboards/${id}/data/`)
      .then((r) => r.data),
  widgetTypes: () => api.get<string[]>("/dashboards/widget_types/").then((r) => r.data),
  share: (id: number, email: string) =>
    api.post<Dashboard>(`/dashboards/${id}/share/`, { email }).then((r) => r.data),
  unshare: (id: number, email: string) =>
    api.post<Dashboard>(`/dashboards/${id}/unshare/`, { email }).then((r) => r.data),
};

export const collaborationApi = {
  // Teams
  teams: {
    list: () =>
      api.get<Team[] | Paginated<Team>>("/teams/").then((r) => unwrapList(r.data)),
    create: (data: ApiPayload) => api.post("/teams/", data).then((r) => r.data),
    update: (id: number, data: ApiPayload) =>
      api.patch(`/teams/${id}/`, data).then((r) => r.data),
    remove: (id: number) => api.delete(`/teams/${id}/`),
    members: (teamId: number) =>
      api
        .get<TeamMember[] | Paginated<TeamMember>>(`/teams/${teamId}/members/`)
        .then((r) => unwrapList(r.data)),
    addMember: (teamId: number, userId: number, role: string) =>
      api
        .post(`/teams/${teamId}/members/`, { user_id: userId, role })
        .then((r) => r.data),
    removeMember: (teamId: number, memberId: number) =>
      api.delete(`/teams/${teamId}/members/${memberId}/`).then((r) => r.data),
  },
  // Project members
  projectMembers: {
    list: (projectId: number) =>
      api
        .get<ProjectMember[] | Paginated<ProjectMember>>(
          `/project-members/?project=${projectId}`,
        )
        .then((r) => unwrapList(r.data)),
    invite: (projectId: number, data: { email: string; role: string }) =>
      api
        .post("/project-members/invite/", {
          email: data.email,
          project_id: projectId,
          role: data.role,
        })
        .then((r) => r.data),
    update: (id: number, data: { role?: string }) =>
      api.patch(`/project-members/${id}/`, data).then((r) => r.data),
    remove: (id: number) => api.delete(`/project-members/${id}/`),
  },
  // Mentions
  mentions: {
    list: () =>
      api
        .get<MentionItem[] | Paginated<MentionItem>>("/mentions/")
        .then((r) => unwrapList(r.data)),
  },
  // Audit logs
  auditLogs: {
    list: (params?: ApiParams) =>
      api
        .get<AuditLogEntry[] | Paginated<AuditLogEntry>>("/audit-logs/", {
          params,
        })
        .then((r) => unwrapList(r.data)),
    // Export SIEM: blob descargable (csv|jsonl) — fmt, no format
    // (DRF reserva "format" para content negotiation).
    export: (fmt: "csv" | "jsonl") =>
      api
        .get("/audit-logs/export/", {
          params: { fmt },
          responseType: "blob",
        })
        .then((r) => r.data as Blob),
  },
};

export const apiKeysApi = {
  list: () =>
    api
      .get<ApiKeyItem[] | Paginated<ApiKeyItem>>("/api-keys/")
      .then((r) => unwrapList(r.data)),
  create: (data: { name: string; scopes?: string[] }) =>
    api.post("/api-keys/", data).then((r) => r.data),
  revoke: (id: number) => api.post(`/api-keys/${id}/revoke/`).then((r) => r.data),
  delete: (id: number) => api.delete(`/api-keys/${id}/`).then((r) => r.data),
};

export const twofactorApi = {
  status: () => api.get("/auth/2fa/").then((r) => r.data),
  setup: () => api.post("/auth/2fa/", { action: "setup" }).then((r) => r.data),
  confirm: (code: string) =>
    api.post("/auth/2fa/", { action: "confirm", code }).then((r) => r.data),
  disable: (code: string) =>
    api.delete("/auth/2fa/", { data: { code } }).then((r) => r.data),
};

export const timeEntriesApi = {
  list: () =>
    api
      .get<TimeEntry[] | Paginated<TimeEntry>>("/time-entries/")
      .then((r) => unwrapList(r.data)),
  create: (data: ApiPayload) => api.post("/time-entries/", data).then((r) => r.data),
  update: (id: number, data: ApiPayload) =>
    api.patch(`/time-entries/${id}/`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/time-entries/${id}/`).then((r) => r.data),
};

export const taskTemplatesApi = {
  list: () =>
    api.get("/task-templates/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (data: ApiPayload) => api.post("/task-templates/", data).then((r) => r.data),
  update: (id: number, data: ApiPayload) =>
    api.patch(`/task-templates/${id}/`, data).then((r) => r.data),
  createTask: (id: number, overrides?: ApiPayload) =>
    api.post(`/task-templates/${id}/create_task/`, { overrides }).then((r) => r.data),
  delete: (id: number) => api.delete(`/task-templates/${id}/`).then((r) => r.data),
};

export const customFieldsApi = {
  list: () =>
    api.get("/custom-fields/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (data: ApiPayload) => api.post("/custom-fields/", data).then((r) => r.data),
  update: (id: number, data: ApiPayload) =>
    api.patch(`/custom-fields/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/custom-fields/${id}/`),
  values: (params?: { task?: number; field?: number }) =>
    api
      .get<CustomFieldValue[] | Paginated<CustomFieldValue>>(
        "/custom-field-values/",
        { params },
      )
      .then((r) => unwrapList(r.data)),
  setValue: (data: ApiPayload) =>
    api.post("/custom-field-values/", data).then((r) => r.data),
  updateValue: (id: number, value: unknown) =>
    api.patch(`/custom-field-values/${id}/`, { value }).then((r) => r.data),
  removeValue: (id: number) => api.delete(`/custom-field-values/${id}/`),
};

export const outgoingWebhooksApi = {
  list: () =>
    api.get("/outgoing-webhooks/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (data: ApiPayload) => api.post("/outgoing-webhooks/", data).then((r) => r.data),
  update: (id: number, data: ApiPayload) =>
    api.patch(`/outgoing-webhooks/${id}/`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/outgoing-webhooks/${id}/`).then((r) => r.data),
  test: (id: number) => api.post(`/outgoing-webhooks/${id}/test/`).then((r) => r.data),
  deliveries: () =>
    api.get("/webhooks/deliveries/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: unknown[] }).results || [];
    }),
  retryDeadLetter: () =>
    api.post<{ message: string }>("/webhooks/retry-dead-letter/").then((r) => r.data),
};

export const bulkOpsApi = {
  update: (taskIds: number[], updates: ApiPayload) =>
    api.post("/tasks/bulk_update/", { task_ids: taskIds, updates }).then((r) => r.data),
  delete: (taskIds: number[]) =>
    api.post("/tasks/bulk_delete/", { task_ids: taskIds }).then((r) => r.data),
  moveSprint: (taskIds: number[], sprintId: number) =>
    api
      .post("/tasks/bulk_move_sprint/", { task_ids: taskIds, sprint_id: sprintId })
      .then((r) => r.data),
};

export const searchApi = {
  tasks: (q: string) =>
    api.get(`/tasks/search/?q=${encodeURIComponent(q)}`).then((r) => r.data),
};

// OKRs
export const okrsApi = {
  listObjectives: () =>
    api.get("/objectives/").then((r) => unwrapList<Record<string, unknown>>(r.data)),
  createObjective: (data: ApiPayload) =>
    api.post("/objectives/", data).then((r) => r.data),
  updateObjective: (id: number, data: ApiPayload) =>
    api.patch(`/objectives/${id}/`, data).then((r) => r.data),
  deleteObjective: (id: number) => api.delete(`/objectives/${id}/`).then((r) => r.data),
  createKeyResult: (data: ApiPayload) =>
    api.post("/key-results/", data).then((r) => r.data),
  updateKeyResult: (id: number, data: ApiPayload) =>
    api.patch(`/key-results/${id}/`, data).then((r) => r.data),
  deleteKeyResult: (id: number) => api.delete(`/key-results/${id}/`).then((r) => r.data),
  updateValue: (id: number, newValue: number, note: string) =>
    api
      .post(`/key-results/${id}/update_value/`, { new_value: newValue, note })
      .then((r) => r.data),
};

// Feature flags
export const featureFlagsApi = {
  list: () =>
    api.get("/feature-flags/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (data: ApiPayload) => api.post("/feature-flags/", data).then((r) => r.data),
  update: (id: number, data: ApiPayload) =>
    api.patch(`/feature-flags/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/feature-flags/${id}/`),
  check: (key: string) => api.get(`/feature-flags/${key}/check/`).then((r) => r.data),
};

// AI assistant
export const aiApi = {
  estimatePriority: (taskId: number) =>
    api.post("/ai/estimate-priority/", { task_id: taskId }).then((r) => r.data),
  estimateStoryPoints: (taskId: number) =>
    api.post("/ai/estimate-story-points/", { task_id: taskId }).then((r) => r.data),
  detectBlockers: () => api.get("/ai/detect-blockers/").then((r) => r.data),
  improveDescription: (taskId: number) =>
    api.post("/ai/improve-description/", { task_id: taskId }).then((r) => r.data),
  suggestions: () =>
    api
      .get<AiSuggestion[] | Paginated<AiSuggestion>>("/ai/suggestions/")
      .then((r) => unwrapList(r.data)),
  suggestionAction: (id: number, action: "accept" | "reject" | "apply") =>
    api.post(`/ai/suggestions/${id}/action/`, { action }).then((r) => r.data),
};

// Chat integrations
export const chatIntegrationsApi = {
  list: () =>
    api
      .get<ChatIntegration[] | Paginated<ChatIntegration>>("/chat-integrations/")
      .then((r) => unwrapList(r.data)),
  create: (data: ApiPayload) => api.post("/chat-integrations/", data).then((r) => r.data),
  update: (id: number, data: ApiPayload) =>
    api.patch(`/chat-integrations/${id}/`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/chat-integrations/${id}/`).then((r) => r.data),
  test: (id: number) => api.post(`/chat-integrations/${id}/test/`).then((r) => r.data),
};

// Advanced metrics
export const advancedMetricsApi = {
  gantt: () => api.get("/tasks/gantt/").then((r) => r.data),
  burndown: (sprintId: number) =>
    api.get(`/tasks/burndown/?sprint_id=${sprintId}`).then((r) => r.data),
  burnup: (sprintId: number) =>
    api.get(`/tasks/burnup/?sprint_id=${sprintId}`).then((r) => r.data),
  capacity: () => api.get("/tasks/capacity/").then((r) => r.data),
  roadmap: () => api.get("/tasks/roadmap/").then((r) => r.data),
  velocity: () => api.get("/tasks/velocity/").then((r) => r.data),
};

// Offline sync
export interface SyncDeviceItem {
  id: number;
  device_id: string;
  device_name: string;
  last_sync_at: string | null;
  is_active: boolean;
  created_at: string;
}

export const offlineSyncApi = {
  registerDevice: (deviceId: string, deviceName: string) =>
    api
      .post("/sync/register-device/", { device_id: deviceId, device_name: deviceName })
      .then((r) => r.data),
  push: (operations: ApiPayload[]) =>
    api.post("/sync/push/", { operations }).then((r) => r.data),
  pull: (since: string) => api.get(`/sync/pull/?since=${since}`).then((r) => r.data),
  listDevices: () =>
    api
      .get<{ results: SyncDeviceItem[] } | SyncDeviceItem[]>("/sync/devices/")
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
  revokeDevice: (deviceId: string) =>
    api.post(`/sync/devices/${deviceId}/revoke/`).then((r) => r.data),
  removeDevice: (deviceId: string) =>
    api.delete(`/sync/devices/${deviceId}/`).then((r) => r.data),
  revokeAllDevices: () => api.post("/sync/devices/revoke_all/").then((r) => r.data),
};

// E2E Encryption
export const encryptionApi = {
  registerPublicKey: (
    publicKey: string,
    keyId: string,
    algorithm: string = "RSA-OA-256",
  ) =>
    api
      .post("/public-keys/", { public_key: publicKey, key_id: keyId, algorithm })
      .then((r) => r.data),
  getActiveKey: () => api.get("/public-keys/active/").then((r) => r.data),
  // Clave pública activa de otro usuario (para cifrarle un key share)
  lookupPublicKey: (email: string) =>
    api
      .get<{ id: number; public_key: string; key_id: string; algorithm: string }>(
        "/public-keys/lookup/",
        { params: { email } },
      )
      .then((r) => r.data),
  createEncryptedTask: (data: ApiPayload) =>
    api.post("/encrypted-tasks/", data).then((r) => r.data),
  listEncryptedTasks: () =>
    api.get("/encrypted-tasks/").then((r) => unwrapList(r.data)),
  shareTask: (
    taskId: number,
    userEmail: string,
    encryptedKey: string,
    publicKeyId: number,
  ) =>
    api
      .post(`/encrypted-tasks/${taskId}/share/`, {
        user_email: userEmail,
        encrypted_key: encryptedKey,
        public_key_id: publicKeyId,
      })
      .then((r) => r.data),
  sharedTasks: () => api.get("/encrypted-tasks/shared/").then((r) => r.data),
};

// --- Sprints ---

export interface Sprint {
  id: number;
  name: string;
  goal: string;
  description: string;
  state: "planned" | "active" | "closed";
  start_date: string;
  end_date: string;
  project: number | null;
  task_count: number;
  created_at: string;
  updated_at: string;
}

export const sprintsApi = {
  list: () =>
    api.get<Paginated<Sprint> | Sprint[]>("/sprints/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (s: Partial<Sprint>) => api.post<Sprint>("/sprints/", s).then((r) => r.data),
  update: (id: number, s: Partial<Sprint>) =>
    api.patch<Sprint>(`/sprints/${id}/`, s).then((r) => r.data),
  remove: (id: number) => api.delete(`/sprints/${id}/`),
  getTasks: (id: number) =>
    api.get<Paginated<Task> | Task[]>(`/sprints/${id}/tasks/`).then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  /** Métricas del sprint: conteos por estado, puntos, scope creep. */
  getMetrics: (id: number) =>
    api.get<SprintMetrics>(`/sprints/${id}/metrics/`).then((r) => r.data),
};

export interface SprintMetrics {
  sprint_name: string;
  sprint_state: string;
  total_tasks: number;
  done: number;
  in_progress: number;
  blocked: number;
  pending: number;
  story_points_total: number;
  story_points_done: number;
  progress_pct: number;
  added_after_start: number;
  scope_creep_pct: number;
}

// --- Epics ---

export interface Epic {
  id: number;
  title: string;
  description: string;
  state: "planned" | "in_progress" | "completed" | "cancelled";
  color: string;
  start_date: string | null;
  end_date: string | null;
  project: number | null;
  progress_done: number;
  progress_total: number;
  created_at: string;
  updated_at: string;
}

export const epicsApi = {
  list: () =>
    api.get<Paginated<Epic> | Epic[]>("/epics/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (e: Partial<Epic>) => api.post<Epic>("/epics/", e).then((r) => r.data),
  update: (id: number, e: Partial<Epic>) =>
    api.patch<Epic>(`/epics/${id}/`, e).then((r) => r.data),
  remove: (id: number) => api.delete(`/epics/${id}/`),
  getTasks: (id: number) =>
    api.get<Paginated<Task> | Task[]>(`/epics/${id}/tasks/`).then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
};

// --- Saved Searches ---

export interface SavedSearch {
  id: number;
  name: string;
  filters: string; // JSON serializado: la API lo devuelve como string, se hace JSON.parse al cargar
  is_shared: boolean;
  /** Sólo del serializer: distinguir mis búsquedas de las compartidas ajenas. */
  is_owner?: boolean;
  created_at: string;
  updated_at: string;
}

export const savedSearchesApi = {
  list: () =>
    api.get<Paginated<SavedSearch> | SavedSearch[]>("/saved-searches/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (s: Partial<SavedSearch>) =>
    api.post<SavedSearch>("/saved-searches/", s).then((r) => r.data),
  update: (id: number, s: Partial<SavedSearch>) =>
    api.patch<SavedSearch>(`/saved-searches/${id}/`, s).then((r) => r.data),
  remove: (id: number) => api.delete(`/saved-searches/${id}/`),
};

// --- GitHub Integration ---

export interface GitHubInstallation {
  id: number;
  installation_id: number;
  account_login: string;
  account_type: string;
  avatar_url: string;
  github_username: string;
  created_at: string;
}

export interface GitHubRepo {
  id: number;
  repo_id: number;
  full_name: string;
  name: string;
  owner: string;
  is_private: boolean;
  sync_enabled: boolean;
  default_branch: string;
  created_at: string;
}

export interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  state: string;
  html_url: string;
  body: string;
  labels: string[];
  already_linked: boolean;
}

export interface GitHubIssueLink {
  id: number;
  task: number;
  repo: number;
  repo_full_name: string;
  issue_number: number;
  issue_url: string;
  issue_state: string;
  last_synced_at: string | null;
  created_at: string;
}

export const githubApi = {
  // OAuth
  getOAuthUrl: () =>
    api
      .get<{ auth_url: string; state: string }>("/auth/github/start/")
      .then((r) => r.data),
  oauthCallback: (code: string, state: string) =>
    api
      .post<{ access: string; refresh: string; github_username: string }>(
        "/auth/github/callback/",
        { code, state },
      )
      .then((r) => r.data),
  getProviders: () =>
    api
      .get<{ github: boolean; google: boolean }>("/auth/oauth-providers/")
      .then((r) => r.data),

  // Instalaciones
  listInstallations: () =>
    api
      .get<GitHubInstallation[] | Paginated<GitHubInstallation>>(
        "/github/installations/",
      )
      .then((r) => unwrapList(r.data)),
  discoverRepos: () =>
    api
      .post<{ total: number; new: number; message: string }>(
        "/github/installations/discover_repos/",
      )
      .then((r) => r.data),
  removeInstallation: (id: number) => api.delete(`/github/installations/${id}/`),

  // Repos
  listRepos: () =>
    api
      .get<GitHubRepo[] | Paginated<GitHubRepo>>("/github/repos/")
      .then((r) => unwrapList(r.data)),
  updateRepo: (id: number, data: Partial<GitHubRepo>) =>
    api.patch<GitHubRepo>(`/github/repos/${id}/`, data).then((r) => r.data),
  syncRepo: (id: number) =>
    api.post<{ message: string }>(`/github/repos/${id}/sync/`).then((r) => r.data),
  listRepoIssues: (id: number, state = "open") =>
    api
      .get<{ results: GitHubIssue[] }>(`/github/repos/${id}/issues/`, {
        params: { state },
      })
      .then((r) => r.data.results),
  importIssues: (id: number, state = "open", labelFilter = "") =>
    api
      .post<{ imported: number; skipped: number; total: number }>(
        `/github/repos/${id}/import_issues/`,
        { state, label_filter: labelFilter },
      )
      .then((r) => r.data),

  // Links
  listLinks: () =>
    api.get<GitHubIssueLink[]>("/github/links/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: GitHubIssueLink[] }).results || [];
    }),
  createLinkForTask: (taskId: number, repoId: number) =>
    api
      .post<GitHubIssueLink>("/github/links/create_for_task/", {
        task_id: taskId,
        repo_id: repoId,
      })
      .then((r) => r.data),
  syncLink: (id: number) =>
    api.post<{ message: string }>(`/github/links/${id}/sync/`).then((r) => r.data),

  // Pull Requests
  listPullRequests: () =>
    api.get<GitHubPR[]>("/github/prs/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: GitHubPR[] }).results || [];
    }),
  linkPrToTask: (prId: number, taskId: number) =>
    api
      .post<{ message: string }>(`/github/prs/${prId}/link_task/`, {
        task_id: taskId,
      })
      .then((r) => r.data),
  // Commits
  listCommits: () =>
    api.get<GitHubCommit[]>("/github/commits/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: GitHubCommit[] }).results || [];
    }),
  // Releases
  listReleases: () =>
    api.get<GitHubRelease[]>("/github/releases/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: GitHubRelease[] }).results || [];
    }),
  // Check Runs (CI)
  listChecks: () =>
    api.get<GitHubCheckRun[]>("/github/checks/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: GitHubCheckRun[] }).results || [];
    }),
};

// --- Attachments ---

export const attachmentsApi = {
  list: (taskId?: number) =>
    api
      .get<AttachmentItem[]>("/attachments/", { params: taskId ? { task: taskId } : {} })
      .then((r) => {
        const d = r.data;
        return Array.isArray(d) ? d : (d as { results?: AttachmentItem[] }).results || [];
      }),
  upload: (taskId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("task", String(taskId));
    return api
      .post<Record<string, unknown>>("/attachments/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  createLink: (taskId: number, externalUrl: string, name?: string) =>
    api
      .post<Record<string, unknown>>("/attachments/", {
        task: taskId,
        external_url: externalUrl,
        filename: name || externalUrl,
      })
      .then((r) => r.data),
  remove: (id: number) => api.delete(`/attachments/${id}/`),
};

// --- Recurrence Rules ---

export const recurrenceRulesApi = {
  list: () =>
    api.get<RecurrenceRuleItem[]>("/recurrence-rules/").then((r) => {
      const d = r.data;
      return Array.isArray(d)
        ? d
        : (d as { results?: RecurrenceRuleItem[] }).results || [];
    }),
  create: (data: ApiPayload) =>
    api.post<Record<string, unknown>>("/recurrence-rules/", data).then((r) => r.data),
  remove: (id: number) => api.delete(`/recurrence-rules/${id}/`),
};

// --- User account ---

export const userApi = {
  // Token opaco para suscribir el feed iCal desde clientes de calendario
  // (no pueden enviar JWT). POST rota el token; DELETE lo revoca.
  calendarToken: () =>
    api
      .post<{ ical_token: string; feed_url: string }>("/users/me/calendar_token/")
      .then((r) => r.data),
  calendarTokenRevoke: () => api.delete("/users/me/calendar_token/").then((r) => r.data),
  // Dirección email-to-task: cualquier correo a task-<token>@ crea una tarea
  emailToken: () =>
    api
      .post<{ inbound_email_token: string }>("/users/me/email_token/")
      .then((r) => r.data),
  emailTokenRevoke: () => api.delete("/users/me/email_token/").then((r) => r.data),
  deactivate: (password: string) =>
    api.post("/users/me/deactivate/", { password }).then((r) => r.data),
  deleteAccount: (password: string) =>
    api
      .delete("/users/me/delete_account/?confirm=true", { data: { password } })
      .then((r) => r.data),
};

// --- Invitations ---

export const invitationsApi = {
  list: () =>
    api.get<Record<string, unknown>>("/invitations/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: unknown[] }).results || [];
    }),
  accept: (id: number) => api.post(`/invitations/${id}/accept/`).then((r) => r.data),
  decline: (id: number) => api.post(`/invitations/${id}/decline/`).then((r) => r.data),
};

// --- Sync Operations ---

export const syncOperationsApi = {
  list: () =>
    api.get<SyncOperationItem[]>("/sync/operations/").then((r) => {
      const d = r.data;
      return Array.isArray(d)
        ? d
        : (d as { results?: SyncOperationItem[] }).results || [];
    }),
};

// --- Chat Message Logs ---

export const chatLogsApi = {
  list: () =>
    api.get<ChatMessageLog[]>("/chat-logs/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as { results?: ChatMessageLog[] }).results || [];
    }),
};

// --- Wiki ---
export interface WikiPageItem {
  id: number;
  title: string;
  content: string;
  project: number | null;
  parent: number | null;
  version: number;
  children_count: number;
  updated_by_email: string | null;
  updated_at: string;
}

export interface WikiRevision {
  version: number;
  title: string;
  edited_by: number | null;
  created_at: string;
}

export interface WikiRevisionDetail extends WikiRevision {
  content: string;
}

export const wikiApi = {
  list: () =>
    api
      .get<{ results: WikiPageItem[] } | WikiPageItem[]>("/wiki/")
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
  create: (data: Partial<WikiPageItem>) =>
    api.post<WikiPageItem>("/wiki/", data).then((r) => r.data),
  update: (id: number, data: Partial<WikiPageItem>) =>
    api.patch<WikiPageItem>(`/wiki/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/wiki/${id}/`),
  revisions: (id: number) =>
    api.get<WikiRevision[]>(`/wiki/${id}/revisions/`).then((r) => r.data),
  revisionDetail: (id: number, version: number) =>
    api
      .get<WikiRevisionDetail>(`/wiki/${id}/revisions/${version}/`)
      .then((r) => r.data),
  restore: (id: number, version: number) =>
    api
      .post<WikiPageItem>(`/wiki/${id}/restore/`, { version })
      .then((r) => r.data),
};

// --- Organizations (tenant raíz) ---

export interface OrganizationItem {
  id: number;
  name: string;
  slug: string;
  description: string;
  member_count: number;
  sso_domain?: string | null;
  sso_required?: boolean;
  created_at: string;
}

export const organizationsApi = {
  list: () =>
    api
      .get<{ results: OrganizationItem[] } | OrganizationItem[]>("/organizations/")
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
  create: (data: { name: string; description?: string }) =>
    api.post<OrganizationItem>("/organizations/", data).then((r) => r.data),
  update: (id: number, data: Partial<OrganizationItem>) =>
    api.patch<OrganizationItem>(`/organizations/${id}/`, data).then((r) => r.data),
  addMember: (id: number, email: string, role = "member") =>
    api.post(`/organizations/${id}/add_member/`, { email, role }).then((r) => r.data),
};

// --- Risks (project risks) ---

export interface ProjectRiskItem {
  id: number;
  project: number;
  title: string;
  description: string;
  probability: "low" | "medium" | "high";
  impact: "low" | "medium" | "high";
  severity: number;
  status: "open" | "mitigated" | "closed" | "realized";
  mitigation: string;
  owner_email: string | null;
  created_at: string;
}

export const risksApi = {
  list: (projectId?: number) =>
    api
      .get<{ results: ProjectRiskItem[] } | ProjectRiskItem[]>("/project-risks/", {
        params: projectId ? { project: projectId } : {},
      })
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
  create: (data: Partial<ProjectRiskItem>) =>
    api.post<ProjectRiskItem>("/project-risks/", data).then((r) => r.data),
  update: (id: number, data: Partial<ProjectRiskItem>) =>
    api.patch<ProjectRiskItem>(`/project-risks/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/project-risks/${id}/`),
};

// --- Meetings ---

export interface MeetingItem {
  id: number;
  project: number | null;
  title: string;
  scheduled_at: string;
  duration_minutes: number;
  attendees: number[];
  attendees_emails: string[];
  notes: string;
  decisions: string;
  tasks_ids: number[];
  created_at: string;
  updated_at: string;
}

export const meetingsApi = {
  list: (projectId?: number) =>
    api
      .get<{ results: MeetingItem[] } | MeetingItem[]>("/meetings/", {
        params: projectId ? { project: projectId } : {},
      })
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
  create: (data: Partial<MeetingItem>) =>
    api.post<MeetingItem>("/meetings/", data).then((r) => r.data),
  update: (id: number, data: Partial<MeetingItem>) =>
    api.patch<MeetingItem>(`/meetings/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/meetings/${id}/`),
  createTask: (id: number, title: string) =>
    api.post(`/meetings/${id}/create_task/`, { title }).then((r) => r.data),
};

// --- Intake forms ---

export interface IntakeFormField {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
}

export interface IntakeFormItem {
  id: number;
  name: string;
  description: string;
  project: number;
  enabled: boolean;
  // La API guarda la lista plana de campos; el objeto {fields} es el
  // shape legacy. Normalizar con intakeFields() antes de usarlo.
  schema: IntakeFormField[] | { fields: IntakeFormField[] };
  task_defaults?: Record<string, unknown>;
  submissions_count?: number;
  created_at: string;
}

export function intakeFields(
  schema: IntakeFormItem["schema"] | undefined,
): IntakeFormField[] {
  if (!schema) return [];
  return Array.isArray(schema) ? schema : (schema.fields ?? []);
}

export const intakeFormsApi = {
  list: (projectId?: number) =>
    api
      .get<{ results: IntakeFormItem[] } | IntakeFormItem[]>("/intake-forms/", {
        params: projectId ? { project: projectId } : {},
      })
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
  create: (data: Partial<IntakeFormItem>) =>
    api.post<IntakeFormItem>("/intake-forms/", data).then((r) => r.data),
  update: (id: number, data: Partial<IntakeFormItem>) =>
    api.patch<IntakeFormItem>(`/intake-forms/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/intake-forms/${id}/`),
  submit: (id: number, values: Record<string, unknown>) =>
    api.post(`/intake-forms/${id}/submit/`, values).then((r) => r.data),
};

export interface IntakeSubmissionItem {
  id: number;
  form: number;
  data: Record<string, unknown>;
  task_id: number | null;
  task_title: string | null;
  submitted_by_email: string;
  created_at: string;
}

export const intakeSubmissionsApi = {
  list: (formId: number) =>
    api
      .get<{ results: IntakeSubmissionItem[] } | IntakeSubmissionItem[]>(
        "/intake-submissions/",
        { params: { form: formId } },
      )
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
};

// --- Workflow transitions ---

export interface WorkflowTransitionItem {
  id: number;
  project: number;
  from_state: string;
  to_state: string;
  created_at: string;
}

export const workflowApi = {
  list: (projectId?: number) =>
    api
      .get<{ results: WorkflowTransitionItem[] } | WorkflowTransitionItem[]>(
        "/workflow-transitions/",
        {
          params: projectId ? { project: projectId } : {},
        },
      )
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
  create: (data: { project: number; from_state: string; to_state: string }) =>
    api.post<WorkflowTransitionItem>("/workflow-transitions/", data).then((r) => r.data),
  remove: (id: number) => api.delete(`/workflow-transitions/${id}/`),
};

// --- Activity feed global ---

export interface ActivityItem {
  kind: "task_activity" | "audit";
  action: string;
  actor: string | null;
  resource: string;
  summary: string;
  created_at: string;
}

export const activityFeedApi = {
  list: (limit = 50) =>
    api
      .get<{ results: ActivityItem[] } | ActivityItem[]>("/activity-feed/", {
        params: { limit },
      })
      .then((r) => (Array.isArray(r.data) ? r.data : r.data.results)),
};
