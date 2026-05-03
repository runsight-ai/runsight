import { test, expect, type Page } from "@playwright/test";

import {
  cleanupReadonlySurfaceFixture,
  fetchReadonlyRunList,
  readonlySurfaceFixture,
  setupReadonlySurfaceFixture,
} from "./helpers/readonly-surface-fixture";

test.describe.configure({ mode: "serial" });

const forkedWorkflowIds = new Set<string>();
const editRoutePattern = new RegExp("/workflows/[^/]+/edit$");

async function expectSurfaceShell(page: Page) {
  await expect(page.getByTestId("surface-topbar")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-center")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-bottom-panel")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-status-bar")).toBeVisible({ timeout: 15000 });
}

async function expectEditControls(page: Page) {
  await expect(page.getByTestId("workflow-save-button")).toBeVisible({ timeout: 15000 });
  await expect(
    page.locator('[data-testid="workflow-run-button"], [data-testid="workflow-add-api-key-button"]'),
  ).toBeVisible({ timeout: 15000 });
}

function workflowIdFromUrl(url: string) {
  const match = url.match(/\/workflows\/([^/]+)\/edit$/);
  if (!match) {
    throw new Error(`Could not parse workflow id from ${url}`);
  }
  return decodeURIComponent(match[1]);
}

test.beforeAll(async () => {
  await setupReadonlySurfaceFixture();
});

test.afterAll(async ({ request }) => {
  await cleanupReadonlySurfaceFixture(request, forkedWorkflowIds);
});

test.describe("Readonly surface browser smoke", () => {
  test("runs row opens the readonly surface and forks into the edit route", async ({ page }) => {
    const runList = await fetchReadonlyRunList();
    const seededRun = runList.items.find((item) => item.id === readonlySurfaceFixture.runId);
    expect(seededRun, `Expected ${readonlySurfaceFixture.runId} in /api/runs`).toBeDefined();

    await page.goto("/runs");
    await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible({ timeout: 15000 });

    const row = page
      .locator("tbody tr")
      .filter({ hasText: readonlySurfaceFixture.workflowName })
      .filter({ hasText: `#${seededRun?.run_number ?? ""}` });

    await expect(row).toHaveCount(1);
    await row.click();

    await expect(page).toHaveURL(new RegExp(`/runs/${readonlySurfaceFixture.runId}$`), {
      timeout: 15000,
    });
    await expectSurfaceShell(page);
    await expect(page.getByText("Read-only review")).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: "Fork" }).click();
    await expect(page).toHaveURL(editRoutePattern, { timeout: 15000 });

    const forkedWorkflowId = workflowIdFromUrl(page.url());
    forkedWorkflowIds.add(forkedWorkflowId);

    await expectSurfaceShell(page);
    await expectEditControls(page);
  });

  test("missing readonly run shows a not found state", async ({ page }) => {
    await page.goto("/runs/nonexistent");

    await expect(page.getByText("Run not found")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("link", { name: "Back to runs" })).toBeVisible({
      timeout: 15000,
    });
  });
});
