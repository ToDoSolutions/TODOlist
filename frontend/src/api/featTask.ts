// API helpers para las features "task extras" (recordatorio, asignados
// múltiples, watchers, temporizador, quick-add, undo-delete).
// Los campos nuevos del backend (reminder_at, assignees, assignees_detail,
// watchers, is_watching) aún no están en `Task` de ../types, así que se
// modelan aquí como extensión para no tocar ficheros compartidos.
import { api } from "./client";
import { tasksApi, tagsApi } from "./resources";
import type { Task, TaskInput, Tag, ProjectMember } from "../types";
import type { QuickAddResult } from "../lib/quickAdd";
import { createElement } from "react";
import { Button } from "@mui/material";
import { useSnackbar } from "notistack";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { notify } from "../notify";

export interface AssigneeDetail {
  id: number;
  email: string;
  username: string;
}

/** Campos del contrato nuevo que el backend expone en Task. */
export interface TaskExtras {
  reminder_at?: string | null;
  assignees?: number[];
  assignees_detail?: AssigneeDetail[];
  watchers?: number[];
  is_watching?: boolean;
}

export type TaskX = Task & TaskExtras;

/** Patch aceptado por PATCH /tasks/{id}/ incluyendo los campos nuevos. */
export interface TaskXPatch extends Partial<TaskInput> {
  reminder_at?: string | null;
  assignees?: number[];
}

export interface TimerStatus {
  running: boolean;
  started_at: string | null;
}

export const taskXApi = {
  /** PATCH genérico que admite reminder_at/assignees (pendientes en TaskInput). */
  update: (id: number, patch: TaskXPatch) =>
    api.patch<TaskX>(`/tasks/${id}/`, patch).then((r) => r.data),

  // Watchers: POST para ambos (el contrato acepta también DELETE en unwatch).
  watch: (id: number) => api.post(`/tasks/${id}/watch/`).then((r) => r.data),
  unwatch: (id: number) => api.post(`/tasks/${id}/unwatch/`).then((r) => r.data),

  // Temporizador por tarea.
  timerStart: (id: number) => api.post(`/tasks/${id}/timer_start/`).then((r) => r.data),
  timerStop: (id: number) => api.post(`/tasks/${id}/timer_stop/`).then((r) => r.data),
  timerStatus: (id: number) =>
    api.get<TimerStatus>(`/tasks/${id}/timer_status/`).then((r) => r.data),

  /**
   * Usuarios asignables = miembros del proyecto de la tarea
   * (GET /project-members/?project=N). Sin proyecto no hay directorio de
   * usuarios expuesto: el caller fusiona assignees_detail como fallback.
   */
  assignableUsers: (projectId: number) =>
    api
      .get<ProjectMember[] | { results?: ProjectMember[] }>(`/project-members/`, {
        params: { project: projectId },
      })
      .then((r) => {
        const data = r.data;
        const members = Array.isArray(data) ? data : data?.results || [];
        return members
          .filter((m) => typeof m.user === "number")
          .map<AssigneeDetail>((m) => ({
            id: m.user,
            email: m.user_email || m.email || `#${m.user}`,
            username: m.user_display || m.user_email || `#${m.user}`,
          }));
      }),
};

/**
 * Crea una tarea a partir del resultado de parseQuickAdd.
 * Resuelve los nombres de etiqueta a ids (crea las que no existan).
 */
export async function createFromQuickAdd(
  parsed: QuickAddResult,
  existingTags: Tag[],
): Promise<Task> {
  const byName = new Map(existingTags.map((tg) => [tg.name.toLowerCase(), tg.id]));
  const tagIds: number[] = [];
  for (const name of parsed.tags || []) {
    const found = byName.get(name.toLowerCase());
    if (found !== undefined) {
      tagIds.push(found);
    } else {
      const created = await tagsCreate(name);
      tagIds.push(created.id);
    }
  }
  const payload: TaskXPatch = {
    title: parsed.title,
    due_date: parsed.due_date ?? null,
    priority:
      parsed.priority !== undefined
        ? (parsed.priority as TaskInput["priority"])
        : undefined,
    project: parsed.project_id ?? undefined,
    tags: tagIds.length ? tagIds : undefined,
  };
  return tasksApi.create(payload as TaskInput);
}

const tagsCreate = (name: string) => tagsApi.create({ name });

/** Snapshot de una tarea para "deshacer borrado" (recrea con nuevo id). */
export function snapshotTask(t: TaskX): TaskXPatch {
  return {
    title: t.title,
    description: t.description,
    state: t.state,
    priority: t.priority,
    due_date: t.due_date,
    project: t.project,
    tags: t.tags ?? t.tags_ids ?? [],
    sprint: t.sprint,
    epic: t.epic,
    assignees: t.assignees ?? [],
  };
}

/** Recrea la tarea eliminada a partir de su snapshot. */
export function restoreTask(snapshot: TaskXPatch) {
  return tasksApi.create(snapshot as TaskInput);
}

/**
 * Snackbar "Tarea eliminada — Deshacer" (5 s). Llamar en el onSuccess del
 * delete: guarda un snapshot completo y el botón lo recrea con nuevo id.
 * Devuelve la función `notifyDeleted(task)`.
 */
export function useUndoDelete() {
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();
  const { t } = useTranslation();
  const qc = useQueryClient();

  const restoreMut = useMutation({
    mutationFn: restoreTask,
    onSuccess: () => {
      notify.success(t("p.taskx.undo.restored"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: () => notify.error(t("p.taskx.undo.restoreError")),
  });

  return (task: TaskX) => {
    const snapshot = snapshotTask(task);
    enqueueSnackbar(t("p.taskx.undo.deleted"), {
      variant: "info",
      autoHideDuration: 5000,
      action: (key) =>
        createElement(
          Button,
          {
            color: "inherit",
            size: "small",
            onClick: () => {
              closeSnackbar(key);
              restoreMut.mutate(snapshot);
            },
          },
          t("p.taskx.undo.undo"),
        ),
    });
  };
}
