/**
 * Real E2E integration tests for Navigation — NO MOCKS.
 *
 * Prerequisites:
 *   - API running on localhost:8000
 *   - GUI running on localhost:3000
 *
 * Run:
 *   cd apps/gui && E2E_INTEGRATION=1 CI= npx playwright test navigation --reporter=list
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const NAV_ITEMS = [
  { label: "Dashboard", url: "/", heading: "Dashboard" },
  { label: "Workflows", url: "/workflows", heading: "Workflows" },
  { label: "Souls", url: "/souls", heading: "Souls" },
  { label: "Tasks", url: "/tasks", heading: "Tasks" },
  { label: "Steps", url: "/steps", heading: "Steps" },
  { label: "Runs", url: "/runs", heading: "Runs" },
  { label: "Settings", url: "/settings", heading: "Settings" },
];

test.describe("Navigation - Real E2E", () => {
  test("sidebar shows correct nav items: Dashboard, Workflows, Souls, Tasks, Steps, Runs, Settings", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Main nav: Dashboard, Workflows, Souls, Tasks, Steps, Runs
    const mainNavLabels = ["Dashboard", "Workflows", "Souls", "Tasks", "Steps", "Runs"];
    for (const label of mainNavLabels) {
      await expect(
        page.getByRole("navigation").getByRole("link", { name: label })
      ).toBeVisible({ timeout: 10000 });
    }

    // Settings is in bottom nav, separate from main <nav>
    await expect(
      page.getByRole("link", { name: "Settings" })
    ).toBeVisible({ timeout: 5000 });
  });

  test("active nav item is highlighted with aria-current=page", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const dashboardLink = page.locator("aside").getByRole("link", { name: "Dashboard" });
    await expect(dashboardLink).toHaveAttribute("aria-current", "page");
  });

  test("clicking each nav item navigates to correct URL", async ({ page }) => {
    test.setTimeout(60000);

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const sidebar = page.locator("aside").first();

    for (const { label, url } of NAV_ITEMS) {
      const link = sidebar.getByRole("link", { name: label });
      await link.scrollIntoViewIfNeeded();
      await link.click({ timeout: 10000 });

      const pathRegex = url === "/" ? /localhost:3000\/?(\?|$)/ : new RegExp(`.*${url.replace(/\//g, "\\/")}(\\/)?(\\?.*)?$`);
      await expect(page).toHaveURL(pathRegex, { timeout: 10000 });
    }
  });

  test("page titles/headings match: Souls → Souls, Tasks → Tasks, etc.", async ({
    page,
  }) => {
    for (const { url, heading } of NAV_ITEMS) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");

      await expect(
        page.getByRole("heading", { name: heading }).first()
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test("Dashboard link navigates to / and shows Dashboard heading", async ({
    page,
  }) => {
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    await page.getByRole("link", { name: "Dashboard" }).first().click();

    await expect(page).toHaveURL(/\//);
    await expect(
      page.getByRole("heading", { name: "Dashboard" }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test("Workflows link navigates to /workflows", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Workflows" }).first().click();

    await expect(page).toHaveURL(/\/workflows/);
  });
});
