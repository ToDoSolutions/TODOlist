import * as Sentry from "@sentry/react";
import { onCLS, onFCP, onINP, onLCP, onTTFB } from "web-vitals";
import { env } from "./env";

export const monitoringEnabled = !!env.VITE_SENTRY_DSN;

export function initMonitoring() {
  if (!monitoringEnabled) return;

  Sentry.init({
    dsn: env.VITE_SENTRY_DSN,
    environment: env.MODE,
    // Sanitizar: el cliente nunca debe mandar tokens ni cookies.
    beforeSend(event) {
      delete event.request?.cookies;
      if (event.request?.headers) {
        for (const k of Object.keys(event.request.headers)) {
          if (/auth|token|cookie|csrf/i.test(k)) {
            delete event.request.headers[k];
          }
        }
      }
      return event;
    },
  });

  // Web Vitals → Sentry metrics (si la versión lo soporta) o consola en dev.
  const report = (metric: { name: string; value: number }) => {
    if (env.DEV) console.debug(`[vitals] ${metric.name}: ${metric.value}`);
    try {
      const m = (
        Sentry as unknown as {
          metrics?: { distribution?: (n: string, v: number, o?: object) => void };
        }
      ).metrics;
      m?.distribution?.(metric.name, metric.value, { unit: "millisecond" });
    } catch {
      /* noop */
    }
  };
  onCLS(report);
  onFCP(report);
  onINP(report);
  onLCP(report);
  onTTFB(report);
}

export function captureError(error: unknown, context?: Record<string, unknown>) {
  if (!monitoringEnabled) return;
  Sentry.withScope((scope) => {
    if (context) scope.setExtras(context);
    Sentry.captureException(error);
  });
}
