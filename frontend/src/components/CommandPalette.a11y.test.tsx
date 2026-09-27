// Auditoría de accesibilidad automática (axe-core) sobre la palette.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { axe } from "jest-axe";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { createElement } from "react";
import CommandPalette from "./CommandPalette";

vi.mock("../api/resources", () => ({
  tasksApi: {
    globalSearch: vi
      .fn()
      .mockResolvedValue({ tasks: [], comments: [], wiki: [], projects: [] }),
  },
}));

describe("CommandPalette — accesibilidad (axe)", () => {
  afterEach(cleanup);

  it("sin violaciones en estado vacío", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      createElement(
        QueryClientProvider,
        { client: qc },
        createElement(
          MemoryRouter,
          null,
          createElement(CommandPalette, { open: true, onClose: () => {} }),
        ),
      ),
    );
    const results = await axe(document.body);
    expect(results.violations).toEqual([]);
  });
});
