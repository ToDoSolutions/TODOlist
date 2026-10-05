/**
 * Cola de escrituras offline: cuando una mutación falla por error de
 * red (sin respuesta HTTP) la guardamos y la reintentamos al volver la
 * conectividad. Persistida en localStorage para sobrevivir recargas.
 *
 * No es CRDT: el replay es best-effort last-write-wins por REST (igual
 * que si el usuario repitiera la acción). Los conflictos detectables
 * vía /sync/push/ quedan para clientes dedicados; aquí el objetivo es
 * que un click offline no se pierda en silencio.
 */
import type { AxiosError } from "axios";
import { api } from "../api/client";

export interface QueuedOp {
  id: string;
  method: string;
  url: string;
  data?: unknown;
  params?: Record<string, unknown>;
  queuedAt: string;
}

const KEY = "todolist.offlineQueue";
const listeners = new Set<() => void>();

function load(): QueuedOp[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as QueuedOp[]) : [];
  } catch {
    return [];
  }
}

function persist(ops: QueuedOp[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(ops));
  } catch {
    // localStorage lleno/no disponible: la cola queda en memoria
  }
  listeners.forEach((fn) => fn());
}

export const offlineQueue = {
  list: (): QueuedOp[] => load(),
  size: (): number => load().length,

  subscribe(fn: () => void): () => void {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },

  /** Encola una petición mutante que falló por falta de red. */
  enqueue(config: {
    method?: string;
    url?: string;
    data?: unknown;
    params?: Record<string, unknown>;
  }): QueuedOp {
    const op: QueuedOp = {
      id: `q-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      method: (config.method || "post").toUpperCase(),
      url: config.url || "",
      data: typeof config.data === "string" ? safeParse(config.data) : config.data,
      params: config.params,
      queuedAt: new Date().toISOString(),
    };
    persist([...load(), op]);
    return op;
  },

  drop(id: string) {
    persist(load().filter((o) => o.id !== id));
  },

  clear() {
    persist([]);
  },

  /**
   * Reintenta la cola en orden; cada op se reenvía tal cual por REST.
   * Las que vuelven a fallar por red permanecen; las rechazadas por el
   * servidor (4xx) se descartan (ya no se pueden aplicar).
   * Devuelve { sent, failed } — 'sent' incluye descartadas por 4xx.
   */
  async flush(): Promise<{ sent: number; failed: number }> {
    let sent = 0;
    let failed = 0;
    for (const op of load()) {
      try {
        await api({
          method: op.method.toLowerCase(),
          url: op.url,
          data: op.data,
          params: op.params,
          _offline_replay: true, // evita re-encolar en el interceptor
        } as never);
        this.drop(op.id);
        sent += 1;
      } catch (e) {
        const axErr = e as AxiosError;
        if (axErr.response && axErr.response.status >= 400) {
          // El servidor la rechazó (validación/permiso) — no reintentar
          this.drop(op.id);
          sent += 1;
        } else {
          failed += 1; // sigue offline
          break;
        }
      }
    }
    return { sent, failed };
  },
};

function safeParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

/** ¿Debe esta request ir a la cola offline? */
export function isQueueable(config: {
  method?: string;
  url?: string;
  _offline_replay?: boolean;
}): boolean {
  if (config._offline_replay) return false;
  const method = (config.method || "get").toLowerCase();
  if (["get", "head", "options", "trace"].includes(method)) return false;
  const url = config.url || "";
  // Auth/refresh no se encola (los tokens pueden haber rotado);
  // /sync/push ya es la vía de clientes dedicados.
  return !/auth|\/sync\/push/i.test(url);
}
