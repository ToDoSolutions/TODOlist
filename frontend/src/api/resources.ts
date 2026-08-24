import { api } from "./client";
import type {
  Project,
  Tag,
  Task,
  TaskInput,
  Subtask,
  Comment,
  Paginated,
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
  due_before?: string;
  due_after?: string;
  search?: string;
  ordering?: string;
}

export const tasksApi = {
  list: (filters: TaskFilters = {}) =>
    api
      .get<Paginated<Task> | Task[]>("/tasks/", { params: filters })
      .then((r) => {
        const d = r.data;
        return Array.isArray(d) ? d : d.results;
      }),
  get: (id: number) => api.get<Task>(`/tasks/${id}/`).then((r) => r.data),
  create: (t: TaskInput) => api.post<Task>("/tasks/", t).then((r) => r.data),
  update: (id: number, t: Partial<TaskInput>) =>
    api.patch<Task>(`/tasks/${id}/`, t).then((r) => r.data),
  remove: (id: number) => api.delete(`/tasks/${id}/`),
  addSubtask: (id: number, title: string) =>
    api.post<Subtask>(`/tasks/${id}/subtasks/`, { title }).then((r) => r.data),
  addComment: (id: number, body: string) =>
    api.post<Comment>(`/tasks/${id}/comments/`, { body }).then((r) => r.data),
  updateSubtask: (id: number, data: Partial<Subtask>) =>
    api.patch<Subtask>(`/subtasks/${id}/`, data).then((r) => r.data),
  removeSubtask: (id: number) => api.delete(`/subtasks/${id}/`),
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
        { code, state }
      )
      .then((r) => r.data),

  // Instalaciones
  listInstallations: () =>
    api.get<GitHubInstallation[]>("/github/installations/").then((r) => r.data),
  discoverRepos: () =>
    api
      .post<{ total: number; new: number; message: string }>(
        "/github/installations/discover_repos/"
      )
      .then((r) => r.data),
  removeInstallation: (id: number) =>
    api.delete(`/github/installations/${id}/`),

  // Repos
  listRepos: () =>
    api.get<GitHubRepo[]>("/github/repos/").then((r) => r.data),
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
        { state, label_filter: labelFilter }
      )
      .then((r) => r.data),

  // Links
  listLinks: () =>
    api.get<GitHubIssueLink[]>("/github/links/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d as any).results || [];
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
};
