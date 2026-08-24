import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Middleware SPA: reescribe rutas del cliente (que no son assets)
// a /index.html ANTES del middleware de ficheros estáticos.
// Necesario porque el WORKDIR del contenedor es /app y choca con la ruta /app.
function spaFallback(): Plugin {
  return {
    name: "spa-fallback",
    configureServer(server) {
      server.middlewares.use((req: any, _res: any, next: any) => {
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
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), spaFallback()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
  },
  test: {
    globals: true,
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
} as any);
