// APIs de la feature "público": enlaces compartidos de proyecto, webhooks
// entrantes y token público de formularios intake. Los endpoints
// autenticados usan el cliente axios (cookies JWT); la lectura pública del
// share usa fetch plano porque el visitante no tiene sesión.
import { api } from "./client";
import { env } from "../env";
import type { Paginated } from "../types";

// --- Enlaces compartidos de proyecto (autenticado) ---

export interface ShareLinkItem {
  id: number;
  token: string;
  project: number;
  created_at: string;
  is_active: boolean;
}

export const shareLinksApi = {
  list: () =>
    api.get<ShareLinkItem[] | Paginated<ShareLinkItem>>("/share-links/").then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d.results;
    }),
  create: (project: number) =>
    api.post<ShareLinkItem>("/share-links/", { project }).then((r) => r.data),
  remove: (id: number) => api.delete(`/share-links/${id}/`),
};

// --- Webhooks entrantes (autenticado) ---

export interface InboundWebhookItem {
  id: number;
  name: string;
  token: string;
  project: number | null;
  is_active: boolean;
  last_used_at: string | null;
}

export const inboundWebhooksApi = {
  list: () =>
    api
      .get<InboundWebhookItem[] | Paginated<InboundWebhookItem>>("/inbound-webhooks/")
      .then((r) => {
        const d = r.data;
        return Array.isArray(d) ? d : d.results;
      }),
  create: (data: { name: string; project?: number | null }) =>
    api.post<InboundWebhookItem>("/inbound-webhooks/", data).then((r) => r.data),
  update: (id: number, data: Partial<InboundWebhookItem>) =>
    api.patch<InboundWebhookItem>(`/inbound-webhooks/${id}/`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/inbound-webhooks/${id}/`),
};

// --- Token público de formularios intake (autenticado) ---

export const intakePublicApi = {
  rotateToken: (id: number) =>
    api
      .post<{ public_token: string }>(`/intake-forms/${id}/rotate_public_token/`)
      .then((r) => r.data),
};

// --- Vista pública de un proyecto compartido (SIN autenticación) ---

export interface SharedTaskItem {
  id: number;
  title: string;
  state: string;
  priority: number;
  due_date: string | null;
  assignee_name: string | null;
}

export interface PublicShareData {
  project: { id: number; name: string; description: string };
  tasks: SharedTaskItem[];
}

export class PublicShareError extends Error {
  status: number;
  constructor(status: number) {
    super(`public_share_${status}`);
    this.status = status;
  }
}

/** GET público: no usa el cliente axios para no enviar cookies/CSRF y
 *  evitar el interceptor de refresh/redirect a /app/403. */
export async function fetchPublicShare(token: string): Promise<PublicShareData> {
  const res = await fetch(
    `${env.VITE_API_URL}/public/share/${encodeURIComponent(token)}/`,
  );
  if (!res.ok) throw new PublicShareError(res.status);
  return (await res.json()) as PublicShareData;
}
