/**
 * Real E2E integration tests for Souls/Tasks/Steps search and empty states — NO MOCKS.
 * Prerequisites: API on localhost:8000, GUI on localhost:3000
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

test.describe("Souls page: search and empty states", () => {
  test("Souls page: search input exists", async ({ page }) => {
    const data = await apiGet("/souls");
    const hasSouls = (data.items?.length ?? 0) > 0;
    test.skip(!hasSouls, "No souls — search bar only shown when souls exist");

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test("Souls page: type in search → filters rows (use name of a real soul from API)", async ({
    page,
  }) => {
    const data = await apiGet("/souls");
    const souls = data.items ?? [];
    const realSoulName = souls[0]?.name;

    test.skip(!realSoulName, "No souls in API to test search");

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await searchInput.fill(realSoulName);

    await expect(
      page.getByRole("table").getByText(realSoulName, { exact: true }).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test("Souls page: search for nonexistent → shows empty state", async ({
    page,
  }) => {
    const data = await apiGet("/souls");
    const hasSouls = (data.items?.length ?? 0) > 0;
    test.skip(!hasSouls, "No souls — search bar only shown when souls exist");

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await searchInput.fill("xyznonexistent12345");

    await expect(
      page.getByText(/No souls match your search/i)
    ).toBeVisible({ timeout: 5000 });
    await expect(
      page.getByText(/No results found for/i)
    ).toBeVisible();
  });

  test("Souls page: clear search → all souls reappear", async ({ page }) => {
    const data = await apiGet("/souls");
    const souls = data.items ?? [];
    const realSoulName = souls[0]?.name;

    test.skip(!realSoulName, "No souls in API to test clear search");

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await searchInput.fill("xyznonexistent12345");
    await expect(page.getByText(/No souls match your search/i)).toBeVisible({
      timeout: 5000,
    });

    await page.getByRole("button", { name: /Clear search/i }).click();
    await expect(page.getByText(realSoulName, { exact: true }).first()).toBeVisible({ timeout: 5000 });
  });

  test("Souls page: shows empty state heading when no souls exist", async ({
    page,
  }) => {
    const data = await apiGet("/souls");
    const hasSouls = (data.items?.length ?? 0) > 0;

    test.skip(hasSouls, "Souls exist — cannot test empty state");

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByText(/No souls configured/i)
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Tasks page: search and empty states", () => {
  test("Tasks page: search input exists", async ({ page }) => {
    const data = await apiGet("/tasks");
    const hasTasks = (data.items?.length ?? 0) > 0;
    test.skip(!hasTasks, "No tasks — search bar only shown when tasks exist");

    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search tasks/i);
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test("Tasks page: search filters tasks by name", async ({ page }) => {
    const data = await apiGet("/tasks");
    const tasks = data.items ?? [];
    const realTaskName = tasks[0]?.name;

    test.skip(!realTaskName, "No tasks in API to test search");

    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search tasks/i);
    await searchInput.fill(realTaskName);

    await expect(page.getByText(realTaskName, { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test("Tasks page: search empty state", async ({ page }) => {
    const data = await apiGet("/tasks");
    const hasTasks = (data.items?.length ?? 0) > 0;
    test.skip(!hasTasks, "No tasks — search bar only shown when tasks exist");

    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search tasks/i);
    await searchInput.fill("xyznonexistent12345");

    await expect(
      page.getByText(/No tasks match your search/i)
    ).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Steps page: search and empty states", () => {
  test("Steps page: search input exists", async ({ page }) => {
    const data = await apiGet("/steps");
    const hasSteps = (data.items?.length ?? 0) > 0;
    test.skip(!hasSteps, "No steps — search bar only shown when steps exist");

    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search steps/i);
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test("Steps page: search filters steps by name", async ({ page }) => {
    const data = await apiGet("/steps");
    const steps = data.items ?? [];
    const realStepName = steps[0]?.name;

    test.skip(!realStepName, "No steps in API to test search");

    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search steps/i);
    await searchInput.fill(realStepName);

    await expect(page.getByText(realStepName, { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test("Steps page: search empty state", async ({ page }) => {
    const data = await apiGet("/steps");
    const hasSteps = (data.items?.length ?? 0) > 0;
    test.skip(!hasSteps, "No steps — search bar only shown when steps exist");

    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search steps/i);
    await searchInput.fill("xyznonexistent12345");

    await expect(
      page.getByText(/No steps match your search/i)
    ).toBeVisible({ timeout: 5000 });
  });
});
