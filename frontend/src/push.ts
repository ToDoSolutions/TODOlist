// Web Push: helpers de suscripción del navegador.
// Usa un service worker dedicado (public/push-sw.js) registrado aparte del
// SW de precache de vite-plugin-pwa, para no tocar la estrategia generateSW.
import { pushApi, type PushSubscriptionKeys } from "./api/featPush";

export const PUSH_SW_URL = "/push-sw.js";

export type PushErrorCode =
  "unsupported" | "not-configured" | "permission-denied" | "invalid-subscription";

export class PushError extends Error {
  readonly code: PushErrorCode;

  constructor(code: PushErrorCode, message: string) {
    super(message);
    this.name = "PushError";
    this.code = code;
  }
}

/** Decodifica la clave pública VAPID (base64url) al formato que exige pushManager. */
export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    out[i] = raw.charCodeAt(i);
  }
  return out;
}

/**
 * Push API disponible: ServiceWorker + PushManager + contexto seguro
 * (window.isSecureContext cubre https y localhost/127.0.0.1).
 */
export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    window.isSecureContext &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    typeof Notification !== "undefined"
  );
}

let vapidKeyCache: Promise<string | null> | null = null;

/**
 * Clave pública VAPID del backend, memoizada.
 * Devuelve null cuando el servidor no la tiene configurada (404).
 * Los errores transitorios NO se memoizan, para permitir reintentos.
 */
export function getVapidKey(): Promise<string | null> {
  if (!vapidKeyCache) {
    vapidKeyCache = pushApi
      .vapidKey()
      .then((d) => d.publicKey || null)
      .catch((err: { response?: { status?: number } }) => {
        if (err?.response?.status === 404) return null;
        vapidKeyCache = null;
        throw err;
      });
  }
  return vapidKeyCache;
}

/** Registro existente del SW de push (no lo crea). */
async function findPushRegistration(): Promise<ServiceWorkerRegistration | null> {
  const regs = await navigator.serviceWorker.getRegistrations();
  for (const reg of regs) {
    const sw = reg.active ?? reg.waiting ?? reg.installing;
    if (sw?.scriptURL.endsWith(PUSH_SW_URL)) return reg;
  }
  return null;
}

/** Registro del SW de push, creándolo con scope "/" si no existe. */
async function ensurePushRegistration(): Promise<ServiceWorkerRegistration> {
  const existing = await findPushRegistration();
  if (existing) return existing;
  return navigator.serviceWorker.register(PUSH_SW_URL, { scope: "/" });
}

async function ensureNotificationPermission(): Promise<NotificationPermission> {
  if (Notification.permission !== "default") return Notification.permission;
  return Notification.requestPermission();
}

function subscriptionPayload(sub: PushSubscription): {
  endpoint: string;
  keys: PushSubscriptionKeys;
} {
  const json = sub.toJSON();
  const endpoint = json.endpoint;
  const keys = json.keys;
  if (!endpoint || !keys?.p256dh || !keys?.auth) {
    throw new PushError("invalid-subscription", "Suscripción push incompleta");
  }
  return { endpoint, keys: { p256dh: keys.p256dh, auth: keys.auth } };
}

/**
 * Suscribe el navegador a push y registra el endpoint en el backend.
 * Lanza PushError con code descriptivo para que la UI mapee el mensaje.
 */
export async function subscribePush(): Promise<PushSubscription> {
  if (!isPushSupported()) {
    throw new PushError("unsupported", "Este navegador no soporta push");
  }
  // El permiso se pide lo antes posible: algunos navegadores exigen que la
  // petición ocurra dentro del gesto de usuario que activó el toggle.
  const permission = await ensureNotificationPermission();
  if (permission !== "granted") {
    throw new PushError("permission-denied", "Permiso de notificaciones no concedido");
  }
  const vapidKey = await getVapidKey();
  if (!vapidKey) {
    throw new PushError("not-configured", "El servidor no tiene clave VAPID");
  }
  const reg = await ensurePushRegistration();
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey),
    });
  }
  const payload = subscriptionPayload(sub);
  await pushApi.createSubscription(payload.endpoint, payload.keys);
  return sub;
}

/** Da de baja la suscripción local y la elimina del backend (best-effort). */
export async function unsubscribePush(): Promise<void> {
  if (!isPushSupported()) return;
  const reg = await findPushRegistration();
  const sub = await reg?.pushManager.getSubscription();
  const endpoint = sub?.endpoint;
  if (sub) await sub.unsubscribe();
  if (endpoint) {
    try {
      await pushApi.deleteSubscription(endpoint);
    } catch {
      // El backend puede ya no conocerla (404): el estado local quedó limpio.
    }
  }
}

/**
 * true solo si el navegador está suscrito Y el backend conoce el endpoint.
 * Si el navegador sigue suscrito pero el backend perdió el registro,
 * se re-sincroniza re-publicando la suscripción.
 */
export async function isSubscribed(): Promise<boolean> {
  if (!isPushSupported()) return false;
  try {
    const reg = await findPushRegistration();
    if (!reg) return false;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return false;
    const list = await pushApi.listSubscriptions();
    if (list.some((s) => s.endpoint === sub.endpoint)) return true;
    const payload = subscriptionPayload(sub);
    await pushApi.createSubscription(payload.endpoint, payload.keys);
    return true;
  } catch {
    return false;
  }
}
