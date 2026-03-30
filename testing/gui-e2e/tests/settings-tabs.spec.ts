import { expect, test } from "@playwright/test";

test.describe("Settings tabs", () => {
  test("uses a top tab bar and toggles provider actions with tab changes", async ({
    page,
  }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings$/);

    const visibleAddProviderButton = page.locator("button:visible", {
      hasText: "Add Provider",
    });
    const tablist = page.getByRole("tablist");
    await expect(tablist).toBeVisible();

    const providersTab = page.getByRole("tab", { name: "Providers" });
    const modelsTab = page.getByRole("tab", { name: "Models" });

    await expect(providersTab).toHaveAttribute("aria-selected", "true");
    await expect(modelsTab).toHaveAttribute("aria-selected", "false");
    await expect(visibleAddProviderButton.first()).toBeVisible();

    await expect(page.getByText("Budgets", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Profile", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Advanced", { exact: true })).toHaveCount(0);

    await modelsTab.click();

    await expect(modelsTab).toHaveAttribute("aria-selected", "true");
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByRole("heading", { name: "Models" })).toBeVisible();
    await expect(visibleAddProviderButton).toHaveCount(0);
  });

  test("supports tab and arrow-key tab navigation", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings$/);

    const providersTab = page.getByRole("tab", { name: "Providers" });
    const modelsTab = page.getByRole("tab", { name: "Models" });

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
    await expect(page).toHaveURL(/\/settings$/);

    await page.keyboard.press("Shift+Tab");

    await expect(providersTab).toBeFocused();
    await expect(page).toHaveURL(/\/settings$/);

    await providersTab.focus();
    await page.keyboard.press("ArrowRight");

    await expect(modelsTab).toBeFocused();
    await expect(page).toHaveURL(/\/settings$/);

    await page.keyboard.press("ArrowLeft");

    await expect(providersTab).toBeFocused();
    await expect(page).toHaveURL(/\/settings$/);
  });
});
