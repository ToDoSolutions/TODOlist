/**
 * API de funciones "comp" (batch complementario):
 * - Salud de proyecto: PATCH /projects/{id}/ {health} + registro histórico
 *   /project-status-updates/ (POST crea entrada y sincroniza project.health).
 * - Capacidad semanal del usuario: /users/me/ (weekly_capacity_hours).
 * - Vinculación KeyResult ↔ tareas: PATCH /key-results/{id}/ {linked_tasks}.
 *
 * Separada de resources.ts porque pertenece a un batch de features distinto;
 * reutiliza el mismo cliente axios (auth por cookie + CSRF + refresh).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { TaskState, User } from "../types";

type ListResponse<T> = T[] | { results: T[] };

function unwrap<T>(d: ListResponse<T>): T[] {
  return Array.isArray(d) ? d : d.results;
}

// --- Salud de proyecto ---

export type ProjectHealth = "on_track" | "at_risk" | "off_track";

export const PROJECT_HEALTHS: ProjectHealth[] = ["on_track", "at_risk", "off_track"];

/** Color de Chip MUI por salud. */
export const HEALTH_CHIP_COLORS: Record<ProjectHealth, "success" | "warning" | "error"> =
  {
    on_track: "success",
    at_risk: "warning",
    off_track: "error",
  };

/** Color sx (palette path) por salud, para bullets/puntos. */
export const HEALTH_SX_COLORS: Record<ProjectHealth, string> = {
  on_track: "success.main",
  at_risk: "warning.main",
  off_track: "error.main",
};

export interface ProjectStatusUpdate {
  id: number;
  project: number;
  author_email: string;
  health: ProjectHealth;
  note: string;
  created_at: string;
}

/**
 * Campos extra que el ProjectSerializer expone además de `Project`
 * (salud manual + última actualización de estado).
 */
export interface ProjectHealthFields {
  health: ProjectHealth | null;
  latest_status_update: ProjectStatusUpdate | null;
}

export const projectStatusUpdatesApi = {
  /** Historial de un proyecto (?project=N), ordenado por el backend. */
  list: (projectId: number) =>
    api
      .get<ListResponse<ProjectStatusUpdate>>("/project-status-updates/", {
        params: { project: projectId },
      })
      .then((r) => unwrap(r.data)),
  /** Crear una actualización también sincroniza project.health. */
  create: (data: { project: number; health: ProjectHealth; note: string }) =>
    api.post<ProjectStatusUpdate>("/project-status-updates/", data).then((r) => r.data),
};

/** Cambia solo la salud del proyecto (sin crear registro en el historial). */
export function setProjectHealth(id: number, health: ProjectHealth | null) {
  return api.patch(`/projects/${id}/`, { health }).then((r) => r.data);
}

// --- Capacidad semanal (/users/me/) ---

export interface UserMe extends User {
  weekly_capacity_hours?: number;
}

export const meApi = {
  get: () => api.get<UserMe>("/users/me/").then((r) => r.data),
  update: (p: Partial<Pick<UserMe, "weekly_capacity_hours">>) =>
    api.patch<UserMe>("/users/me/", p).then((r) => r.data),
};

/**
 * Capacidad semanal del usuario actual (horas disponibles por semana).
 * Devuelve el valor + una mutación `save` que hace PATCH /users/me/ e
 * invalida la query ["me"].
 */
export function useWeeklyCapacity() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["me"], queryFn: meApi.get });
  const save = useMutation({
    mutationFn: (weekly_capacity_hours: number) =>
      meApi.update({ weekly_capacity_hours }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
  return {
    /** undefined mientras carga o si el backend no devuelve el campo. */
    capacity: query.data?.weekly_capacity_hours,
    isLoading: query.isLoading,
    save,
  };
}

// --- Vinculación KeyResult ↔ tareas ---

/** Resumen de tarea vinculada (linked_tasks_detail del serializer). */
export interface LinkedTaskRef {
  id: number;
  title: string;
  state: TaskState;
}

/**
 * Sustituye la lista de tareas vinculadas a un KeyResult.
 * Mismo endpoint que okrsApi.updateKeyResult; se mantiene aquí para no
 * tocar resources.ts. El serializer devuelve linked_tasks_detail y
 * linked_progress (0-100) recalculado.
 */
export function setKeyResultLinkedTasks(keyResultId: number, taskIds: number[]) {
  return api
    .patch(`/key-results/${keyResultId}/`, { linked_tasks: taskIds })
    .then((r) => r.data);
}
