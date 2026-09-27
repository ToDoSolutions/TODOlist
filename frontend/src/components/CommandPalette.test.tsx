import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import CommandPalette from "./CommandPalette";

vi.mock("../api/resources", () => ({
  tasksApi: { globalSearch: vi.fn() },
}));
import { tasksApi } from "../api/resources";
const searchMock = tasksApi.globalSearch as ReturnType<typeof vi.fn>;

function renderPalette() {
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
        createElement(CommandPalette, {
          open: true,
          onClose: vi.fn(),
        }),
      ),
    ),
  );
}

describe("CommandPalette", () => {
  beforeEach(() => vi.clearAllMocks());

  it("muestra ayuda de sintaxis con input vacío", () => {
    renderPalette();
    expect(screen.getByText(/assigned:me/)).toBeTruthy();
    expect(screen.getByText(/status:open/)).toBeTruthy();
  });

  it("muestra resultados agrupados por tipo", async () => {
    searchMock.mockResolvedValue({
      query: "oauth",
      filters: {},
      tasks: [
        {
          type: "task",
          id: 1,
          title: "Fix oauth",
          state: "pending",
          priority: 1,
          project: "P1",
        },
      ],
      comments: [],
      wiki: [{ type: "wiki", id: 2, title: "Runbook oauth", project: null }],
      projects: [{ type: "project", id: 3, title: "api", is_archived: false }],
    });
    renderPalette();
    const input = screen.getByPlaceholderText(/buscar/i);
    fireEvent.change(input, { target: { value: "oauth" } });
    await waitFor(() => expect(screen.getByText("Fix oauth")).toBeTruthy(), {
      timeout: 3000,
    });
    expect(screen.getByText("Runbook oauth")).toBeTruthy();
    expect(screen.getByText("api")).toBeTruthy();
    // Headers de grupo
    expect(screen.getByText("Tareas")).toBeTruthy();
    expect(screen.getByText("Wiki")).toBeTruthy();
    expect(screen.getByText("Proyectos")).toBeTruthy();
  });

  it("no busca con query vacía", () => {
    renderPalette();
    expect(searchMock).not.toHaveBeenCalled();
  });
});
