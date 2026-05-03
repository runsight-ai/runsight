import { expect, test } from "@playwright/test";

import { setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const response = await fetch(`${API}${path}`);
  expect(response.ok).toBeTruthy();
  return response.json();
}

test.describe("souls page healthy state", () => {
  test("does not show a load error when the souls API is healthy", async ({ page }) => {
    const data = await apiGet("/souls");
    expect(data).toBeDefined();
    expect(Array.isArray(data.items)).toBe(true);

    await page.goto("/souls");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/Failed to load souls/i)).not.toBeVisible();
  });
});
