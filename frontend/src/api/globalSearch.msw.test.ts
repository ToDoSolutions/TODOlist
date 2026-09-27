// Tests de contrato a nivel HTTP real: axios → MSW → validación Zod.
// Complementan los tests con vi.mock validando el pipeline completo.
import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { faker } from "@faker-js/faker";
import fc from "fast-check";
import { tasksApi } from "./resources";
import { server } from "../test/msw";
import { buildResults } from "../lib/commandPalette";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const makeItem = () => ({
  type: "task",
  id: faker.number.int({ min: 1, max: 10_000 }),
  title: faker.lorem.sentence(3),
  state: "open",
});

describe("globalSearch — contrato HTTP (msw)", () => {
  it("devuelve resultados validados por zod", async () => {
    const fakeTasks = Array.from({ length: 3 }, makeItem);
    server.use(
      http.get("*/api/tasks/global-search/", () =>
        HttpResponse.json({ tasks: fakeTasks, comments: [], wiki: [], projects: [] }),
      ),
    );
    const res = await tasksApi.globalSearch("foo");
    expect(res.tasks).toHaveLength(3);
    expect(res.tasks[0]?.title).toBe(fakeTasks[0]!.title);
  });

  it("rechaza respuestas malformadas del servidor", async () => {
    server.use(
      http.get("*/api/tasks/global-search/", () =>
        HttpResponse.json({ tasks: "no-es-un-array", comments: [] }),
      ),
    );
    await expect(tasksApi.globalSearch("foo")).rejects.toThrow();
  });
});

describe("buildResults — propiedades (fast-check)", () => {
  const itemArb = fc.record({
    type: fc.constant("task"),
    id: fc.nat({ max: 999_999 }),
    title: fc.string({ maxLength: 60 }),
  });
  const commentArb = fc.record({
    type: fc.constant("comment"),
    id: fc.nat({ max: 999_999 }),
    title: fc.string({ maxLength: 60 }),
    task: fc.record({ id: fc.nat(), title: fc.string({ maxLength: 30 }) }),
  });
  const itemsArb = fc.uniqueArray(itemArb, {
    selector: (i) => i.id,
    maxLength: 12,
  });
  const commentsArb = fc.uniqueArray(commentArb, {
    selector: (i) => i.id,
    maxLength: 12,
  });
  const payloadArb = fc.record({
    tasks: itemsArb,
    comments: commentsArb,
    wiki: itemsArb,
    projects: itemsArb,
  });

  it("nunca produce keys duplicadas ni más de 8 items por grupo", () => {
    fc.assert(
      fc.property(payloadArb, (payload) => {
        const results = buildResults(payload as any);
        const keys = results.map((r) => r.key);
        expect(new Set(keys).size).toBe(keys.length);
        const perGroup = results.reduce<Record<string, number>>((acc, r) => {
          acc[r.group] = (acc[r.group] || 0) + 1;
          return acc;
        }, {});
        for (const count of Object.values(perGroup)) {
          expect(count).toBeLessThanOrEqual(8);
        }
      }),
    );
  });

  it("preserva todos los ids de entrada en las keys", () => {
    fc.assert(
      fc.property(payloadArb, (payload) => {
        const results = buildResults(payload as any);
        const keys = new Set(results.map((r) => r.key));
        for (const g of Object.values(payload)) {
          for (const item of (g as typeof payload.tasks).slice(0, 8)) {
            expect(
              keys.has(`task-${item.id}`) ||
                keys.has(`comment-${item.id}`) ||
                keys.has(`wiki-${item.id}`) ||
                keys.has(`project-${item.id}`),
            ).toBe(true);
          }
        }
      }),
    );
  });
});
