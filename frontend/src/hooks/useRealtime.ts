import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { env } from "../env";

/**
 * Conecta a los WebSockets del backend y invalida los caches de
 * TanStack Query cuando llegan eventos en tiempo real.
 *
 * Endpoints: /ws/tasks/ y /ws/notifications/.
 * Autenticación: cookie httpOnly (el navegador la envía en el handshake;
 * el token nunca es legible por JavaScript).
 * Reconecta con backoff exponencial hasta 30s.
 */
export function useRealtime(enabled: boolean) {
  const qc = useQueryClient();
  const socketsRef = useRef<WebSocket[]>([]);

  useEffect(() => {
    if (!enabled) return;

    const wsBase =
      env.VITE_API_URL.replace(/^http/, "ws").replace(/\/api\/?$/, "") + "/ws";

    let closed = false;
    let retryDelay = 1000;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      if (closed) return;
      const sockets: WebSocket[] = [];
      for (const path of ["tasks", "notifications"]) {
        const ws = new WebSocket(`${wsBase}/${path}/`);
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data);
            if (typeof msg?.type !== "string") return;
            if (msg.type.startsWith("task.")) {
              qc.invalidateQueries({ queryKey: ["tasks"] });
            } else if (msg.type.startsWith("notification")) {
              qc.invalidateQueries({ queryKey: ["notifications"] });
              qc.invalidateQueries({ queryKey: ["notifications-unread"] });
            }
          } catch {
            // mensaje no JSON: ignorar
          }
        };
        ws.onclose = () => {
          if (closed) return;
          retryDelay = Math.min(retryDelay * 2, 30000);
          timer = setTimeout(connect, retryDelay);
        };
        ws.onopen = () => {
          retryDelay = 1000;
        };
        sockets.push(ws);
      }
      socketsRef.current = sockets;
    };

    connect();

    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      socketsRef.current.forEach((ws) => ws.close());
      socketsRef.current = [];
    };
  }, [enabled, qc]);
}
