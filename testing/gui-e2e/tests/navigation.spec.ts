import { expect, test } from "@playwright/test";

import { gotoShellRoute, setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

const NAV_ITEMS = [
  { label: "Home", url: "/", heading: "Home" },
  { label: "Flows", url: "/flows", heading: "Flows" },
  { label: "Runs", url: "/runs", heading: "Runs" },
  { label: "Souls", url: "/souls", heading: "Souls" },
  { label: "Settings", url: "/settings", heading: "Settings" },
];

test.describe("Shell navigation", () => {
  test("shows the current shell labels and omits retired nav items", async ({ page }) => {
    await gotoShellRoute(page, "/");

    for (const { label } of NAV_ITEMS) {
      await expect(page.locator("aside").getByRole("link", { name: label })).toBeVisible();
    }

    await expect(page.locator("aside").getByRole("link", { name: "Tasks" })).toHaveCount(0);
    await expect(page.locator("aside").getByRole("link", { name: "Steps" })).toHaveCount(0);
  });

  test("marks the active nav item with aria-current", async ({ page }) => {
    await gotoShellRoute(page, "/");
    await expect(page.locator("aside").getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("clicks through the canonical shell routes", async ({ page }) => {
    await gotoShellRoute(page, "/");

    const sidebar = page.locator("aside");

    for (const { label, url } of NAV_ITEMS) {
      await sidebar.getByRole("link", { name: label }).click();
      if (url === "/") {
        await expect(page).toHaveURL(/\/(?:\?.*)?$/);
      } else {
        await expect(page).toHaveURL(new RegExp(`${url}(?:\\?.*)?$`));
      }
    }
  });

  test("renders the expected page heading for each shell route", async ({ page }) => {
    for (const { url, heading } of NAV_ITEMS) {
      await gotoShellRoute(page, url);
      await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
    }
  });
});
