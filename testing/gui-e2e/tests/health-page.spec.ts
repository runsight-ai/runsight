import { expect, test } from "@playwright/test";
import { gotoShellRoute, setupShellReadyWorkspace } from "./helpers/shellReady";

setupShellReadyWorkspace(test);

test.describe("Retired health route", () => {
  test("direct visits to /health redirect into the supported shell, not onboarding", async ({
    page,
  }) => {
    await gotoShellRoute(page, "/health");

    await expect(page).not.toHaveURL(/\/health$/);
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Home" })).toBeVisible();
  });

  test("retired /health bookmarks no longer render health placeholder content", async ({
    page,
  }) => {
    await gotoShellRoute(page, "/health");

    await expect(page.getByText(/Health.*TODO|TODO.*Health/i)).toHaveCount(0);
    await expect(page.getByText(/^Health$/i)).toHaveCount(0);
  });

  test("shell navigation no longer exposes a Health route", async ({ page }) => {
    await gotoShellRoute(page, "/");

    await expect(
      page.getByRole("navigation").getByRole("link", { name: "Health" }),
    ).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Health" })).toHaveCount(0);
  });
});
