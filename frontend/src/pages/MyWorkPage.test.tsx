import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import MyWorkPage from "./MyWorkPage";
import type { MyWork } from "../api/resources";

vi.mock("../api/resources", () => ({
  tasksApi: { myWork: vi.fn() },
}));

import { tasksApi } from "../api/resources";
const myWorkMock = tasksApi.myWork as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    createElement(QueryClientProvider, { client: qc }, createElement(MyWorkPage)),
  );
}

const empty: MyWork = {
  overdue: [],
  due_today: [],
  in_progress: [],
  blocked: [],
  upcoming: [],
};

describe("MyWorkPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("agrupa tareas por urgencia", async () => {
    myWorkMock.mockResolvedValue({
      ...empty,
      overdue: [
        {
          id: 1,
          title: "Vencida",
          state: "pending",
          priority: 1,
          due_date: "2024-01-01",
          project: null,
        },
      ],
      in_progress: [
        {
          id: 2,
          title: "En curso",
          state: "in_progress",
          priority: 2,
          due_date: null,
          project: "P1",
        },
      ],
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Vencida")).toBeTruthy());
    expect(screen.getByText("En curso")).toBeTruthy();
    expect(screen.getByText("Vencidas")).toBeTruthy();
    expect(screen.getByText("Para hoy")).toBeTruthy();
  });

  it("muestra el blocker inline", async () => {
    myWorkMock.mockResolvedValue({
      ...empty,
      blocked: [
        {
          id: 1,
          title: "Bloqueada",
          state: "pending",
          priority: 1,
          due_date: null,
          project: null,
          blocked_by: [{ id: 9, title: "Bloqueante", state: "pending" }],
        },
      ],
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("🔒 Bloqueante")).toBeTruthy());
  });

  it("empty state cuando no hay nada urgente", async () => {
    myWorkMock.mockResolvedValue(empty);
    renderPage();
    await waitFor(() => expect(screen.getByText("Todo completado")).toBeTruthy());
  });
});
