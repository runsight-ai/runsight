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

async function apiDelete(path: string) {
  return fetch(`${API}${path}`, { method: "DELETE" });
}

async function apiPost(path: string, body: object) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

test.describe("Souls page: search and empty states", () => {
  const fixtureSoulName = `e2e-search-soul-${Date.now()}`;
  let fixtureSoulId: string | null = null;

  test.beforeAll(async () => {
    const data = await apiPost("/souls", {
      name: fixtureSoulName,
      system_prompt: "E2E search fixture soul",
    });
    fixtureSoulId = data.id ?? null;
  });

  test.afterAll(async () => {
    if (fixtureSoulId) {
      await apiDelete(`/souls/${fixtureSoulId}`);
    }
  });

  test("Souls page: search input exists", async ({ page }) => {
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test("Souls page: type in search → filters rows (use name of a real soul from API)", async ({
    page,
  }) => {
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await searchInput.fill(fixtureSoulName);

    await expect(
      page.getByRole("table").getByText(fixtureSoulName, { exact: true }).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test("Souls page: search for nonexistent → shows empty state", async ({
    page,
  }) => {
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
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await searchInput.fill("xyznonexistent12345");
    await expect(page.getByText(/No souls match your search/i)).toBeVisible({
      timeout: 5000,
    });

    await page.getByRole("button", { name: /Clear search/i }).click();
    await expect(page.getByText(fixtureSoulName, { exact: true }).first()).toBeVisible({ timeout: 5000 });
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
  const fixtureTaskName = `e2e-search-task-${Date.now()}`;
  let fixtureTaskId: string | null = null;

  test.beforeAll(async () => {
    const data = await apiPost("/tasks", {
      name: fixtureTaskName,
      description: "E2E search fixture task",
    });
    fixtureTaskId = data.id ?? null;
  });

  test.afterAll(async () => {
    if (fixtureTaskId) {
      await apiDelete(`/tasks/${fixtureTaskId}`);
    }
  });

  test("Tasks page: search input exists", async ({ page }) => {
    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search tasks/i);
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test("Tasks page: search filters tasks by name", async ({ page }) => {
    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search tasks/i);
    await searchInput.fill(fixtureTaskName);

    await expect(page.getByText(fixtureTaskName, { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test("Tasks page: search empty state", async ({ page }) => {
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
  const fixtureStepName = `e2e-search-step-${Date.now()}`;
  let fixtureStepId: string | null = null;

  test.beforeAll(async () => {
    const data = await apiPost("/steps", {
      name: fixtureStepName,
      description: "E2E search fixture step",
    });
    fixtureStepId = data.id ?? null;
  });

  test.afterAll(async () => {
    if (fixtureStepId) {
      await apiDelete(`/steps/${fixtureStepId}`);
    }
  });

  test("Steps page: search input exists", async ({ page }) => {
    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search steps/i);
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test("Steps page: search filters steps by name", async ({ page }) => {
    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search steps/i);
    await searchInput.fill(fixtureStepName);

    await expect(page.getByText(fixtureStepName, { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test("Steps page: search empty state", async ({ page }) => {
    await page.goto("/steps");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search steps/i);
    await searchInput.fill("xyznonexistent12345");

    await expect(
      page.getByText(/No steps match your search/i)
    ).toBeVisible({ timeout: 5000 });
  });
});
