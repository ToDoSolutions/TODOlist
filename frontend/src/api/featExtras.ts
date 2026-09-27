/**
 * APIs de extras en desarrollo paralelo (contrato backend acordado):
 * - /api/external-calendars/ : suscripciones iCal externas + refresh + events
 * - /api/whiteboards/        : pizarras por proyecto (content JSON libre)
 *
 * Vive fuera de resources.ts para no bloquear el merge con otros frentes.
 */
import { api } from "./client";
import type { Paginated } from "../types";

export interface ExternalCalendar {
  id: number;
  name: string;
  url: string;
  color: string;
  is_active: boolean;
  last_synced_at: string | null;
  last_error: string | null;
}

export interface ExternalCalendarEvent {
  id: number;
  uid: string;
  summary: string;
  dtstart: string;
  dtend: string;
  all_day: boolean;
}

/** Evento enriquecido con los metadatos de su calendario (para la vista). */
export interface OverlayEvent extends ExternalCalendarEvent {
  color: string;
  calendar: string;
}

export interface WhiteboardNode {
  id: string;
  x: number;
  y: number;
  text: string;
  color: string;
  w: number;
  h: number;
}

export interface WhiteboardEdge {
  from: string;
  to: string;
}

export interface WhiteboardContent {
  nodes: WhiteboardNode[];
  edges: WhiteboardEdge[];
}

export interface Whiteboard {
  id: number;
  project: number;
  name: string;
  content: WhiteboardContent;
  updated_at: string;
}

function unwrap<T>(d: T[] | Paginated<T>): T[] {
  return Array.isArray(d) ? d : d.results;
}

export const externalCalendarsApi = {
  list: () =>
    api
      .get<ExternalCalendar[] | Paginated<ExternalCalendar>>("/external-calendars/")
      .then((r) => unwrap(r.data)),
  create: (p: Partial<ExternalCalendar>) =>
    api.post<ExternalCalendar>("/external-calendars/", p).then((r) => r.data),
  update: (id: number, p: Partial<ExternalCalendar>) =>
    api.patch<ExternalCalendar>(`/external-calendars/${id}/`, p).then((r) => r.data),
  remove: (id: number) => api.delete(`/external-calendars/${id}/`),
  refresh: (id: number) =>
    api.post<ExternalCalendar>(`/external-calendars/${id}/refresh/`).then((r) => r.data),
  events: (id: number, start: string, end: string) =>
    api
      .get<ExternalCalendarEvent[]>(`/external-calendars/${id}/events/`, {
        params: { start, end },
      })
      .then((r) => (Array.isArray(r.data) ? r.data : [])),
};

/**
 * Todos los eventos de los calendarios activos del usuario en un rango.
 * Un calendario que falla no tira el overlay entero: devuelve [] para ese feed.
 */
export async function fetchOverlayEvents(
  start: Date,
  end: Date,
): Promise<OverlayEvent[]> {
  let calendars: ExternalCalendar[];
  try {
    calendars = await externalCalendarsApi.list();
  } catch {
    // Overlay opcional: si el endpoint falla, la vista de calendario
    // de tareas no debe degradarse (ni mostrar snackbar global).
    return [];
  }
  const active = calendars.filter((c) => c.is_active);
  const s = start.toISOString();
  const e = end.toISOString();
  const perCalendar = await Promise.all(
    active.map(async (cal): Promise<OverlayEvent[]> => {
      try {
        const events = await externalCalendarsApi.events(cal.id, s, e);
        return events.map((ev) => ({
          ...ev,
          color: cal.color || "#607d8b",
          calendar: cal.name,
        }));
      } catch {
        return [];
      }
    }),
  );
  return perCalendar.flat();
}

export const whiteboardsApi = {
  list: () =>
    api
      .get<Whiteboard[] | Paginated<Whiteboard>>("/whiteboards/")
      .then((r) => unwrap(r.data)),
  get: (id: number) => api.get<Whiteboard>(`/whiteboards/${id}/`).then((r) => r.data),
  create: (p: { project: number; name: string }) =>
    api.post<Whiteboard>("/whiteboards/", p).then((r) => r.data),
  update: (id: number, p: Partial<Pick<Whiteboard, "name" | "content">>) =>
    api.patch<Whiteboard>(`/whiteboards/${id}/`, p).then((r) => r.data),
  remove: (id: number) => api.delete(`/whiteboards/${id}/`),
};
