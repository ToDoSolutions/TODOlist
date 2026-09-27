import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import RegisterPage from "./RegisterPage";

const mockRegister = vi.fn();
const mockNavigate = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ register: mockRegister }),
}));
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock("../notify", () => ({
  notify: { success: vi.fn(), error: vi.fn() },
}));

import { notify } from "../notify";

function renderPage() {
  return render(createElement(MemoryRouter, null, createElement(RegisterPage)));
}

function fillForm(
  username = "alex",
  email = "a@b.com",
  pw = "password123",
  pw2 = "password123",
) {
  fireEvent.change(screen.getByLabelText(/usuario|username/i), {
    target: { value: username },
  });
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: email },
  });
  const pwFields = screen.getAllByLabelText(/contrase/i);
  fireEvent.change(pwFields[0]!, { target: { value: pw } });
  fireEvent.change(pwFields[1]!, { target: { value: pw2 } });
  fireEvent.click(screen.getByRole("button", { name: /crear cuenta|registr/i }));
}

describe("RegisterPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renderiza el formulario", () => {
    renderPage();
    expect(screen.getByLabelText(/email/i)).toBeTruthy();
    expect(screen.getAllByLabelText(/contrase/i).length).toBeGreaterThanOrEqual(2);
  });

  it("valida username corto", async () => {
    renderPage();
    fillForm("ab");
    await waitFor(() => expect(screen.getByText(/mínimo 3 caracteres/i)).toBeTruthy());
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("valida email inválido", async () => {
    renderPage();
    fillForm("alex", "malo");
    await waitFor(() => expect(screen.getByText(/email no válido/i)).toBeTruthy());
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("valida password corta", async () => {
    renderPage();
    fillForm("alex", "a@b.com", "short", "short");
    await waitFor(() =>
      expect(screen.getAllByText(/mínimo 8 caracteres/i).length).toBeGreaterThan(0),
    );
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("valida contraseñas distintas", async () => {
    renderPage();
    fillForm("alex", "a@b.com", "password123", "otra12345");
    await waitFor(() => expect(screen.getByText(/no coinciden/i)).toBeTruthy());
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("registro correcto navega a /app", async () => {
    mockRegister.mockResolvedValue({});
    renderPage();
    fillForm();
    await waitFor(() =>
      expect(mockRegister).toHaveBeenCalledWith("a@b.com", "alex", "password123"),
    );
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/app"));
  });

  it("muestra error de email duplicado del servidor", async () => {
    mockRegister.mockRejectedValue({
      response: { data: { email: ["Ya existe una cuenta con este email"] } },
    });
    renderPage();
    fillForm();
    await waitFor(() => expect(screen.getByText(/ya existe una cuenta/i)).toBeTruthy());
    expect(notify.error).toHaveBeenCalled();
  });

  it("muestra error de username duplicado", async () => {
    mockRegister.mockRejectedValue({
      response: { data: { username: ["Nombre en uso"] } },
    });
    renderPage();
    fillForm();
    await waitFor(() => expect(screen.getByText(/nombre en uso/i)).toBeTruthy());
  });

  it("error genérico sin campos específicos", async () => {
    mockRegister.mockRejectedValue({ response: { data: {} } });
    renderPage();
    fillForm();
    await waitFor(() => expect(screen.getByText(/no se pudo registrar/i)).toBeTruthy());
  });
});
