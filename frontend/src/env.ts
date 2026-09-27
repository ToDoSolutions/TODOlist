import { z } from "zod";

// Validación de variables de entorno al arrancar: falla rápido con un
// mensaje claro en vez de comportamientos raros en runtime.
const envSchema = z.object({
  VITE_API_URL: z.string().url().default("http://127.0.0.1:8000/api"),
  VITE_SENTRY_DSN: z.string().optional(),
  MODE: z.string().default("production"),
  DEV: z.boolean().default(false),
  PROD: z.boolean().default(true),
});

const parsed = envSchema.safeParse(import.meta.env);

if (!parsed.success) {
  // En desarrollo, falla fuerte para detectar la mala config al instante.
  // En producción, avisa pero no rompe la app.
  const msg = `Config de entorno inválida: ${parsed.error.issues
    .map((i) => `${i.path.join(".")}: ${i.message}`)
    .join(", ")}`;
  if (import.meta.env.DEV) throw new Error(msg);
  console.error(msg);
}

export const env = parsed.success
  ? parsed.data
  : envSchema.parse({
      VITE_API_URL: "http://127.0.0.1:8000/api",
      MODE: "production",
      DEV: false,
      PROD: true,
    });
