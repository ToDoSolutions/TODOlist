import { expect, request, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://127.0.0.1:8000/api";
const PASSWORD = "E2e-password-1234!";

export interface TestUser {
  email: string;
  password: string;
  /** request context autenticado con Bearer (sembrar datos sin UI) */
  api: APIRequestContext;
}

/** true si el backend responde (cualquier status < 500 vale). */
export async function backendUp(): Promise<boolean> {
  try {
    const ctx = await request.newContext();
    const r = await ctx.get(`${API}/auth/me/`, { timeout: 4000 });
    await ctx.dispose();
    return r.status() < 500;
  } catch {
    return false;
  }
}

/** Devuelve un contexto API autenticado con Bearer para email/password. */
export async function apiContext(email: string, password: string): Promise<APIRequestContext> {
  const anon = await request.newContext();
  const lr = await anon.post(`${API}/auth/login/`, { data: { email, password } });
  const body = await lr.json().catch(() => ({}));
  await anon.dispose();
  if (!lr.ok() || !body.access) {
    throw new Error(`login API falló (${lr.status()}) para ${email}`);
  }
  return request.newContext({
    baseURL: `${API}/`,
    extraHTTPHeaders: { Authorization: `Bearer ${body.access}` },
  });
}

/** Usuario ya existente (env vars) → contexto API sin pasar por /register. */
export async function existingUser(email: string, password: string): Promise<TestUser> {
  return { email, password, api: await apiContext(email, password) };
}

/**
 * Registra un usuario nuevo y devuelve un request context con Bearer.
 * OJO: el endpoint está limitado a 5 registros/hora por IP — reusar el
 * usuario compartido entre tests en vez de registrar por test.
 * Devuelve null si el servidor responde 429 (cuota agotada).
 */
export async function registerUser(): Promise<TestUser | null> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e5)}@test.dev`;
  const anon = await request.newContext();
  const r = await anon.post(`${API}/auth/register/`, {
    data: {
      email,
      username: email.split("@")[0].replace(/[^a-zA-Z0-9]/g, ""),
      password: PASSWORD,
      password2: PASSWORD,
    },
  });
  if (r.status() === 429) {
    await anon.dispose();
    return null;
  }
  if (r.status() !== 201) {
    const body = await r.text().catch(() => "");
    await anon.dispose();
    throw new Error(`registro falló (${r.status()}): ${body.slice(0, 300)}`);
  }
  await anon.dispose();
  return { email, password: PASSWORD, api: await apiContext(email, PASSWORD) };
}

/** Login por la UI real (formulario de /login). */
export async function loginUi(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: /iniciar sesión/i }).click();
  await page.waitForURL(/\/app/, { timeout: 15000 });
}

/** Deja al usuario sin proyectos (para que el onboarding se active). */
export async function deleteAllProjects(user: TestUser) {
  const r = await user.api.get("projects/");
  const body = await r.json();
  const list = Array.isArray(body) ? body : body.results ?? [];
  for (const p of list) {
    await user.api.delete(`projects/${p.id}/`);
  }
}

/** Si el usuario cae en onboarding (0 proyectos), lo omite.
 *  El redirect es async (useEffect + react-query), así que esperamos a que
 *  el botón «Omitir introducción» aparezca en vez de mirar la URL al instante. */
export async function skipOnboarding(page: Page) {
  const omitir = page.getByRole("button", { name: /omitir introducción/i });
  const appeared = await omitir
    .waitFor({ state: "visible", timeout: 8000 })
    .then(() => true)
    .catch(() => false);
  if (appeared) {
    await omitir.click();
    await page.waitForURL(/\/app$/, { timeout: 10000 });
  }
}
