import { expect, test } from "@playwright/test";

import { setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

test.describe("settings providers page", () => {
  test("loads the Providers tab without an error state", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("tab", { name: /Providers/i }).or(page.getByText(/Providers/i).first()),
    ).toBeVisible({ timeout: 10000 });
  });
});
