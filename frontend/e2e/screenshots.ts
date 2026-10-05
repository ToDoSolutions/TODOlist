import { chromium } from "@playwright/test";
import { mkdirSync } from "fs";

// Barrido completo de vistas â€” requiere backend :8000 (seed_demo) y Vite :5173.
// npx tsx e2e/screenshots.ts
const BASE = "http://localhost:5174";
const OUT = "../docs/assets/screenshots";

const PAGES: [string, string][] = [
  // Vistas principales
  ["/app", "app-home"],
  ["/app/my-work", "my-work"],
  ["/app/attention", "attention"],
  ["/app/inbox", "inbox"],
  ["/app/tasks", "tasks-list"],
  ["/app/tasks?view=kanban", "kanban"],
  ["/app/tasks?view=calendar", "calendar"],
  ["/app/tasks?view=table", "tasks-table"],
  ["/app/tasks/31", "task-detail"],
  ["/app/favorites", "favorites"],
  ["/app/completed", "completed"],
  ["/app/focus", "focus"],
  ["/app/search", "search"],
  ["/app/notifications", "notifications"],
  // PlanificaciÃ³n / proyectos
  ["/app/projects", "projects"],
  ["/app/sprints", "sprints"],
  ["/app/epics", "epics"],
  ["/app/backlog", "backlog"],
  ["/app/gantt", "gantt"],
  ["/app/roadmap", "roadmap"],
  ["/app/burndown", "burndown"],
  ["/app/capacity", "capacity"],
  ["/app/dashboard", "dashboard"],
  ["/app/dashboards", "dashboards"],
  ["/app/okrs", "okrs"],
  ["/app/portfolios", "portfolios"],
  ["/app/risks", "risks"],
  ["/app/meetings", "meetings"],
  // ColaboraciÃ³n
  ["/app/teams", "teams"],
  ["/app/wiki", "wiki"],
  ["/app/whiteboards", "whiteboards"],
  ["/app/decisions", "decisions"],
  ["/app/dependencies", "dependencies"],
  ["/app/activity", "activity"],
  ["/app/intake-forms", "intake-forms"],
  ["/app/shares", "shares"],
  // ConfiguraciÃ³n / admin
  ["/app/account", "account"],
  ["/app/profile", "profile"],
  ["/app/tags", "tags"],
  ["/app/templates", "templates"],
  ["/app/custom-fields", "custom-fields"],
  ["/app/automations", "automations"],
  ["/app/recurrence-rules", "recurrence-rules"],
  ["/app/workflows", "workflows"],
  ["/app/time-entries", "time-entries"],
  ["/app/productivity", "productivity"],
  ["/app/trash", "trash"],
  ["/app/import-export", "import-export"],
  ["/app/ai-assistant", "ai-assistant"],
  ["/app/integrations", "integrations"],
  ["/app/github", "github"],
  ["/app/calendars", "calendars"],
  ["/app/webhooks", "webhooks"],
  ["/app/api-keys", "api-keys"],
  ["/app/offline-sync", "offline-sync"],
  ["/app/encryption", "encryption"],
  ["/app/security", "security"],
  ["/app/audit", "audit"],
  ["/app/feature-flags", "feature-flags"],
  ["/app/admin", "admin"],
  ["/app/admin/roles", "admin-roles"],
  ["/app/admin/organizations", "admin-organizations"],
  ["/app/admin/sla", "admin-sla"],
  ["/app/admin/jobs", "admin-jobs"],
  ["/app/help", "help"],
  ["/app/changelog", "changelog"],
  // Vistas dinámicas con ids sembrados
  ["/app/project/1", "project"],
  ["/app/project/1/tasks", "project-tasks"],
  ["/app/project/1/settings", "project-settings"],
  ["/app/onboarding", "onboarding"],
  // Estados de error / sistema
  ["/app/403", "forbidden"],
  ["/app/suspended", "suspended"],
  ["/app/ruta-inexistente", "not-found"],
];

// Públicas adicionales (sin auth)
const PUBLIC_PAGES: [string, string][] = [
  ["/forgot-password", "forgot-password"],
  ["/session-expired", "session-expired"],
  ["/reset-password", "reset-password"],
  ["/verify-email", "verify-email"],
];

const API = "http://127.0.0.1:8100/api";

// Subconjunto opcional: SHOTS=decisions,intake-forms npx tsx e2e/screenshots.ts
const ONLY = (process.env.SHOTS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const want = (n: string) => !ONLY.length || ONLY.includes(n);

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // Pantallas pÃºblicas
  if (want("login")) {
    await page.goto(`${BASE}/login`);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/login.png` });
  }
  if (want("register")) {
    await page.goto(`${BASE}/register`);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/register.png` });
  }
  for (const [p, n] of PUBLIC_PAGES) {
    if (!want(n)) continue;
    await page.goto(`${BASE}${p}`);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/${n}.png` });
    console.log("ok", n);
  }

  // Login por API (evita el throttle del endpoint /login en barridos largos)
  let access = "";
  async function login() {
    const r = await ctx.request.post(`${API}/auth/login/`, {
      data: { email: "demo@todolist.com", password: "demo12345" },
    });
    if (!r.ok()) throw new Error(`login API ${r.status()}`);
    const tokens = await r.json();
    access = tokens.access;
    await page.goto(`${BASE}/login`);
    await page.evaluate(([a, rf]) => {
      localStorage.setItem("todolist.access", a);
      localStorage.setItem("todolist.refresh", rf);
    }, [tokens.access, tokens.refresh]);
    await page.goto(`${BASE}/app`);
    const omitir = page.getByRole("button", { name: /omitir introducción/i });
    if (await omitir.isVisible({ timeout: 3000 }).catch(() => false)) await omitir.click();
  }
  await login();

  const sidebarReady = () =>
    page.getByText("Mi trabajo", { exact: true }).first()
      .waitFor({ state: "visible", timeout: 8000 })
      .then(() => true).catch(() => false);

  // Vistas que requieren ids/tokens resueltos por API
  const auth = { headers: { Authorization: `Bearer ${access}` } };
  const dynamic: [string, string, boolean][] = []; // [path, name, needsSidebar]
  try {
    const inv = await ctx.request.get(`${API}/invitations/`, auth);
    const invList = await inv.json();
    const invId = (Array.isArray(invList) ? invList : invList.results)?.[0]?.id;
    if (invId) dynamic.push([`/app/invitations/${invId}`, "invitation", true]);
    const share = await ctx.request.get(`${API}/share-links/`, auth);
    const shareList = await share.json();
    const shareToken = (Array.isArray(shareList)
      ? shareList
      : shareList.results)?.[0]?.token;
    if (shareToken) dynamic.push([`/share/${shareToken}`, "share-public", false]);
    const intake = await ctx.request.get(`${API}/intake-forms/`, auth);
    const intakeList = await intake.json();
    const intakeToken = (Array.isArray(intakeList)
      ? intakeList
      : intakeList.results)?.[0]?.public_token;
    if (intakeToken)
      dynamic.push([`/intake/${intakeToken}`, "intake-public", false]);
  } catch (e) {
    console.log("WARN dinámicas:", String(e).slice(0, 120));
  }

  for (const [path, name, needsSidebar] of [
    ...PAGES.map(([p, n]) => [p, n, true] as [string, string, boolean]),
    ...dynamic,
  ]) {
    if (!want(name)) continue;
    try {
      let ok = false;
      for (let attempt = 0; attempt < 2 && !ok; attempt++) {
        await page.goto(`${BASE}${path}`, { timeout: 20000 });
        await page.waitForTimeout(2500); // spinner + query settle
        if (page.url().includes("/login") || (needsSidebar && !(await sidebarReady()))) {
          console.log("re-login en", name);
          await login();
          continue;
        }
        ok = true;
      }
      await page.screenshot({ path: `${OUT}/${name}.png` });
      console.log(ok ? "ok" : "SHOOT-LOGIN", name);
    } catch (e) {
      console.log("FAIL", name, String(e).slice(0, 120));
    }
  }

  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
