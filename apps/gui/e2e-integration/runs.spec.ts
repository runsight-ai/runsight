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
    
    // BUG: Runs page might not load correctly
    await expect(
      page.getByRole("main").getByRole("heading", { name: /Runs/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test("check active and history tabs", async ({ page }) => {
    await page.goto("/runs");
    
    // BUG: Tabs might be missing or broken
    const activeTab = page.getByRole("tab", { name: /Active/i });
    const historyTab = page.getByRole("tab", { name: /History/i });
    
    await expect(activeTab).toBeVisible();
    await expect(historyTab).toBeVisible();
    await historyTab.click();
    await expect(historyTab).toHaveAttribute("aria-selected", "true");
    
    await activeTab.click();
    await expect(activeTab).toHaveAttribute("aria-selected", "true");
  });

  test("existing runs display correctly", async ({ page }) => {
    await page.goto("/runs");
    
    const data = await apiGet("/runs");
    
    // BUG: Run list rendering might be broken
    if (data.items && data.items.length > 0) {
      await expect(
        page.getByText(data.items[0].id.substring(0, 8), { exact: false }).first()
      ).toBeVisible({ timeout: 10000 });
    } else {
      await expect(
        page.getByText(/No active runs|No runs in history/i, { exact: false })
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test("run creation (known limitation without LLM)", async ({ page }) => {
    // Documenting known limitation: Run creation may not work without LLM
    // BUG: Run creation fails gracefully or ungracefully if no LLM is configured
    test.info().annotations.push({
      type: "known limitation",
      description: "Run creation may not work without LLM configured"
    });
    
    test.skip(true, 'Run creation requires LLM — known limitation');
  });
});
