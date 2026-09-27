import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider, createTheme } from "@mui/material";
import { createElement, type ReactNode } from "react";
import KanbanBoard from "./KanbanBoard";
import type { Task } from "../types";

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

describe("KanbanBoard", () => {
  it("renderiza las columnas por estado", () => {
    render(<KanbanBoard tasks={[]} onEdit={vi.fn()} />, { wrapper });
    for (const label of [
      "Backlog",
      "Pendiente",
      "En progreso",
      "Bloqueada",
      "En revisión",
      "Completada",
    ]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it("coloca cada tarea en su columna por estado", () => {
    const tasks = [
      makeTask({ id: 1, title: "Tarea backlog", state: "backlog" }),
      makeTask({ id: 2, title: "Tarea progreso", state: "in_progress" }),
      makeTask({ id: 3, title: "Tarea hecha", state: "completed" }),
    ];
    render(<KanbanBoard tasks={tasks} onEdit={vi.fn()} />, { wrapper });
    expect(screen.getByText("Tarea backlog")).toBeTruthy();
    expect(screen.getByText("Tarea progreso")).toBeTruthy();
    expect(screen.getByText("Tarea hecha")).toBeTruthy();
  });

  it("filtra por búsqueda", () => {
    const tasks = [
      makeTask({ id: 1, title: "Fix bug crítico", state: "pending" }),
      makeTask({ id: 2, title: "Nueva feature", state: "pending" }),
    ];
    render(<KanbanBoard tasks={tasks} onEdit={vi.fn()} />, { wrapper });
    const search = screen.getByPlaceholderText(/buscar/i);
    fireEvent.change(search, { target: { value: "bug" } });
    expect(screen.getByText("Fix bug crítico")).toBeTruthy();
    expect(screen.queryByText("Nueva feature")).toBeNull();
  });

  it("llama a onEdit al hacer click en una tarjeta", () => {
    const onEdit = vi.fn();
    const tasks = [makeTask({ id: 7, title: "Click me", state: "pending" })];
    render(<KanbanBoard tasks={tasks} onEdit={onEdit} />, { wrapper });
    fireEvent.click(screen.getByText("Click me"));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 7 }));
  });

  it("muestra swimlanes al agrupar por prioridad", () => {
    const tasks = [
      makeTask({ id: 1, title: "Alta", state: "pending", priority: 1 }),
      makeTask({ id: 2, title: "Baja", state: "pending", priority: 5 }),
    ];
    render(<KanbanBoard tasks={tasks} onEdit={vi.fn()} />, { wrapper });
    // Abrir el selector de swimlanes
    const btn = screen.getByRole("button", { name: /swimlane|agrupar|sin swimlanes/i });
    fireEvent.click(btn);
    const prio = screen.getByText(/prioridad/i);
    fireEvent.click(prio);
    // Las dos tareas siguen visibles pero agrupadas por prioridad
    expect(screen.getByText("Alta")).toBeTruthy();
    expect(screen.getByText("Baja")).toBeTruthy();
  });
});
