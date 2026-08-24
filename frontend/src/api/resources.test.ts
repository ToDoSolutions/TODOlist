import { describe, it, expect, vi, beforeEach } from "vitest";
import { projectsApi, tagsApi, tasksApi } from "./resources";

// Mock axios client
vi.mock("./client", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  tokenStorage: {
    getAccess: () => null,
    getRefresh: () => null,
    set: () => {},
    clear: () => {},
  },
}));

import { api } from "./client";

describe("projectsApi.list - manejo de paginación", () => {
  beforeEach(() => vi.clearAllMocks());

  it("devuelve array cuando la API responde con array plano", async () => {
    const mockProjects = [
      { id: 1, name: "Proyecto A", tasks_count: 0 },
    ];
    (api.get as any).mockResolvedValue({ data: mockProjects });

    const result = await projectsApi.list();
    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual(mockProjects);
    expect(result.map).toBeDefined();
  });

  it("devuelve array cuando la API responde con objeto paginado", async () => {
    const mockResponse = {
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 1, name: "Proyecto A", tasks_count: 3 },
        { id: 2, name: "Proyecto B", tasks_count: 0 },
      ],
    };
    (api.get as any).mockResolvedValue({ data: mockResponse });

    const result = await projectsApi.list();
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(2);
    expect(result.map).toBeDefined();
    expect(result[0].name).toBe("Proyecto A");
  });

  it("no crashea con respuesta vacía paginada", async () => {
    (api.get as any).mockResolvedValue({
      data: { count: 0, next: null, previous: null, results: [] },
    });

    const result = await projectsApi.list();
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(0);
  });
});

describe("tagsApi.list - manejo de paginación", () => {
  beforeEach(() => vi.clearAllMocks());

  it("devuelve array cuando la API responde con objeto paginado", async () => {
    (api.get as any).mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: [{ id: 1, name: "Trabajo", color: "#1976d2" }],
      },
    });

    const result = await tagsApi.list();
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expect(result.map).toBeDefined();
  });

  it("devuelve array cuando la API responde con array plano", async () => {
    (api.get as any).mockResolvedValue({
      data: [{ id: 1, name: "Trabajo", color: "#1976d2" }],
    });

    const result = await tagsApi.list();
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
  });
});

describe("tasksApi.list - manejo de paginación", () => {
  beforeEach(() => vi.clearAllMocks());

  it("devuelve array cuando la API responde con objeto paginado", async () => {
    (api.get as any).mockResolvedValue({
      data: {
        count: 2,
        next: null,
        previous: null,
        results: [
          { id: 1, title: "Tarea 1", state: "pending", priority: 3 },
          { id: 2, title: "Tarea 2", state: "completed", priority: 1 },
        ],
      },
    });

    const result = await tasksApi.list({});
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(2);
    expect(result.map).toBeDefined();
  });

  it("devuelve array cuando la API responde con array plano", async () => {
    (api.get as any).mockResolvedValue({
      data: [{ id: 1, title: "Tarea 1", state: "pending", priority: 3 }],
    });

    const result = await tasksApi.list({});
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
  });
});
