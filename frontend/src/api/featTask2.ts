// API helpers para la segunda tanda de features de tareas:
// duplicar tarea, posponer recordatorio (snooze) y métricas de
// productividad (racha, completadas por día).
import { api } from "./client";
import type { Task } from "../types";

/** Respuesta de POST /tasks/{id}/snooze_reminder/. */
export interface SnoozeReminderResponse {
  reminder_at: string;
}

/** Un punto del histograma diario de productividad. */
export interface ProductivityDay {
  /** "YYYY-MM-DD" */
  date: string;
  count: number;
}

/** Respuesta de GET /tasks/productivity/?days=N. */
export interface ProductivityStats {
  daily: ProductivityDay[];
  streak: number;
  total: number;
  avg_per_day: number;
  /** "YYYY-MM-DD" o null si no hubo completadas en el período. */
  best_day: string | null;
}

export const taskX2Api = {
  /** Clona campos/tags/assignees/subtareas; devuelve la tarea nueva (201). */
  duplicate: (id: number) =>
    api.post<Task>(`/tasks/${id}/duplicate/`).then((r) => r.data),

  /**
   * Pospone el recordatorio de la tarea `minutes` minutos desde ahora.
   * Devuelve el nuevo reminder_at (ISO).
   */
  snoozeReminder: (id: number, minutes: number) =>
    api
      .post<SnoozeReminderResponse>(`/tasks/${id}/snooze_reminder/`, { minutes })
      .then((r) => r.data),

  /** Métricas de productividad de los últimos `days` días. */
  productivity: (days = 30) =>
    api
      .get<ProductivityStats>(`/tasks/productivity/`, { params: { days } })
      .then((r) => r.data),
};

/**
 * Minutos hasta la próxima hora 09:00 local (hoy si aún no pasó,
 * mañana en caso contrario). Para la opción "mañana 9:00" del snooze.
 */
export function minutesUntilNextNineAM(now = new Date()): number {
  const target = new Date(now);
  target.setHours(9, 0, 0, 0);
  if (target.getTime() <= now.getTime()) {
    target.setDate(target.getDate() + 1);
  }
  return Math.max(1, Math.round((target.getTime() - now.getTime()) / 60000));
}
