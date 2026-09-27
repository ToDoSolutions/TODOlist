import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import OfflineSyncPage from "./OfflineSyncPage";

vi.mock("../api/resources", () => ({
  offlineSyncApi: {
    registerDevice: vi.fn(),
    push: vi.fn(),
    pull: vi.fn(),
  },
  syncOperationsApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}));
vi.mock("../notify", () => ({
  notify: { success: vi.fn(), error: vi.fn() },
}));

import { offlineSyncApi, syncOperationsApi } from "../api/resources";
import { notify } from "../notify";

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    createElement(QueryClientProvider, { client: qc }, createElement(OfflineSyncPage)),
  );
}

describe("OfflineSyncPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renderiza el estado sin sincronizar", () => {
    renderPage();
    expect(screen.getAllByText(/sincronización offline/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/no se ha sincronizado/i)).toBeTruthy();
  });

  it("botón registrar deshabilitado sin nombre", () => {
    renderPage();
    const btn = screen.getByRole("button", { name: /registrar/i });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("registrar dispositivo llama a la API", async () => {
    (offlineSyncApi.registerDevice as ReturnType<typeof vi.fn>).mockResolvedValue({
      device_id: "dev-1",
    });
    renderPage();
    fireEvent.change(screen.getByLabelText(/nombre del dispositivo/i), {
      target: { value: "Mi móvil" },
    });
    fireEvent.click(screen.getByRole("button", { name: /registrar/i }));
    await waitFor(() => expect(offlineSyncApi.registerDevice).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText(/registrado: dev-1/i)).toBeTruthy());
  });

  it("push con JSON inválido muestra error y no llama API", async () => {
    renderPage();
    const textarea = screen.getByPlaceholderText(/"op": "create"/);
    fireEvent.change(textarea, { target: { value: "{no json" } });
    fireEvent.click(screen.getByRole("button", { name: /enviar/i }));
    await waitFor(() => expect(notify.error).toHaveBeenCalled());
    expect(offlineSyncApi.push).not.toHaveBeenCalled();
  });

  it("push con no-array muestra error", async () => {
    renderPage();
    const textarea = screen.getByPlaceholderText(/"op": "create"/);
    fireEvent.change(textarea, { target: { value: '{"a": 1}' } });
    fireEvent.click(screen.getByRole("button", { name: /enviar/i }));
    await waitFor(() => expect(notify.error).toHaveBeenCalled());
    expect(offlineSyncApi.push).not.toHaveBeenCalled();
  });

  it("push válido envía operaciones y marca última sync", async () => {
    (offlineSyncApi.push as ReturnType<typeof vi.fn>).mockResolvedValue({
      applied: 1,
    });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /enviar/i }));
    await waitFor(() =>
      expect(offlineSyncApi.push).toHaveBeenCalledWith([
        { op: "create", entity: "task", data: {} },
      ]),
    );
    await waitFor(() => expect(screen.getByText(/última sincronización/i)).toBeTruthy());
  });

  it("pull usa fecha por defecto cuando está vacía", async () => {
    (offlineSyncApi.pull as ReturnType<typeof vi.fn>).mockResolvedValue({
      changes: [],
    });
    renderPage();
    fireEvent.click(
      screen.getByRole("button", { name: /descargar|pull|traer|recibir/i }),
    );
    await waitFor(() =>
      expect(offlineSyncApi.pull).toHaveBeenCalledWith("2000-01-01T00:00:00Z"),
    );
  });

  it("pull muestra los cambios recibidos", async () => {
    (offlineSyncApi.pull as ReturnType<typeof vi.fn>).mockResolvedValue({
      changes: [{ id: 1 }, { id: 2 }, { id: 3 }],
    });
    renderPage();
    fireEvent.click(
      screen.getByRole("button", { name: /descargar|pull|traer|recibir/i }),
    );
    await waitFor(() => expect(screen.getByText(/última sincronización/i)).toBeTruthy());
  });

  it("carga operaciones de sync al montar", async () => {
    (syncOperationsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id: 1, op_type: "create" },
    ]);
    renderPage();
    await waitFor(() => expect(syncOperationsApi.list).toHaveBeenCalled());
  });
});
