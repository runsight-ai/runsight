/**
 * Real E2E smoke tests — NO MOCKS.
 *
 * Prerequisites:
 *   - API running on localhost:8000 (uvicorn runsight_api.main:app)
 *   - GUI running on localhost:3000 (npm run dev, proxies /api → :8000)
 *
 * Run:
 *   pnpm -C testing/gui-e2e test -- --reporter=list
 *
 * Pattern for sub-agents:
 *   1. NEVER use page.route() — all requests hit the real API
 *   2. Use real assertions: after creating something, verify it appears via the API
 *   3. Clean up after yourself: delete anything you created in afterEach/afterAll
 *   4. Tests run sequentially (fullyParallel: false) to avoid race conditions
 *   5. Use generous timeouts — real API calls take time
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

async function apiDelete(path: string) {
  return fetch(`${API}${path}`, { method: "DELETE" });
}

test.describe("Smoke: Dashboard loads with real data", () => {
  test("dashboard renders with live API data", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\//);

    const dashboard = page.getByRole("main").getByRole("heading", { name: "Dashboard" });
    const emptyState = page.getByText("Create your first workflow");
    await expect(dashboard.or(emptyState)).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Smoke: Souls CRUD", () => {
  const testSoulName = `e2e-test-soul-${Date.now()}`;
  let createdSoulId: string | null = null;

  test.beforeAll(async () => {
    const res = await fetch(`${API}/souls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: testSoulName, system_prompt: "E2E test soul — safe to delete" }),
    });
    const data = await res.json();
    createdSoulId = data.id ?? null;
  });

  test.afterAll(async () => {
    if (createdSoulId) {
      await apiDelete(`/souls/${createdSoulId}`);
    }
  });

  test("souls page lists real souls from API", async ({ page }) => {
    await page.goto("/souls");

    const data = await apiGet("/souls");
    expect(data.items.length).toBeGreaterThan(0);

    await expect(
      page.getByText(data.items[0].name, { exact: true }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test("create soul via modal → appears in list and API", async ({ page }) => {
    const createName = `${testSoulName}-ui`;
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const beforeData = await apiGet("/souls");
    const countBefore = beforeData.total;

    await page.getByRole("button", { name: /New Soul/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter soul name/i).fill(createName);
    await modal
      .getByPlaceholder(/Enter the system prompt/i)
      .fill("E2E test soul — safe to delete");

    await modal.getByRole("button", { name: /Create/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 10000 });

    await expect(page.getByText(createName)).toBeVisible({ timeout: 10000 });

    const afterData = await apiGet("/souls");
    const created = afterData.items.find(
      (s: { name: string }) => s.name === createName
    );
    expect(created).toBeTruthy();
    expect(afterData.total).toBeGreaterThanOrEqual(countBefore + 1);

    // Clean up the UI-created soul
    if (created?.id) {
      await apiDelete(`/souls/${created.id}`);
    }
  });

  test("soul created via beforeAll persists after page reload", async ({ page }) => {
    await page.goto("/souls");
    await expect(page.getByText(testSoulName)).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Smoke: Workflow CRUD", () => {
  const testWorkflowName = `e2e-test-workflow-${Date.now()}`;
  let createdWorkflowId: string | null = null;

  test.afterAll(async () => {
    if (createdWorkflowId) {
      await apiDelete(`/workflows/${createdWorkflowId}`);
    }
  });

  test("workflows page lists real workflows", async ({ page }) => {
    await page.goto("/workflows");

    const data = await apiGet("/workflows");

    if (data.total > 0) {
      await expect(
        page.getByText(data.items[0].name, { exact: true }).first()
      ).toBeVisible({ timeout: 10000 });
    } else {
      await expect(
        page.getByText(/no workflows/i)
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test("create workflow via modal → navigates to canvas", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /New Workflow/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/workflow name/i).fill(testWorkflowName);

    await modal.getByRole("button", { name: /Create/i }).click();

    await expect(page).toHaveURL(/\/workflows\//, { timeout: 15000 });

    const data = await apiGet("/workflows");
    const created = data.items.find(
      (w: { name: string }) => w.name === testWorkflowName
    );
    expect(created).toBeDefined();
    createdWorkflowId = created.id;
  });
});
