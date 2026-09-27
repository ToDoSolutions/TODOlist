import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider, createTheme } from "@mui/material";
import { createElement, type ReactNode } from "react";
import TaskTableView from "./TaskTableView";
import type { Task } from "../types";

vi.mock("../api/resources", () => ({
  tasksApi: { update: vi.fn() },
}));
vi.mock("../notify", () => ({ notify: vi.fn() }));

import { tasksApi } from "../api/resources";

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    title: "Tarea",
    description: "",
    state: "pending",
    priority: 3,
    task_type: "task",
    due_date: null,
    start_date: null,
    completed_at: null,
    story_points: null,
    estimate_hours: null,
    size: null,
    project: null,
    sprint: null,
    sprint_name: null,
    epic: null,
    epic_title: null,
    parent: null,
    parent_title: null,
    assignee: null,
    assignee_email: null,
    tags: [],
    tags_ids: [],
    subtasks: [],
    subtask_done: 0,
    subtask_total: 0,
    comments: [],
    relations: [],
    activities: [],
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  } as Task;
}

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return createElement(
    QueryClientProvider,
    { client: qc },
    createElement(ThemeProvider, { theme: createTheme() }, children),
  );
}

describe("TaskTableView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renderiza filas por tarea", () => {
    const tasks = [
      makeTask({ id: 1, title: "Alpha" }),
      makeTask({ id: 2, title: "Beta" }),
    ];
    render(<TaskTableView tasks={tasks} onEdit={vi.fn()} />, { wrapper });
    expect(screen.getByText("Alpha")).toBeTruthy();
    expect(screen.getByText("Beta")).toBeTruthy();
  });

  it("ordena por título al click en cabecera", () => {
    const tasks = [
      makeTask({ id: 1, title: "Zebra" }),
      makeTask({ id: 2, title: "Alpha" }),
      makeTask({ id: 3, title: "Mango" }),
    ];
    render(<TaskTableView tasks={tasks} onEdit={vi.fn()} />, { wrapper });
    fireEvent.click(screen.getByText("Título"));
    const cells = screen.getAllByText(/Zebra|Alpha|Mango/);
    // Tras ordenar asc: Alpha primero
    expect(cells[0]!.textContent).toBe("Alpha");
  });

  it("filtra por texto de búsqueda", () => {
    const tasks = [
      makeTask({ id: 1, title: "Bug crítico" }),
      makeTask({ id: 2, title: "Feature" }),
    ];
    render(<TaskTableView tasks={tasks} onEdit={vi.fn()} />, { wrapper });
    const search = screen.getByPlaceholderText(/buscar/i);
    fireEvent.change(search, { target: { value: "bug" } });
    expect(screen.getByText("Bug crítico")).toBeTruthy();
    expect(screen.queryByText("Feature")).toBeNull();
  });

  it("llama onEdit al click en fila", () => {
    const onEdit = vi.fn();
    render(
      <TaskTableView tasks={[makeTask({ id: 5, title: "Row" })]} onEdit={onEdit} />,
      { wrapper },
    );
    fireEvent.click(screen.getByText("Row"));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 5 }));
  });

  it("edición inline de estado llama a tasksApi.update", async () => {
    (tasksApi.update as ReturnType<typeof vi.fn>).mockResolvedValue({});
    const tasks = [makeTask({ id: 1, title: "T", state: "pending" })];
    render(<TaskTableView tasks={tasks} onEdit={vi.fn()} />, { wrapper });
    // Click en el chip de estado para entrar en modo edición
    fireEvent.click(screen.getByText("Pendiente"));
    const select = await screen.findByRole("combobox");
    fireEvent.mouseDown(select);
    const opt = await screen.findByText("En progreso");
    fireEvent.click(opt);
    await waitFor(() =>
      expect(tasksApi.update).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ state: "in_progress" }),
      ),
    );
  });
});
