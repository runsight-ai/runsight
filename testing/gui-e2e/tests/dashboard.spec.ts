/**
 * Real E2E integration tests for Dashboard — NO MOCKS.
 *
 * Prerequisites:
 *   - API running on localhost:8000
 *   - GUI running on localhost:3000 (proxies /api → :8000)
 *
 * Run:
 *   pnpm -C testing/gui-e2e test -- dashboard --reporter=list
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

test.describe("Dashboard - Real E2E", () => {
  const testWorkflowName = `e2e-dash-workflow-${Date.now()}`;
  let createdWorkflowId: string | null = null;

  test.afterAll(async () => {
    if (createdWorkflowId) {
      await apiDelete(`/workflows/${createdWorkflowId}`);
    }
  });

  test("dashboard shows heading Dashboard when workflows exist", async ({
    page,
  }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total === 0, "Need at least one workflow to see populated dashboard");

    await page.goto("/");
    await expect(page).toHaveURL(/\//);

    // ShellLayout header bar shows page title (use first to avoid strict mode when multiple match)
    await expect(
      page.getByRole("heading", { name: "Dashboard" }).first()
    ).toBeVisible({ timeout: 15000 });
  });

  test("dashboard shows summary cards with real data from /api/dashboard", async ({
    page,
  }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total === 0, "Need workflows for populated dashboard");

    const dashboardData = await apiGet("/dashboard");
    expect(dashboardData).toHaveProperty("active_runs");
    expect(dashboardData).toHaveProperty("completed_runs");
    expect(dashboardData).toHaveProperty("total_cost_usd");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Summary cards: Active Runs, Completed, Total Cost, System Health
    await expect(
      page.getByText("Active Runs", { exact: true }).first()
    ).toBeVisible({ timeout: 15000 });
    await expect(
      page.getByText("Completed", { exact: true }).first()
    ).toBeVisible({ timeout: 5000 });
    await expect(
      page.getByText("Total Cost", { exact: true }).first()
    ).toBeVisible({ timeout: 5000 });
    await expect(
      page.getByText("System Health", { exact: true }).first()
    ).toBeVisible({ timeout: 5000 });

    // Values match API
    await expect(
      page.locator(`text=${String(dashboardData.active_runs)}`).first()
    ).toBeVisible({ timeout: 5000 });
    await expect(
      page.locator(`text=${String(dashboardData.completed_runs)}`).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test("dashboard shows Active Workflows section with real workflows from API", async ({
    page,
  }) => {
    const { items, total } = await apiGet("/workflows");
    test.skip(total === 0, "Need workflows for Active Workflows section");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("heading", { name: "Active Workflows", level: 2 })
    ).toBeVisible({ timeout: 15000 });

    // At least first workflow from API should appear
    await expect(
      page.getByText(items[0].name, { exact: true }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test("dashboard shows empty state Create your first workflow when no workflows", async ({
    page,
  }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total > 0, "Empty state only visible when no workflows exist");

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("heading", { name: "Create your first workflow", level: 2 })
    ).toBeVisible({ timeout: 15000 });
  });

  test("New Workflow button on dashboard opens modal", async ({ page }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total === 0, "Need workflows to see dashboard with New Workflow button");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /New Workflow/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal.getByText("Create New Workflow")).toBeVisible();
  });

  test("New Workflow modal has name input, description input, Cancel/Create buttons", async ({
    page,
  }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total === 0, "Need workflows for dashboard");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /New Workflow/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await expect(
      modal.getByPlaceholder(/Enter workflow name/i)
    ).toBeVisible();
    await expect(
      modal.getByPlaceholder(/Describe what this workflow does/i)
    ).toBeVisible();
    await expect(modal.getByRole("button", { name: /Cancel/i })).toBeVisible();
    await expect(modal.getByRole("button", { name: /Create/i })).toBeVisible();
  });

  test("Create button disabled when name empty, enabled when filled", async ({
    page,
  }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total === 0, "Need workflows for dashboard");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /New Workflow/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const createBtn = modal.getByRole("button", { name: /^Create$/ });
    await expect(createBtn).toBeDisabled();

    await modal.getByPlaceholder(/Enter workflow name/i).fill("x");
    await expect(createBtn).toBeEnabled();
  });

  test("creating a workflow navigates to canvas", async ({ page }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total === 0, "Need workflows for dashboard modal access");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /New Workflow/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByPlaceholder(/Enter workflow name/i).fill(testWorkflowName);
    await modal.getByRole("button", { name: /Create/i }).click();

    await expect(page).toHaveURL(/\/workflows\/[^/]+/, { timeout: 15000 });

    const data = await apiGet("/workflows");
    const created = data.items.find((w: { name: string }) => w.name === testWorkflowName);
    expect(created).toBeDefined();
    createdWorkflowId = created.id;
  });

  test("Cancel dismisses New Workflow modal without side effects", async ({
    page,
  }) => {
    const { total } = await apiGet("/workflows");
    test.skip(total === 0, "Need workflows for dashboard");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /New Workflow/i }).first().click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    await modal.getByRole("button", { name: /Cancel/i }).click();

    await expect(modal).not.toBeVisible({ timeout: 5000 });
    await expect(page).toHaveURL(/\//);
  });
});
