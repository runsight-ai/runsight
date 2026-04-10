import { expect, test } from "@playwright/test";
import { gotoShellRoute, setupShellReadyWorkspace } from "./helpers/shellReady";

setupShellReadyWorkspace(test);

test.describe("Settings tabs", () => {
  test("uses Providers and Fallback tabs and only shows provider actions on Providers", async ({
    page,
  }) => {
    await gotoShellRoute(page, "/settings");
    await expect(page).toHaveURL(/\/settings$/);

    const visibleAddProviderButton = page.locator("button:visible", {
      hasText: "Add Provider",
    });
    const tablist = page.getByRole("tablist");
    await expect(tablist).toBeVisible();

    const providersTab = page.getByRole("tab", { name: "Providers" });
    const fallbackTab = page.getByRole("tab", { name: "Fallback" });

    await expect(providersTab).toHaveAttribute("aria-selected", "true");
    await expect(fallbackTab).toHaveAttribute("aria-selected", "false");
    await expect(visibleAddProviderButton.first()).toBeVisible();

    await expect(page.getByRole("tab", { name: "Models" })).toHaveCount(0);
    await expect(page.getByText("Budgets", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Profile", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Advanced", { exact: true })).toHaveCount(0);

    await fallbackTab.click();

    await expect(fallbackTab).toHaveAttribute("aria-selected", "true");
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByText("Fallback", { exact: true }).first()).toBeVisible();
    await expect(visibleAddProviderButton).toHaveCount(0);
  });

  test("supports tab and arrow-key navigation within Providers and Fallback", async ({
    page,
  }) => {
    await gotoShellRoute(page, "/settings");
    await expect(page).toHaveURL(/\/settings$/);

    const providersTab = page.getByRole("tab", { name: "Providers" });
    const fallbackTab = page.getByRole("tab", { name: "Fallback" });

    for (let index = 0; index < 25; index += 1) {
      await page.keyboard.press("Tab");
      if (await providersTab.evaluate((element) => element === document.activeElement)) {
        break;
      }
    }
    await expect(providersTab).toBeFocused();
    await expect(page).toHaveURL(/\/settings$/);

    await page.keyboard.press("Tab");
    await expect(providersTab).not.toBeFocused();
    await expect(providersTab).toHaveAttribute("aria-selected", "true");

    await page.keyboard.press("Shift+Tab");
    await expect(providersTab).toBeFocused();

    await providersTab.focus();
    await page.keyboard.press("ArrowRight");
    await expect(fallbackTab).toBeFocused();

    await page.keyboard.press("ArrowLeft");
    await expect(providersTab).toBeFocused();
  });
});
