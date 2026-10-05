import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfirmProvider } from "../components/ConfirmDialog";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import SprintsPage from "./SprintsPage";
import type { Sprint } from "../api/resources";

vi.mock("../auth/ProjectContext", () => ({
  useProject: () => ({ project: { id: 1, name: "P1" }, setProject: vi.fn() }),
}));
vi.mock("../api/resources", () => ({
  sprintsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    close: vi.fn(),
    getTasks: vi.fn().mockResolvedValue([]),
  },
  projectsApi: { list: vi.fn().mockResolvedValue([{ id: 1, name: "P1" }]) },
}));
vi.mock("../notify", () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { sprintsApi } from "../api/resources";
import { notify } from "../notify";

const listMock = sprintsApi.list as ReturnType<typeof vi.fn>;
const updateMock = sprintsApi.update as ReturnType<typeof vi.fn>;
const removeMock = sprintsApi.remove as ReturnType<typeof vi.fn>;

function makeSprint(overrides: Partial<Sprint> = {}): Sprint {
  return {
    id: 1,
    name: "Sprint 1",
    goal: "Objetivo",
    state: "planned",
    start_date: "2024-01-01",
    end_date: "2024-01-14",
    project: 1,
    task_count: 3,
    created_at: "2024-01-01",
    updated_at: "2024-01-01",
    ...overrides,
  } as Sprint;
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    createElement(
      MemoryRouter,
      null,
      createElement(
        QueryClientProvider,
        { client: qc },
        createElement(ConfirmProvider, null, createElement(SprintsPage)),
      ),
    ),
  );
}

describe("SprintsPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("empty state sin sprints", async () => {
    listMock.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(/sin sprints/i)).toBeTruthy());
  });

  it("renderiza sprint con chips de estado, fechas y tareas", async () => {
    listMock.mockResolvedValue([makeSprint()]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Sprint 1")).toBeTruthy());
    expect(screen.getByText("Planificado")).toBeTruthy();
    expect(screen.getByText("1 ene 2024 → 14 ene 2024")).toBeTruthy();
    expect(screen.getByText("3 tareas")).toBeTruthy();
    expect(screen.getByText("P1")).toBeTruthy();
  });

  it("sprint planned muestra botón Activar que lo activa", async () => {
    updateMock.mockResolvedValue({});
    listMock.mockResolvedValue([makeSprint({ id: 9 })]);
    renderPage();
    await waitFor(() => screen.getByText("Activar"));
    fireEvent.click(screen.getByText("Activar"));
    await waitFor(() => expect(updateMock).toHaveBeenCalledWith(9, { state: "active" }));
    expect(notify.success).toHaveBeenCalledWith("Sprint activado");
  });

  it("sprint active muestra Cerrar en vez de Activar", async () => {
    listMock.mockResolvedValue([makeSprint({ state: "active" })]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Cerrar")).toBeTruthy());
    expect(screen.queryByText("Activar")).toBeNull();
    expect(screen.getByText("Activo")).toBeTruthy();
  });

  it("sprint closed no muestra activar ni cerrar", async () => {
    listMock.mockResolvedValue([makeSprint({ state: "closed" })]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Cerrado")).toBeTruthy());
    expect(screen.queryByText("Activar")).toBeNull();
    expect(screen.queryByRole("button", { name: /^cerrar$/i })).toBeNull();
  });

  it("eliminar llama a remove con el id", async () => {
    removeMock.mockResolvedValue({});
    listMock.mockResolvedValue([makeSprint({ id: 4 })]);
    renderPage();
    await waitFor(() => screen.getByText("Sprint 1"));
    fireEvent.click(screen.getByLabelText("Eliminar"));
    const confirmBtn = await screen.findByRole("button", { name: /eliminar sprint/i });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(removeMock).toHaveBeenCalled());
    expect(removeMock.mock.calls[0]![0]).toBe(4);
  });

  it("ver tareas abre el diálogo de tareas del sprint", async () => {
    listMock.mockResolvedValue([makeSprint({ name: "Sprint X" })]);
    renderPage();
    await waitFor(() => screen.getByText("Sprint X"));
    fireEvent.click(screen.getByRole("button", { name: /ver tareas/i }));
    await waitFor(() => expect(sprintsApi.getTasks).toHaveBeenCalledWith(1));
  });
});
