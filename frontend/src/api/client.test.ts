import { describe, it, expect, beforeEach } from "vitest";
import { api } from "./client";

// Acceso al handler registrado por el interceptor (internal de axios,
// estable: InterceptorsManager.handlers)
function requestHandler() {
  // axios-retry registra su interceptor antes que el de CSRF:
  // el nuestro es el ÚLTIMO handler registrado.
  const handlers = (api.interceptors.request as any).handlers.filter(
    (x: unknown) => x && typeof x === "object",
  );
  const h = handlers[handlers.length - 1];
  return (h as any).fulfilled;
}

function setCsrfCookie(value: string | null) {
  Object.defineProperty(document, "cookie", {
    writable: true,
    configurable: true,
    value: value ? `todolist_csrf=${value}` : "",
  });
}

describe("api client interceptors", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("usa withCredentials para las cookies httpOnly", () => {
    expect(api.defaults.withCredentials).toBe(true);
  });

  it("inyecta X-CSRFToken en métodos no seguros cuando hay cookie", () => {
    setCsrfCookie("csrf-token-123");
    const config = { method: "post", headers: {} as Record<string, string> };
    const result = requestHandler()(config);
    expect(result.headers["X-CSRFToken"]).toBe("csrf-token-123");
  });

  it("NO inyecta X-CSRFToken en métodos seguros", () => {
    setCsrfCookie("csrf-token-123");
    for (const method of ["get", "head", "options"]) {
      const config = { method, headers: {} as Record<string, string> };
      const result = requestHandler()(config);
      expect(result.headers["X-CSRFToken"]).toBeUndefined();
    }
  });

  it("sin cookie CSRF no envía el header aunque sea POST", () => {
    setCsrfCookie(null);
    const config = { method: "delete", headers: {} as Record<string, string> };
    const result = requestHandler()(config);
    expect(result.headers["X-CSRFToken"]).toBeUndefined();
  });

  it("envía Bearer si hay token legacy en tokenStorage", async () => {
    setCsrfCookie(null);
    const { tokenStorage } = await import("./client");
    tokenStorage.set("legacy-access", "legacy-refresh");
    const config = { method: "get", headers: {} as Record<string, string> };
    const result = requestHandler()(config);
    expect(result.headers.Authorization).toBe("Bearer legacy-access");
  });
});
