import { expect, test } from "@playwright/test";

import { setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

test.describe("missing resource pages", () => {
  test("workflow editor shows a not-found message for an unknown workflow", async ({ page }) => {
    const fakeId = "00000000-0000-0000-0000-000000000000";

    await page.goto(`/workflows/${fakeId}/edit`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/not found/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("link", { name: /back to workflows/i })).toBeVisible();
  });

  test("run details page shows not found for an unknown run", async ({ page }) => {
    const fakeId = "00000000-0000-0000-0000-000000000000";

    await page.goto(`/runs/${fakeId}`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/Run not found|not found/i)).toBeVisible({
      timeout: 10000,
    });
  });
});
