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
    const mockProjects = [{ id: 1, name: "Proyecto A", tasks_count: 0 }];
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
    expect(result[0]!.name).toBe("Proyecto A");
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

describe("slaPoliciesApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("list normaliza paginación a array", async () => {
    (api.get as any).mockResolvedValue({
      data: { count: 1, next: null, previous: null, results: [{ id: 1, name: "SLA" }] },
    });
    const { slaPoliciesApi } = await import("./resources");
    const result = await slaPoliciesApi.list();
    expect(result).toHaveLength(1);
    expect(result[0]!.name).toBe("SLA");
  });

  it("create postea a /sla-policies/", async () => {
    (api.post as any).mockResolvedValue({ data: { id: 1 } });
    const { slaPoliciesApi } = await import("./resources");
    await slaPoliciesApi.create({ name: "X", priority: 1, resolution_hours: 24 });
    expect(api.post).toHaveBeenCalledWith(
      "/sla-policies/",
      expect.objectContaining({ name: "X", priority: 1 }),
    );
  });
});

describe("advancedMetricsApi nuevos endpoints", () => {
  beforeEach(() => vi.clearAllMocks());

  it("roadmap llama a /tasks/roadmap/", async () => {
    (api.get as any).mockResolvedValue({ data: { epics: [], milestones: [] } });
    const { advancedMetricsApi } = await import("./resources");
    await advancedMetricsApi.roadmap();
    expect(api.get).toHaveBeenCalledWith("/tasks/roadmap/");
  });

  it("velocity llama a /tasks/velocity/", async () => {
    (api.get as any).mockResolvedValue({ data: { velocity: [] } });
    const { advancedMetricsApi } = await import("./resources");
    await advancedMetricsApi.velocity();
    expect(api.get).toHaveBeenCalledWith("/tasks/velocity/");
  });

  it("burnup llama a /tasks/burnup/?sprint_id=N", async () => {
    (api.get as any).mockResolvedValue({ data: { series: [] } });
    const { advancedMetricsApi } = await import("./resources");
    await advancedMetricsApi.burnup(42);
    expect(api.get).toHaveBeenCalledWith("/tasks/burnup/?sprint_id=42");
  });
});
