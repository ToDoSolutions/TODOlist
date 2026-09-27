import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../api/auth", () => ({
  authApi: {
    me: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  },
}));
vi.mock("../api/client", () => ({
  tokenStorage: {
    set: vi.fn(),
    clear: vi.fn(),
    getRefresh: vi.fn().mockReturnValue(null),
  },
}));

import { authApi } from "../api/auth";
import { tokenStorage } from "../api/client";

function Probe() {
  const { user, loading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.email : "anon"}</span>
      <button onClick={() => login("a@b.com", "pw")}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => vi.clearAllMocks());

  it("bootstraps con me(): sesión cookie → user cargado", async () => {
    (authApi.me as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 1,
      email: "a@b.com",
    });
    render(createElement(AuthProvider, null, createElement(Probe)));
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("a@b.com"));
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });

  it("me() falla → limpia storage y queda anónimo", async () => {
    (authApi.me as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("401"));
    render(createElement(AuthProvider, null, createElement(Probe)));
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("user").textContent).toBe("anon");
    expect(tokenStorage.clear).toHaveBeenCalled();
  });

  it("login → authApi.login + me() refresca el user", async () => {
    (authApi.me as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce(new Error("401"))
      .mockResolvedValue({ id: 2, email: "new@b.com" });
    (authApi.login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access: "a",
      refresh: "r",
    });
    render(createElement(AuthProvider, null, createElement(Probe)));
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    screen.getByText("login").click();
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("new@b.com"));
    expect(authApi.login).toHaveBeenCalledWith("a@b.com", "pw", undefined);
  });

  it("logout limpia el user aunque falle la API", async () => {
    (authApi.me as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 1,
      email: "a@b.com",
    });
    (authApi.logout as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("network"));
    render(createElement(AuthProvider, null, createElement(Probe)));
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("a@b.com"));
    screen.getByText("logout").click();
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("anon"));
  });

  it("useAuth fuera del provider lanza error", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(createElement(Probe))).toThrow(/AuthProvider/);
    spy.mockRestore();
  });
});
