import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useRealtime } from "./useRealtime";

// Mock mínimo de WebSocket que captura instancias y permite simular eventos
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onopen: (() => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

describe("useRealtime", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
  });

  it("no conecta si enabled=false", () => {
    const qc = new QueryClient();
    renderHook(() => useRealtime(false), { wrapper: wrapper(qc) });
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("conecta a tasks y notifications vía cookie (sin ?token=)", () => {
    const qc = new QueryClient();
    renderHook(() => useRealtime(true), { wrapper: wrapper(qc) });
    expect(MockWebSocket.instances).toHaveLength(2);
    const urls = MockWebSocket.instances.map((w) => w.url);
    expect(urls.some((u) => u.includes("/ws/tasks/"))).toBe(true);
    expect(urls.some((u) => u.includes("/ws/notifications/"))).toBe(true);
    // El token JWT no debe viajar en la query string (cookie httpOnly)
    for (const u of urls) expect(u).not.toContain("token=");
  });

  it("invalida cache de tasks al recibir task.updated", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    renderHook(() => useRealtime(true), { wrapper: wrapper(qc) });
    const ws = MockWebSocket.instances.find((w) => w.url.includes("tasks"))!;
    ws.simulateMessage({ type: "task.updated", task: { id: 1 } });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["tasks"] });
  });

  it("invalida notifications y unread al recibir notification.new", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    renderHook(() => useRealtime(true), { wrapper: wrapper(qc) });
    const ws = MockWebSocket.instances.find((w) => w.url.includes("notifications"))!;
    ws.simulateMessage({ type: "notification.new", notification: {} });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["notifications"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["notifications-unread"] });
  });

  it("ignora mensajes no-JSON o sin type", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    renderHook(() => useRealtime(true), { wrapper: wrapper(qc) });
    const ws = MockWebSocket.instances[0]!;
    ws.onmessage?.({ data: "not-json{{{" });
    ws.simulateMessage({ foo: "bar" });
    expect(spy).not.toHaveBeenCalled();
  });

  it("cierra sockets al desmontar", () => {
    const qc = new QueryClient();
    const { unmount } = renderHook(() => useRealtime(true), {
      wrapper: wrapper(qc),
    });
    unmount();
    expect(MockWebSocket.instances.every((w) => w.closed)).toBe(true);
  });
});
