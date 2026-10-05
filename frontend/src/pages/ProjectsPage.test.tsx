import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import ProjectsPage from "./ProjectsPage";
import type { Project } from "../types";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("../api/resources", () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));
vi.mock("../notify", () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { projectsApi } from "../api/resources";
import { notify } from "../notify";

const listMock = projectsApi.list as ReturnType<typeof vi.fn>;
const createMock = projectsApi.create as ReturnType<typeof vi.fn>;
const updateMock = projectsApi.update as ReturnType<typeof vi.fn>;
const removeMock = projectsApi.remove as ReturnType<typeof vi.fn>;

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 1,
    name: "Proyecto A",
    description: "Desc",
    color: "#ff0000",
    is_archived: false,
    tasks_count: 3,
    sprints_count: 1,
    epics_count: 2,
    created_at: "2024-01-01",
    updated_at: "2024-01-01",
    ...overrides,
  } as Project;
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    createElement(
      MemoryRouter,
      null,
      createElement(QueryClientProvider, { client: qc }, createElement(ProjectsPage)),
    ),
  );
}

describe("ProjectsPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("muestra estado de carga", () => {
    listMock.mockReturnValue(new Promise(() => {}));
    const { container } = renderPage();
    expect(container.querySelector(".MuiSkeleton-root")).toBeTruthy();
  });

  it("muestra error al cargar", async () => {
    listMock.mockRejectedValue(new Error("boom"));
    renderPage();
    await waitFor(() => expect(screen.getByText(/error al cargar/i)).toBeTruthy());
  });

  it("muestra empty state sin proyectos", async () => {
    listMock.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(/sin proyectos/i)).toBeTruthy());
  });

  it("lista proyectos con counts", async () => {
    listMock.mockResolvedValue([makeProject()]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Proyecto A")).toBeTruthy());
    expect(screen.getByText("3 tareas")).toBeTruthy();
    expect(screen.getByText("1 sprint")).toBeTruthy();
    expect(screen.getByText("2 épicas")).toBeTruthy();
  });

  it("click en proyecto navega al detalle", async () => {
    listMock.mockResolvedValue([makeProject({ id: 42 })]);
    renderPage();
    await waitFor(() => screen.getByText("Proyecto A"));
    fireEvent.click(screen.getByText("Proyecto A"));
    expect(mockNavigate).toHaveBeenCalledWith("/app/project/42");
  });

  it("crear proyecto valida nombre obligatorio", async () => {
    listMock.mockResolvedValue([]);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /nuevo proyecto/i }));
    const crearBtn = screen.getByRole("button", { name: /^crear$/i });
    expect((crearBtn as HTMLButtonElement).disabled).toBe(true);
    expect(createMock).not.toHaveBeenCalled();
  });

  it("crear proyecto llama a la API con el form", async () => {
    createMock.mockResolvedValue({});
    listMock.mockResolvedValue([]);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /nuevo proyecto/i }));
    fireEvent.change(screen.getByLabelText(/nombre/i), {
      target: { value: "Nuevo P" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^crear$/i }));
    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Nuevo P" }),
      ),
    );
    expect(notify.success).toHaveBeenCalled();
  });

  it("error al crear muestra notificación", async () => {
    createMock.mockRejectedValue(new Error("fail"));
    listMock.mockResolvedValue([]);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /nuevo proyecto/i }));
    fireEvent.change(screen.getByLabelText(/nombre/i), {
      target: { value: "X" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^crear$/i }));
    await waitFor(() => expect(notify.error).toHaveBeenCalled());
  });

  it("editar precarga el formulario", async () => {
    updateMock.mockResolvedValue({});
    listMock.mockResolvedValue([
      makeProject({ id: 7, name: "EditMe", description: "d1" }),
    ]);
    renderPage();
    await waitFor(() => screen.getByText("EditMe"));
    fireEvent.click(screen.getByRole("button", { name: /editar/i }));
    const nombreInput = screen.getByLabelText(/nombre/i) as HTMLInputElement;
    expect(nombreInput.value).toBe("EditMe");
    fireEvent.change(nombreInput, { target: { value: "EditMe2" } });
    fireEvent.click(screen.getByRole("button", { name: /guardar/i }));
    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        7,
        expect.objectContaining({ name: "EditMe2" }),
      ),
    );
  });

  it("eliminar pide confirmación y borra", async () => {
    removeMock.mockResolvedValue({});
    listMock.mockResolvedValue([makeProject({ id: 9, name: "Del" })]);
    renderPage();
    await waitFor(() => screen.getByText("Del"));
    fireEvent.click(screen.getByRole("button", { name: /eliminar/i }));
    // Confirmación muestra el nombre del proyecto
    await waitFor(() => screen.getByText(/seguro que deseas eliminar/i));
    fireEvent.click(screen.getByRole("button", { name: /^eliminar$/i }));
    await waitFor(() => expect(removeMock).toHaveBeenCalledWith(9));
  });

  it("cancelar en diálogo de borrado no elimina", async () => {
    listMock.mockResolvedValue([makeProject({ id: 9, name: "Del" })]);
    renderPage();
    await waitFor(() => screen.getByText("Del"));
    fireEvent.click(screen.getByRole("button", { name: /eliminar/i }));
    await waitFor(() => screen.getByText(/seguro que deseas eliminar/i));
    fireEvent.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(removeMock).not.toHaveBeenCalled();
  });
});
