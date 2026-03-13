/**
 * Real E2E integration tests for Runs list and Run detail — NO MOCKS.
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

test.describe("Runs list and detail", () => {
  test("Runs page shows Active/History tab bar", async ({ page }) => {
    await page.goto("/runs");
    await expect(page.getByRole("tab", { name: /Active/i })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByRole("tab", { name: /History/i })).toBeVisible({
      timeout: 5000,
    });
  });

  test("Active tab is selected by default (aria-selected=true)", async ({
    page,
  }) => {
    await page.goto("/runs");
    const activeTab = page.getByRole("tab", { name: /Active/i });
    await expect(activeTab).toBeVisible({ timeout: 10000 });
    await expect(activeTab).toHaveAttribute("aria-selected", "true");
  });

  test("If runs exist: table shows Workflow, Status, Duration, Cost columns", async ({
    page,
  }) => {
    const data = await apiGet("/runs?status=active");
    const hasRuns = data.items?.length > 0;

    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    if (hasRuns) {
      await expect(
        page.getByRole("columnheader", { name: /Workflow/i })
      ).toBeVisible({ timeout: 10000 });
      await expect(
        page.getByRole("columnheader", { name: /Status/i })
      ).toBeVisible();
      await expect(
        page.getByRole("columnheader", { name: /Duration/i })
      ).toBeVisible();
      await expect(page.getByRole("columnheader", { name: /Cost/i })).toBeVisible();
    } else {
      await expect(
        page.getByText(/No active runs/i, { exact: false })
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test("Click History tab → URL changes to include tab=history, History tab selected", async ({
    page,
  }) => {
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    await page.getByRole("tab", { name: /History/i }).click();

    await expect(page).toHaveURL(/tab=history/);
    await expect(page.getByRole("tab", { name: /History/i })).toHaveAttribute(
      "aria-selected",
      "true"
    );
  });

  test("Switching back to Active tab works", async ({ page }) => {
    await page.goto("/runs?tab=history");
    await page.waitForLoadState("networkidle");

    await page.getByRole("tab", { name: /Active/i }).click();

    await expect(page).toHaveURL(/\/runs/);
    await expect(page.getByRole("tab", { name: /Active/i })).toHaveAttribute(
      "aria-selected",
      "true"
    );
  });

  test("Sidebar shows Runs as active nav (aria-current=page)", async ({
    page,
  }) => {
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    const runsLink = page.getByRole("link", { name: /Runs/i });
    await expect(runsLink).toBeVisible({ timeout: 10000 });
    await expect(runsLink).toHaveAttribute("aria-current", "page");
  });

  test("If real run exists: clicking a run row navigates to /runs/:id", async ({
    page,
  }) => {
    const data = await apiGet("/runs?status=active");
    const runs = data.items ?? [];
    // Try history if no active runs
    const historyData =
      runs.length === 0 ? await apiGet("/runs?status=completed,failed") : null;
    const allRuns = runs.length > 0 ? runs : historyData?.items ?? [];
    const firstRun = allRuns[0];

    test.skip(!firstRun, "No runs in API to test navigation");

    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    // If on Active tab with no runs, switch to History
    if (runs.length === 0 && historyData?.items?.length) {
      await page.getByRole("tab", { name: /History/i }).click();
      await page.waitForLoadState("networkidle");
    }

    await page.getByText(firstRun.workflow_name, { exact: true }).first().click();

    await expect(page).toHaveURL(new RegExp(`/runs/${firstRun.id}`), {
      timeout: 10000,
    });
  });

  test("Run detail page: shows run name/id, cost badge, node canvas", async ({
    page,
  }) => {
    const data = await apiGet("/runs?status=completed,failed");
    const runs = data.items ?? [];
    const firstRun = runs[0];

    test.skip(!firstRun, "No completed/failed runs in API");

    await page.goto(`/runs/${firstRun.id}`);
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByText(firstRun.workflow_name, { exact: false })
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/\$[\d.]+/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("bottom-panel")).toBeVisible({ timeout: 5000 });
  });

  test("Empty active runs shows appropriate message", async ({ page }) => {
    const data = await apiGet("/runs?status=active");
    const hasActiveRuns = data.items?.length > 0;

    await page.goto("/runs");
    await page.waitForLoadState("networkidle");

    if (!hasActiveRuns) {
      await expect(
        page.getByText(/No active runs/i, { exact: false })
      ).toBeVisible({ timeout: 10000 });
      await expect(
        page.getByText(/There are no workflows currently running/i, {
          exact: false,
        })
      ).toBeVisible();
    }
  });
});
