import { expect, test } from "@playwright/test";

import { setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

test.describe("soul form validation", () => {
  test("keeps Create Soul disabled when the name is empty", async ({ page }) => {
    await page.goto("/souls/new");
    await page.waitForLoadState("networkidle");

    await page.getByLabel("System Prompt").fill("Test");
    await expect(page.getByRole("button", { name: "Create Soul" })).toBeDisabled();
  });

  test("keeps Create Soul disabled when the name is whitespace only", async ({ page }) => {
    await page.goto("/souls/new");
    await page.waitForLoadState("networkidle");

    await page.getByLabel("Name").fill("   ");
    await page.getByLabel("System Prompt").fill("Test");
    await expect(page.getByRole("button", { name: "Create Soul" })).toBeDisabled();
  });
});
