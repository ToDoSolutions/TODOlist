import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "@mui/material";
import AppLayout from "./AppLayout";
import { theme } from "../theme";

// Mock auth
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: 1, email: "test@test.com", username: "test" },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

// Mock API resources - simula respuestas paginadas del backend real
vi.mock("../api/resources", () => ({
  projectsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 1, name: "Proyecto Test", color: "#1976d2", tasks_count: 2 },
    ]),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
  tasksApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 1,
        title: "Tarea 1",
        state: "pending",
        priority: 3,
        due_date: null,
        subtasks: [],
        tags: [],
      },
    ]),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    addSubtask: vi.fn(),
    addComment: vi.fn(),
    updateSubtask: vi.fn(),
    removeSubtask: vi.fn(),
  },
  notificationsApi: {
    list: vi.fn().mockResolvedValue({ results: [] }),
    unreadCount: vi.fn().mockResolvedValue({ count: 0 }),
    markAllRead: vi.fn().mockResolvedValue({ marked: 0 }),
    markRead: vi.fn(),
    markUnread: vi.fn(),
    preferences: vi.fn().mockResolvedValue({ results: [] }),
    updatePreference: vi.fn(),
  },
  automationsApi: {
    list: vi.fn().mockResolvedValue({ results: [] }),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    test: vi.fn(),
    logs: vi.fn().mockResolvedValue({ results: [] }),
  },
  collaborationApi: {
    teams: {
      list: vi.fn().mockResolvedValue({ results: [] }),
      create: vi.fn(),
      members: vi.fn().mockResolvedValue([]),
      addMember: vi.fn(),
      removeMember: vi.fn(),
    },
    projectMembers: {
      list: vi.fn().mockResolvedValue({ results: [] }),
      invite: vi.fn(),
    },
    mentions: {
      list: vi.fn().mockResolvedValue({ results: [] }),
    },
    auditLogs: {
      list: vi.fn().mockResolvedValue({ results: [] }),
    },
  },
  apiKeysApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    revoke: vi.fn(),
    delete: vi.fn(),
  },
  twofactorApi: {
    status: vi.fn().mockResolvedValue({ is_enabled: false }),
    setup: vi.fn(),
    confirm: vi.fn(),
    disable: vi.fn(),
    verify: vi.fn(),
  },
}));

// Mock notistack
vi.mock("notistack", () => ({
  SnackbarProvider: ({ children }: any) => children,
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider theme={theme}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

describe("AppLayout - render sin crash", () => {
  it("renderiza el sidebar con proyectos sin crashear", async () => {
    const { container } = renderWithProviders(
      <AppLayout />
    );
    // Esperar a que el texto "Proyectos" aparezca
    const proyectosText = await screen.findByText(/Proyectos/i, undefined, {
      timeout: 3000,
    });
    expect(proyectosText).toBeDefined();
    expect(container.innerHTML).toContain("TODOlist");
  });

  it("renderiza la bandeja de entrada en el sidebar", async () => {
    renderWithProviders(<AppLayout />);
    const inbox = await screen.findByText(/Bandeja de entrada/i, undefined, {
      timeout: 3000,
    });
    expect(inbox).toBeDefined();
  });
});
