import { fileURLToPath } from "node:url";
// vitest/config extiende defineConfig con el bloque `test` (tipado, sin `as any`)
import { defineConfig } from "vitest/config";
import { Plugin, type Connect } from "vite";
import type { ServerResponse } from "node:http";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Middleware SPA: reescribe rutas del cliente (que no son assets)
// a /index.html ANTES del middleware de ficheros estáticos.
// Necesario porque el WORKDIR del contenedor es /app y choca con la ruta /app.
function spaFallback(): Plugin {
  return {
    name: "spa-fallback",
    configureServer(server) {
      server.middlewares.use(
        (
          req: Connect.IncomingMessage,
          _res: ServerResponse,
          next: Connect.NextFunction,
        ) => {
          const url = (req.url || "").split("?")[0];
          if (
            url &&
            !url.startsWith("/@") &&
            !url.startsWith("/src") &&
            !url.startsWith("/node_modules") &&
            !url.startsWith("/public") &&
            !url.includes(".") &&
            url !== "/"
          ) {
            req.url = "/index.html";
          }
          next();
        },
      );
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    spaFallback(),
    VitePWA({
      registerType: "prompt",
      includeAssets: ["favicon.ico", "robots.txt"],
      manifest: {
        name: "TODOlist",
        short_name: "TODOlist",
        description: "Gestión de tareas, proyectos, sprints y integración con GitHub",
        theme_color: "#1976d2",
        background_color: "#ffffff",
        display: "standalone",
        orientation: "portrait",
        scope: "/",
        start_url: "/",
        icons: [
          {
            src: "pwa-192x192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        // push-sw.js es un SW independiente (Web Push) registrado aparte;
        // no debe quedar dentro del precache del SW principal.
        globIgnores: ["**/node_modules/**/*", "**/push-sw.js"],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "google-fonts-cache",
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
            },
          },
          {
            urlPattern: /\/api\/.*/i,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              networkTimeoutSeconds: 10,
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24,
              },
            },
          },
        ],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    alias: {
      "virtual:pwa-register/react": fileURLToPath(
        new URL("./src/test/pwa-register-react-stub.ts", import.meta.url),
      ),
    },
    // Máquina dev lenta + jsdom pesado: evitar timeouts falsos en findBy/waitFor
    testTimeout: 15000,
    hookTimeout: 15000,
    // Limitar paralelismo: 22 ficheros de test a la vez saturan la CPU
    pool: "forks",
    maxWorkers: 4,
  },
});
