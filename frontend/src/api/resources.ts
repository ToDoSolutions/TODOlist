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
