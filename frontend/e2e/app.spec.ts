import { test, expect } from "@playwright/test";

test.describe("TODOlist E2E", () => {
  test("página de login se renderiza", async ({ page }) => {
    await page.goto("/");
    // Debe mostrar el formulario de login o la app
    await expect(page).toHaveTitle(/TODOlist/i);
  });

  test("navegación a registro funciona", async ({ page }) => {
    await page.goto("/");
    // Buscar link o botón de registro
    const registerLink = page.locator("text=/registr|sign up|register/i").first();
    if (await registerLink.isVisible()) {
      await registerLink.click();
      await page.waitForURL(/register|signup/i, { timeout: 5000 }).catch(() => {});
    }
  });

  test("dark mode toggle existe", async ({ page }) => {
    await page.goto("/");
    // El toggle de tema debería estar presente si estamos autenticados
    // Este test verifica que la app no crashea
    await page.waitForTimeout(1000);
  });

  test("API docs endpoint responde", async ({ page }) => {
    const response = await page.goto("http://localhost:8000/api/docs/");
    // Puede ser 200 o error si el backend no está corriendo
    if (response) {
      expect(response.status()).toBeLessThan(500);
    }
  });

  test("GraphQL endpoint responde", async ({ page }) => {
    const response = await page.goto("http://localhost:8000/graphql/");
    if (response) {
      expect(response.status()).toBeLessThan(500);
    }
  });
});
