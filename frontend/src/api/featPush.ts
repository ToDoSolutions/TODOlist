// API de Web Push: clave pública VAPID y registro de suscripciones.
// Backend: GET /api/push/vapid-key/ → {publicKey} (404 si no configurada);
// POST /api/push/subscriptions/ {endpoint, keys:{p256dh,auth}};
// DELETE /api/push/subscriptions/ {endpoint}; GET /api/push/subscriptions/ (lista).
import { api } from "./client";

export interface VapidKeyResponse {
  publicKey: string;
}

export interface PushSubscriptionKeys {
  p256dh: string;
  auth: string;
}

export interface PushSubscriptionRecord {
  id?: number;
  endpoint: string;
  keys?: PushSubscriptionKeys;
  created_at?: string;
}

interface PaginatedLike<T> {
  results: T[];
}

export const pushApi = {
  vapidKey: () => api.get<VapidKeyResponse>("/push/vapid-key/").then((r) => r.data),
  listSubscriptions: () =>
    api
      .get<PushSubscriptionRecord[] | PaginatedLike<PushSubscriptionRecord>>(
        "/push/subscriptions/",
      )
      .then((r) => {
        const d = r.data;
        return Array.isArray(d) ? d : d.results;
      }),
  createSubscription: (endpoint: string, keys: PushSubscriptionKeys) =>
    api
      .post<PushSubscriptionRecord>("/push/subscriptions/", { endpoint, keys })
      .then((r) => r.data),
  // DELETE con body: DRF espera {endpoint} para identificar la suscripción.
  deleteSubscription: (endpoint: string) =>
    api.delete("/push/subscriptions/", { data: { endpoint } }).then((r) => r.data),
};
