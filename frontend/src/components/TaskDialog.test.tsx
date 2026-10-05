import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider, createTheme } from "@mui/material";
import TaskDialog from "./TaskDialog";
import type { Task } from "../types";

// Mock notify
vi.mock("../notify", () => ({
  notify: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    dismiss: vi.fn(),
  },
}));

// Mock API resources
vi.mock("../api/resources", () => ({
  projectsApi: {
    list: vi
      .fn()
      .mockResolvedValue([
        { id: 1, name: "Proyecto Test", color: "#1976d2", tasks_count: 0 },
      ]),
  },
  tagsApi: {
    list: vi.fn().mockResolvedValue([{ id: 1, name: "Trabajo", color: "#1976d2" }]),
  },
  tasksApi: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    addSubtask: vi.fn(),
    addComment: vi.fn(),
    updateSubtask: vi.fn(),
    removeSubtask: vi.fn(),
    updateComment: vi.fn(),
    removeComment: vi.fn(),
    reactComment: vi.fn(),
    getRelations: vi.fn(),
    addRelation: vi.fn(),
    removeRelation: vi.fn(),
  },
  attachmentsApi: {
    list: vi.fn(),
    upload: vi.fn(),
    remove: vi.fn(),
  },
  customFieldsApi: {
    list: vi.fn().mockResolvedValue([]),
    values: vi.fn().mockResolvedValue([]),
    setValue: vi.fn(),
    updateValue: vi.fn(),
    removeValue: vi.fn(),
  },
  encryptionApi: {
    getActiveKey: vi.fn().mockRejectedValue(new Error("no key")),
  },
}));

import { tasksApi, attachmentsApi } from "../api/resources";

const baseTask: Task = {
  id: 10,
  title: "Tarea de prueba",
  description: "Descripción",
  state: "pending",
  priority: 3,
  task_type: "task",
  due_date: null,
  start_date: null,
  completed_at: null,
  story_points: null,
  estimate_hours: null,
  size: "",
  project: 1,
  tags: [],
  tags_ids: [],
  parent: null,
  parent_title: null,
  sprint: null,
  sprint_name: null,
  epic: null,
  epic_title: null,
  assignee: null,
  assignee_email: null,
  subtask_done: 0,
  subtask_total: 0,
  subtasks: [],
  comments: [],
  recurrence: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider theme={createTheme()}>{ui}</ThemeProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  (tasksApi.getRelations as any).mockResolvedValue([]);
  (attachmentsApi.list as any).mockResolvedValue([]);
});

describe("TaskDialog - Renderizado general", () => {
  it('muestra "Nueva tarea" cuando task es null', () => {
    renderWithProviders(
      <TaskDialog open={true} task={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByText("Nueva tarea")).toBeTruthy();
  });

  it("muestra el título de la tarea en la cabecera del panel", () => {
    renderWithProviders(
      <TaskDialog open={true} task={baseTask} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByText(`#${baseTask.id} · ${baseTask.title}`)).toBeTruthy();
    expect(screen.getByText("Propiedades")).toBeTruthy();
  });

  it("llama onClose al hacer clic en Cancelar", () => {
    const onClose = vi.fn();
    renderWithProviders(
      <TaskDialog open={true} task={null} onClose={onClose} onSaved={vi.fn()} />,
    );
    fireEvent.click(screen.getByText("Cancelar"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("TaskDialog - Subtareas", () => {
  it("renderiza la lista de subtareas cuando task tiene subtareas", () => {
    const task: Task = {
      ...baseTask,
      subtasks: [
        {
          id: 1,
          title: "Subtarea A",
          is_done: false,
          order: 0,
          created_at: "2024-01-01T00:00:00Z",
        },
        {
          id: 2,
          title: "Subtarea B",
          is_done: true,
          order: 1,
          created_at: "2024-01-01T00:00:00Z",
        },
      ],
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByText("Subtarea A")).toBeTruthy();
    expect(screen.getByText("Subtarea B")).toBeTruthy();
  });

  it("muestra el botón de editar subtarea", () => {
    const task: Task = {
      ...baseTask,
      subtasks: [
        {
          id: 1,
          title: "Subtarea A",
          is_done: false,
          order: 0,
          created_at: "2024-01-01T00:00:00Z",
        },
      ],
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByLabelText("Editar subtarea")).toBeTruthy();
  });

  it("muestra el botón de eliminar subtarea", () => {
    const task: Task = {
      ...baseTask,
      subtasks: [
        {
          id: 1,
          title: "Subtarea A",
          is_done: false,
          order: 0,
          created_at: "2024-01-01T00:00:00Z",
        },
      ],
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByLabelText("Eliminar subtarea")).toBeTruthy();
  });
});

describe("TaskDialog - Comentarios", () => {
  it("renderiza la lista de comentarios cuando task tiene comentarios", () => {
    const task: Task = {
      ...baseTask,
      comments: [
        {
          id: 1,
          body: "Comentario de prueba",
          author_email: "user@test.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByText("Comentario de prueba")).toBeTruthy();
  });

  it("muestra el botón de editar comentario", () => {
    const task: Task = {
      ...baseTask,
      comments: [
        {
          id: 1,
          body: "Comentario de prueba",
          author_email: "user@test.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByLabelText("Editar")).toBeTruthy();
  });

  it("muestra el botón de eliminar comentario", () => {
    const task: Task = {
      ...baseTask,
      comments: [
        {
          id: 1,
          body: "Comentario de prueba",
          author_email: "user@test.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByLabelText("Eliminar")).toBeTruthy();
  });

  it('muestra el chip de "Mención" cuando un comentario contiene @usuario', () => {
    const task: Task = {
      ...baseTask,
      comments: [
        {
          id: 1,
          body: "Hola @usuario revisa esto",
          author_email: "user@test.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByText("Mención")).toBeTruthy();
  });
});

describe("TaskDialog - Relaciones", () => {
  it("renderiza la lista de relaciones", async () => {
    (tasksApi.getRelations as any).mockResolvedValue([
      {
        id: 1,
        source: 10,
        source_title: "Tarea de prueba",
        target: 20,
        target_title: "Otra tarea",
        relation_type: "blocks",
        created_at: "2024-01-01T00:00:00Z",
      },
    ]);
    renderWithProviders(
      <TaskDialog open={true} task={baseTask} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(await screen.findByText(/Otra tarea/)).toBeTruthy();
    // "Bloquea" aparece tanto en el chip de la relación como en el Select por defecto
    expect(screen.getAllByText("Bloquea").length).toBeGreaterThanOrEqual(1);
  });

  it("muestra el botón de eliminar relación", async () => {
    (tasksApi.getRelations as any).mockResolvedValue([
      {
        id: 1,
        source: 10,
        source_title: "Tarea de prueba",
        target: 20,
        target_title: "Otra tarea",
        relation_type: "blocks",
        created_at: "2024-01-01T00:00:00Z",
      },
    ]);
    renderWithProviders(
      <TaskDialog open={true} task={baseTask} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(await screen.findByLabelText("Eliminar relación")).toBeTruthy();
  });
});

describe("TaskDialog - Adjuntos", () => {
  it("renderiza la lista de adjuntos", async () => {
    (attachmentsApi.list as any).mockResolvedValue([
      { id: 1, filename: "doc.pdf", file_size: 2048 },
    ]);
    renderWithProviders(
      <TaskDialog open={true} task={baseTask} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(await screen.findByText(/doc\.pdf/)).toBeTruthy();
  });

  it("muestra el botón de descargar adjunto", async () => {
    (attachmentsApi.list as any).mockResolvedValue([
      { id: 1, filename: "doc.pdf", file_size: 2048 },
    ]);
    renderWithProviders(
      <TaskDialog open={true} task={baseTask} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(await screen.findByLabelText("Descargar")).toBeTruthy();
  });

  it("muestra el botón de eliminar adjunto", async () => {
    (attachmentsApi.list as any).mockResolvedValue([
      { id: 1, filename: "doc.pdf", file_size: 2048 },
    ]);
    renderWithProviders(
      <TaskDialog open={true} task={baseTask} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(await screen.findByLabelText("Eliminar adjunto")).toBeTruthy();
  });
});

describe("TaskDialog - Estimación (story_points/estimate_hours/size)", () => {
  // Estos campos existían en backend y se renderizaban en kanban/tabla
  // pero el dialogo no los exponía: sin editor era imposible ponerlos.
  it("precarga puntos, horas estimadas y talla al editar", async () => {
    const task: Task = {
      ...baseTask,
      story_points: 5,
      estimate_hours: 2.5,
      size: "m",
    };
    renderWithProviders(
      <TaskDialog open={true} task={task} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(await screen.findByLabelText("Puntos")).toHaveProperty(
      "value",
      "5",
    );
    expect(await screen.findByLabelText("Horas est.")).toHaveProperty(
      "value",
      "2.5",
    );
    // El select de talla muestra la etiqueta traducida de "m"
    expect(screen.getAllByText("M").length).toBeGreaterThan(0);
  });

  it("los campos de estimación aparecen también al crear", () => {
    renderWithProviders(
      <TaskDialog open={true} task={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.getByLabelText("Puntos")).toHaveProperty("value", "");
    expect(screen.getByLabelText("Horas est.")).toHaveProperty("value", "");
  });
});
