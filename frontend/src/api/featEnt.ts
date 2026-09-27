// APIs de features "enterprise":
// - SSO corporativo: GET /sso/providers/ (público, AllowAny) alimenta los
//   botones SSO de LoginPage y el estado OIDC del catálogo de integraciones.
// - Videollamadas en reuniones: POST /meetings/{id}/video/ (idempotente,
//   devuelve la sala existente) y POST /meetings/{id}/close_video/ (la cierra).
import { api } from "./client";
import type { MeetingItem } from "./resources";

// --- SSO enterprise ---

export interface SsoProvider {
  id: "github" | "google" | "oidc" | (string & {});
  name: string;
  login_url: string;
  enabled: boolean;
}

export const ssoApi = {
  /**
   * Lista los providers SSO configurados en el servidor. Endpoint público:
   * se llama desde LoginPage sin sesión; un fallo (404/5xx) es no fatal y
   * los callers deben degradar a "sin SSO".
   */
  providers: () =>
    api
      .get<{ providers: SsoProvider[] }>("/sso/providers/")
      .then((r) => r.data.providers),
};

// --- Videollamada en reuniones ---

/**
 * Campos extra que MeetingSerializer expone además de MeetingItem
 * (video_url: string|null, video_room: string). Opcionales para tolerar
 * backends que aún no los serializan.
 */
export interface MeetingVideoFields {
  video_url?: string | null;
  video_room?: string;
}

export type MeetingWithVideo = MeetingItem & MeetingVideoFields;

export interface MeetingVideoRoom {
  room: string;
  url: string;
}

export const meetingsVideoApi = {
  /** Idempotente: si la reunión ya tiene sala devuelve la misma {room, url}. */
  start: (id: number) =>
    api.post<MeetingVideoRoom>(`/meetings/${id}/video/`).then((r) => r.data),
  /** Cierra la sala y limpia video_url/video_room en la reunión. */
  close: (id: number) => api.post(`/meetings/${id}/close_video/`).then((r) => r.data),
};
