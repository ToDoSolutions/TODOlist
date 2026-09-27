import { test, expect } from "@playwright/test";
import {
  backendUp, registerUser, existingUser, loginUi, skipOnboarding, deleteAllProjects, type TestUser,
} from "./helpers";

/**
 * Recorridos críticos e2e. Requieren el backend en http://127.0.0.1:8000
 * (el webServer de playwright solo levanta vite). Si el backend no responde,
 * se saltan — para ejecutarlos: `python manage.py runserver` + `npx playwright test`.
 *
 * Un solo usuario compartido para los tests 2-4: el registro está limitado
 * a 5/hora por IP (RegisterRateThrottle). Se puede fijar con env vars:
 *   E2E_EMAIL / E2E_PASSWORD   → usuario compartido (tests 2-4)
 *   E2E_FRESH_EMAIL / E2E_FRESH_PASSWORD → usuario sin proyectos (test 1)
 * Si no hay env vars, se registra por API (y se salta el test si hay 429).
 */

test.beforeEach(async () => {
  test.skip(!(await backendUp()), "backend no disponible en :8000");
});

test.describe("Recorridos críticos", () => {
  test.describe.configure({ mode: "serial" });

  let shared: TestUser;

  test.beforeAll(async () => {
    if (!(await backendUp())) return;
    if (process.env.E2E_EMAIL && process.env.E2E_PASSWORD) {
      shared = await existingUser(process.env.E2E_EMAIL, process.env.E2E_PASSWORD);
    } else {
      const u = await registerUser();
      if (u) shared = u;
    }
  });

  test("registro → onboarding → primer proyecto y tarea → Inicio", async ({ page }) => {
    // Usuario fresco: sin proyectos, para que el onboarding se active
    let fresh: TestUser | null = null;
    if (process.env.E2E_FRESH_EMAIL && process.env.E2E_FRESH_PASSWORD) {
      fresh = await existingUser(process.env.E2E_FRESH_EMAIL, process.env.E2E_FRESH_PASSWORD);
    } else {
      fresh = await registerUser();
    }
    test.skip(!fresh, "sin usuario fresco (throttle de registro agotado; usar E2E_FRESH_*)");
    await deleteAllProjects(fresh!); // el onboarding solo se dispara con 0 proyectos
    const { email, password } = fresh!;
    await loginUi(page, email, password);

    // Sin proyectos: debe redirigir al onboarding
    await page.waitForURL(/\/app\/onboarding/, { timeout: 10000 });
    await page.getByRole("button", { name: "Empezar" }).click();

    const main = page.locator("main");

    // Crear proyecto
    await main.getByLabel("Nombre del proyecto").fill("Proyecto E2E");
    await main.getByRole("button", { name: "Crear proyecto" }).click();

    // Crear primera tarea (esperar al paso de invitación: la transición es async)
    await main.getByLabel("Título de la tarea").fill("Tarea e2e onboarding");
    await main.getByRole("button", { name: "Crear tarea" }).click();
    await expect(main.getByRole("heading", { name: "Invita a tu equipo" })).toBeVisible();

    // Saltar invitación y terminar
    await main.getByRole("button", { name: "Saltar" }).click();
    await expect(main.getByRole("heading", { name: "Todo listo" })).toBeVisible();
    await main.getByRole("button", { name: "Ir a Inicio" }).click();

    await page.waitForURL(/\/app$/, { timeout: 10000 });
    await expect(page).toHaveTitle(/TODOlist|Inicio/i);
  });

  test("búsqueda global encuentra una tarea por título", async ({ page }) => {
    test.skip(!shared, "sin usuario compartido (throttle de registro; usar E2E_*)");
    const title = `tarea-e2e-${Date.now()}`;
    const r = await shared.api.post("tasks/", { data: { title } });
    expect(r.status()).toBeLessThan(400);

    await loginUi(page, shared.email, shared.password);
    await skipOnboarding(page);

    await page.goto(`/app/search?q=${encodeURIComponent(title)}`);
    await expect(page.getByText(title).first()).toBeVisible({ timeout: 15000 });
  });

  test("mi trabajo muestra la tarea asignada", async ({ page }) => {
    test.skip(!shared, "sin usuario compartido (throttle de registro; usar E2E_*)");
    const me = await (await shared.api.get("auth/me/")).json();
    const title = `mi-trabajo-e2e-${Date.now()}`;
    const r = await shared.api.post("tasks/", {
      data: { title, assignee: me.id, due_date: new Date().toISOString() },
    });
    expect(r.status()).toBeLessThan(400);

    await loginUi(page, shared.email, shared.password);
    await skipOnboarding(page);

    await page.goto("/app/my-work");
    await expect(page.getByText(title).first()).toBeVisible({ timeout: 15000 });
  });

  test("deep link a tarea abre el diálogo y logout vuelve a login", async ({ page }) => {
    test.skip(!shared, "sin usuario compartido (throttle de registro; usar E2E_*)");
    const title = `deeplink-e2e-${Date.now()}`;
    const r = await shared.api.post("tasks/", { data: { title } });
    const task = await r.json();

    await loginUi(page, shared.email, shared.password);
    await skipOnboarding(page);

    // Deep link: /app/tasks/:id debe abrir el TaskDialog directamente
    await page.goto(`/app/tasks/${task.id}`);
    await expect(
      page.getByRole("dialog").or(page.getByText(title)).first()
    ).toBeVisible({ timeout: 15000 });

    // Logout desde el menú de avatar
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Menú de usuario" }).click();
    await page.getByRole("menuitem", { name: /cerrar sesión|logout/i }).click();
    await page.waitForURL(/\/login/, { timeout: 15000 });
  });
});
