import { test, expect } from "@playwright/test";

import { setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

const API = "http://localhost:8000/api";

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
      id: fixtureSoulName,
      kind: "soul",
      name: fixtureSoulName,
      role: fixtureSoulName,
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

    await expect(page.getByPlaceholder(/search souls/i)).toBeVisible({ timeout: 10000 });
  });

  test("Souls page: type in search filters the current table rows", async ({ page }) => {
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await searchInput.fill(fixtureSoulName);

    await expect(page.getByText(fixtureSoulName, { exact: true }).first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("Souls page: search for nonexistent shows the DataTable empty state", async ({
    page,
  }) => {
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    await page.getByPlaceholder(/search souls/i).fill("xyznonexistent12345");

    await expect(page.getByText("No results found")).toBeVisible({ timeout: 5000 });
  });

  test("Souls page: clear search restores the matching rows", async ({ page }) => {
    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    const searchInput = page.getByPlaceholder(/search souls/i);
    await searchInput.fill("xyznonexistent12345");
    await expect(page.getByText("No results found")).toBeVisible({ timeout: 5000 });

    await searchInput.clear();
    await expect(page.getByText(fixtureSoulName, { exact: true }).first()).toBeVisible({
      timeout: 10000,
    });
  });
});
