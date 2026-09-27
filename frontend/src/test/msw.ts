// Servidor MSW para tests a nivel HTTP: intercepta las llamadas axios
// reales y permite validar el pipeline completo (axios → zod → tipos).
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("*/api/tasks/global-search/", ({ request }) => {
    const q = new URL(request.url).searchParams.get("q") || "";
    return HttpResponse.json({
      tasks: [
        {
          type: "task",
          id: 1,
          title: `Resultado ${q}`,
          state: "open",
          project: { id: 1, name: "P" },
        },
      ],
      comments: [],
      wiki: [],
      projects: [],
    });
  }),
];

export const server = setupServer(...handlers);
