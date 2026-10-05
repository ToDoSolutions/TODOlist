import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider, createTheme } from "@mui/material";
import { MemoryRouter } from "react-router-dom";
import { createElement, type ReactNode } from "react";
import NotificationBell from "./NotificationBell";

vi.mock("../api/resources", () => ({
  notificationsApi: {
    unreadCount: vi.fn(),
    list: vi.fn(),
    markAllRead: vi.fn(),
    markRead: vi.fn(),
  },
}));

import { notificationsApi } from "../api/resources";

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

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (notificationsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it("muestra badge con el contador de no leídas", async () => {
    (notificationsApi.unreadCount as ReturnType<typeof vi.fn>).mockResolvedValue({
      count: 7,
    });
    render(<NotificationBell />, { wrapper });
    await waitFor(() => expect(screen.getByText("7")).toBeTruthy());
  });

  it("sin notificaciones no leídas muestra 0", async () => {
    (notificationsApi.unreadCount as ReturnType<typeof vi.fn>).mockResolvedValue({
      count: 0,
    });
    render(<NotificationBell />, { wrapper });
    await waitFor(() => expect(screen.getByText("0")).toBeTruthy());
  });

  it("al abrir carga la lista y muestra los items", async () => {
    (notificationsApi.unreadCount as ReturnType<typeof vi.fn>).mockResolvedValue({
      count: 1,
    });
    (notificationsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 1,
        type: "task_assigned",
        title: "Tarea asignada",
        body: "Te asignaron X",
        read: false,
        created_at: new Date().toISOString(),
      },
    ]);
    render(<NotificationBell />, { wrapper });
    // Abrir popover
    const bell = document.querySelector("button")!;
    fireEvent.click(bell);
    await waitFor(() => expect(screen.getByText("Tarea asignada")).toBeTruthy());
    expect(screen.getByText("Asignada")).toBeTruthy(); // TYPE_LABELS
  });

  it("marcar todas como leídas llama markAllRead", async () => {
    (notificationsApi.unreadCount as ReturnType<typeof vi.fn>).mockResolvedValue({
      count: 2,
    });
    (notificationsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 1,
        type: "custom",
        title: "N1",
        body: "",
        read: false,
        created_at: new Date().toISOString(),
      },
    ]);
    (notificationsApi.markAllRead as ReturnType<typeof vi.fn>).mockResolvedValue({});
    render(<NotificationBell />, { wrapper });
    fireEvent.click(document.querySelector("button")!);
    await waitFor(() => screen.getByText("N1"));
    const markAll = screen.getByRole("button", { name: /marcar|leíd|read/i });
    fireEvent.click(markAll);
    await waitFor(() => expect(notificationsApi.markAllRead).toHaveBeenCalled());
  });
});
