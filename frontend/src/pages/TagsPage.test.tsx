import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ConfirmProvider } from "../components/ConfirmDialog";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import TagsPage from "./TagsPage";
import type { Tag } from "../types";

vi.mock("../api/resources", () => ({
  tagsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));
vi.mock("../notify", () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { tagsApi } from "../api/resources";
import { notify } from "../notify";

const listMock = tagsApi.list as ReturnType<typeof vi.fn>;
const createMock = tagsApi.create as ReturnType<typeof vi.fn>;
const updateMock = tagsApi.update as ReturnType<typeof vi.fn>;
const removeMock = tagsApi.remove as ReturnType<typeof vi.fn>;

function makeTag(overrides: Partial<Tag> = {}): Tag {
  return {
    id: 1,
    name: "bug",
    color: "#ff0000",
    ...overrides,
  } as Tag;
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    createElement(
      QueryClientProvider,
      { client: qc },
      createElement(ConfirmProvider, null, createElement(TagsPage)),
    ),
  );
}

describe("TagsPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("muestra estado de carga", () => {
    listMock.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole("progressbar")).toBeTruthy();
  });

  it("muestra empty state sin etiquetas", async () => {
    listMock.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(/no hay etiquetas/i)).toBeTruthy());
  });

  it("lista etiquetas como chips", async () => {
    listMock.mockResolvedValue([
      makeTag({ id: 1, name: "bug" }),
      makeTag({ id: 2, name: "urgente" }),
    ]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("bug")).toBeTruthy();
      expect(screen.getByText("urgente")).toBeTruthy();
    });
  });

  it("crear: botón deshabilitado con nombre vacío", async () => {
    listMock.mockResolvedValue([]);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /nueva etiqueta/i }));
    const guardar = screen.getByRole("button", { name: /guardar/i });
    expect((guardar as HTMLButtonElement).disabled).toBe(true);
    expect(createMock).not.toHaveBeenCalled();
  });

  it("crear etiqueta llama a la API con trim", async () => {
    createMock.mockResolvedValue({});
    listMock.mockResolvedValue([]);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /nueva etiqueta/i }));
    fireEvent.change(screen.getByLabelText(/nombre/i), {
      target: { value: "  feature  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /guardar/i }));
    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({ name: "feature" }),
      ),
    );
    expect(notify.success).toHaveBeenCalled();
  });

  it("error al crear muestra notificación", async () => {
    createMock.mockRejectedValue(new Error("fail"));
    listMock.mockResolvedValue([]);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /nueva etiqueta/i }));
    fireEvent.change(screen.getByLabelText(/nombre/i), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /guardar/i }));
    await waitFor(() => expect(notify.error).toHaveBeenCalled());
  });

  it("click en chip abre edición con datos precargados", async () => {
    updateMock.mockResolvedValue({});
    listMock.mockResolvedValue([makeTag({ id: 5, name: "docs" })]);
    renderPage();
    await waitFor(() => screen.getByText("docs"));
    fireEvent.click(screen.getByText("docs"));
    const input = screen.getByLabelText(/nombre/i) as HTMLInputElement;
    expect(input.value).toBe("docs");
    expect(screen.getByText(/editar etiqueta/i)).toBeTruthy();
  });

  it("editar llama a update con el id", async () => {
    updateMock.mockResolvedValue({});
    listMock.mockResolvedValue([makeTag({ id: 5, name: "docs" })]);
    renderPage();
    await waitFor(() => screen.getByText("docs"));
    fireEvent.click(screen.getByText("docs"));
    fireEvent.change(screen.getByLabelText(/nombre/i), {
      target: { value: "docs2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /guardar/i }));
    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        5,
        expect.objectContaining({ name: "docs2" }),
      ),
    );
  });

  it("eliminar etiqueta via chip delete", async () => {
    removeMock.mockResolvedValue({});
    listMock.mockResolvedValue([makeTag({ id: 7, name: "vieja" })]);
    const { container } = renderPage();
    await waitFor(() => screen.getByText("vieja"));
    const deleteIcon = container.querySelector(".MuiChip-deleteIcon");
    expect(deleteIcon).toBeTruthy();
    fireEvent.click(deleteIcon!);
    // ConfirmDialog: el delete ahora requiere confirmación
    const confirmBtn = await screen.findByRole("button", { name: /confirmar/i });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(removeMock).toHaveBeenCalledWith(7));
  });
});
