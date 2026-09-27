import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider, createTheme } from "@mui/material";
import { MemoryRouter } from "react-router-dom";
import { createElement, type ReactNode } from "react";
import TaskListItem from "./TaskListItem";
import type { Task } from "../types";

vi.mock("../api/resources", () => ({
  tasksApi: {
    update: vi.fn(),
    delete: vi.fn(),
    activities: vi.fn().mockResolvedValue([]),
  },
  sprintsApi: { list: vi.fn().mockResolvedValue({ results: [] }) },
}));
vi.mock("../notify", () => ({ notify: vi.fn() }));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    title: "Tarea test",
    description: "desc",
    state: "pending",
    priority: 3,
    task_type: "task",
    due_date: null,
    start_date: null,
    completed_at: null,
    story_points: 3,
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
    createElement(
      ThemeProvider,
      { theme: createTheme() },
      createElement(MemoryRouter, null, children),
    ),
  );
}

describe("TaskListItem", () => {
  it("muestra título, estado y prioridad", () => {
    render(<TaskListItem task={makeTask({ title: "Mi tarea" })} onEdit={vi.fn()} />, {
      wrapper,
    });
    expect(screen.getByText("Mi tarea")).toBeTruthy();
    expect(screen.getByText("Pendiente")).toBeTruthy();
  });

  it("marca visualmente tareas completadas", () => {
    render(
      <TaskListItem
        task={makeTask({ state: "completed", title: "Hecha" })}
        onEdit={vi.fn()}
      />,
      { wrapper },
    );
    expect(screen.getByText("Completada")).toBeTruthy();
  });

  it("muestra progreso de subtareas cuando existen", () => {
    render(
      <TaskListItem
        task={makeTask({
          subtasks: [
            { id: 1, title: "a", is_done: true, order: 0 },
            { id: 2, title: "b", is_done: false, order: 1 },
            { id: 3, title: "c", is_done: true, order: 2 },
          ] as Task["subtasks"],
        })}
        onEdit={vi.fn()}
      />,
      { wrapper },
    );
    expect(screen.getByText(/2\/3 subtareas/)).toBeTruthy();
  });

  it("llama a onEdit al hacer click en la tarea", () => {
    const onEdit = vi.fn();
    render(
      <TaskListItem task={makeTask({ id: 9, title: "Editable" })} onEdit={onEdit} />,
      { wrapper },
    );
    fireEvent.click(screen.getByText("Editable"));
    expect(onEdit).toHaveBeenCalled();
  });
});
