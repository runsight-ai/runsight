import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

test.describe("Runs", () => {
  test("navigate to runs page, verify it loads", async ({ page }) => {
    await page.goto("/runs");
    await expect(page.getByRole("main").getByRole("heading", { name: /Runs/i })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByRole("searchbox", { name: "Search runs" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Active" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Needs attention" })).toBeVisible();
  });

  test("active and attention filters use button toggles instead of the retired tab bar", async ({
    page,
  }) => {
    await page.goto("/runs");

    const activeButton = page.getByRole("button", { name: "Active" });
    const attentionButton = page.getByRole("button", { name: "Needs attention" });

    await expect(page.getByRole("tab", { name: /Active/i })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: /History/i })).toHaveCount(0);

    await activeButton.click();
    await expect(activeButton).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(/status=active/);

    await attentionButton.click();
    await expect(attentionButton).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(/attention=only/);
  });

  test("existing runs display correctly", async ({ page }) => {
    await page.goto("/runs");
    const data = await apiGet("/runs");

    if (data.items && data.items.length > 0) {
      await expect(page.getByText(data.items[0].workflow_name, { exact: true }).first()).toBeVisible({
        timeout: 10000,
      });
      await page.getByRole("searchbox", { name: "Search runs" }).fill(data.items[0].workflow_name);
      await expect(page.getByText(data.items[0].workflow_name, { exact: true }).first()).toBeVisible();
    } else {
      await expect(page.getByText(/No runs yet|No matching runs/i, { exact: false })).toBeVisible({
        timeout: 10000,
      });
    }
  });
});
