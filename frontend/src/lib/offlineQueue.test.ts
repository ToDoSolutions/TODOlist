import { describe, it, expect, beforeEach } from "vitest";
import { offlineQueue, isQueueable } from "./offlineQueue";

describe("offlineQueue", () => {
  beforeEach(() => {
    localStorage.clear();
    offlineQueue.clear();
  });

  it("enqueue/list/drop persisten en localStorage", () => {
    const op = offlineQueue.enqueue({
      method: "post",
      url: "/tasks/",
      data: { title: "t" },
    });
    expect(offlineQueue.size()).toBe(1);
    expect(offlineQueue.list()[0]?.url).toBe("/tasks/");
    // sobrevive a un "reload" (releer storage)
    const raw = localStorage.getItem("todolist.offlineQueue");
    expect(raw && JSON.parse(raw)[0].id).toBe(op.id);
    offlineQueue.drop(op.id);
    expect(offlineQueue.size()).toBe(0);
  });

  it("data serializada como string JSON se parsea al encolar", () => {
    const op = offlineQueue.enqueue({
      method: "patch",
      url: "/tasks/1/",
      data: '{"state":"done"}',
    });
    expect(op.data).toEqual({ state: "done" });
  });

  it("isQueueable: mutaciones sí, lecturas/auth/sync no", () => {
    expect(isQueueable({ method: "post", url: "/tasks/" })).toBe(true);
    expect(isQueueable({ method: "delete", url: "/tasks/1/" })).toBe(true);
    expect(isQueueable({ method: "get", url: "/tasks/" })).toBe(false);
    expect(isQueueable({ method: "post", url: "/auth/login/" })).toBe(false);
    expect(isQueueable({ method: "post", url: "/sync/push/" })).toBe(false);
    expect(
      isQueueable({ method: "post", url: "/tasks/", _offline_replay: true }),
    ).toBe(false);
  });
});
