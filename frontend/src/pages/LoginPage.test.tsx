import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "./LoginPage";

const mockLogin = vi.fn();
const mockNavigate = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ login: mockLogin }),
}));
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock("../api/resources", () => ({
  githubApi: {
    getProviders: vi.fn().mockResolvedValue({ github: true, google: false }),
    getOAuthUrl: vi.fn(),
  },
}));
vi.mock("../notify", () => ({
  notify: { success: vi.fn(), error: vi.fn() },
}));

import { githubApi } from "../api/resources";
import { notify } from "../notify";

function renderPage() {
  return render(createElement(MemoryRouter, null, createElement(LoginPage)));
}

function fillAndSubmit(email = "a@b.com", pw = "pw12345") {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText("Contraseña"), {
    target: { value: pw },
  });
  fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (githubApi.getProviders as ReturnType<typeof vi.fn>).mockResolvedValue({
      github: true,
      google: false,
    });
  });

  it("renderiza el formulario de login", () => {
    renderPage();
    expect(screen.getByLabelText(/email/i)).toBeTruthy();
    expect(screen.getByLabelText("Contraseña")).toBeTruthy();
    expect(screen.getByRole("button", { name: /iniciar sesión/i })).toBeTruthy();
  });

  it("muestra botón de GitHub cuando el provider está activo", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /github/i })).toBeTruthy(),
    );
  });

  it("oculta OAuth si no hay providers", async () => {
    (githubApi.getProviders as ReturnType<typeof vi.fn>).mockResolvedValue({
      github: false,
      google: false,
    });
    renderPage();
    await waitFor(() => expect(githubApi.getProviders).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /github/i })).toBeNull();
  });

  it("valida email inválido y no llama a login", async () => {
    renderPage();
    fillAndSubmit("no-es-email");
    await waitFor(() => expect(screen.getByText(/email no válido/i)).toBeTruthy());
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("login correcto navega al destino", async () => {
    mockLogin.mockResolvedValue({});
    renderPage();
    fillAndSubmit();
    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith("a@b.com", "pw12345", undefined),
    );
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/app"));
  });

  it("requires_2fa muestra el campo de código TOTP", async () => {
    mockLogin.mockRejectedValue({
      response: { data: { requires_2fa: true } },
    });
    renderPage();
    fillAndSubmit();
    await waitFor(() =>
      expect(screen.getByLabelText(/código de verificación/i)).toBeTruthy(),
    );
  });

  it("flujo 2FA completo: reintenta con el código", async () => {
    mockLogin
      .mockRejectedValueOnce({ response: { data: { requires_2fa: true } } })
      .mockResolvedValueOnce({});
    renderPage();
    fillAndSubmit();
    await waitFor(() => screen.getByLabelText(/código de verificación/i));
    fireEvent.change(screen.getByLabelText(/código de verificación/i), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));
    await waitFor(() =>
      expect(mockLogin).toHaveBeenLastCalledWith("a@b.com", "pw12345", "123456"),
    );
  });

  it("error de credenciales muestra mensaje", async () => {
    mockLogin.mockRejectedValue({
      response: { data: { detail: "Credenciales inválidas" } },
    });
    renderPage();
    fillAndSubmit();
    await waitFor(() => expect(screen.getByText(/credenciales inválidas/i)).toBeTruthy());
    expect(notify.error).toHaveBeenCalled();
  });

  it("error sin detail muestra mensaje genérico", async () => {
    mockLogin.mockRejectedValue({ response: { data: {} } });
    renderPage();
    fillAndSubmit();
    await waitFor(() =>
      expect(screen.getByText(/no se pudo iniciar sesión/i)).toBeTruthy(),
    );
  });

  it("toggle de mostrar contraseña cambia el tipo del input", () => {
    renderPage();
    const pwInput = screen.getByLabelText("Contraseña") as HTMLInputElement;
    expect(pwInput.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: /mostrar contraseña/i }));
    expect(pwInput.type).toBe("text");
  });
});
