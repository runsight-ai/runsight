/**
 * Canvas Workflow Name Mutations E2E integration tests — NO MOCKS.
 * Tests workflow name edit, API sync, Enter/Escape.
 *
 * Run: pnpm -C testing/gui-e2e test -- canvas-mutations --reporter=list --retries=0
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";

async function apiGet(path: string) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

test.describe("Canvas Mutations", () => {
  const testWorkflowName = `e2e-mutations-${Date.now()}`;
  let createdWorkflowId: string | null = null;

  test.beforeAll(async () => {
    const res = await fetch(`${API}/workflows`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: testWorkflowName }),
    });
    const data = await res.json();
    createdWorkflowId = data.id;
  });

  test.afterAll(async () => {
    if (createdWorkflowId) {
      await fetch(`${API}/workflows/${createdWorkflowId}`, { method: "DELETE" });
    }
  });

  test("workflow name heading shows real workflow name", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const heading = page.getByRole("heading", { name: testWorkflowName });
    await expect(heading).toBeVisible({ timeout: 5000 });

    const data = await apiGet(`/workflows/${createdWorkflowId}`);
    expect(data.name).toBe(testWorkflowName);
  });

  test("click edit button → inline input appears", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    await page.getByRole("button", { name: "Edit workflow name" }).click();
    const input = page.getByRole("textbox", { name: "Edit workflow name" });
    await expect(input).toBeVisible({ timeout: 3000 });
    await expect(input).toHaveValue(testWorkflowName);
  });

  test("edit name and blur → sends PUT to API, heading updates", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    await page.getByRole("button", { name: "Edit workflow name" }).click();
    const input = page.getByRole("textbox", { name: "Edit workflow name" });
    await input.fill("Updated Workflow Name");
    await input.blur();

    await expect(page.getByRole("heading", { name: "Updated Workflow Name" })).toBeVisible({ timeout: 5000 });

    // Wait for API to persist (mutate is async)
    await expect
      .poll(async () => {
        const data = await apiGet(`/workflows/${createdWorkflowId}`);
        return data.name;
      }, { timeout: 5000 })
      .toBe("Updated Workflow Name");
  });

  test("edit name and press Enter → saves", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    await page.getByRole("button", { name: "Edit workflow name" }).click();
    const input = page.getByRole("textbox", { name: "Edit workflow name" });
    await input.fill("Saved Via Enter");
    await input.press("Enter");

    await expect(page.getByRole("heading", { name: "Saved Via Enter" })).toBeVisible({ timeout: 5000 });

    const data = await apiGet(`/workflows/${createdWorkflowId}`);
    expect(data.name).toBe("Saved Via Enter");
  });

  test("edit name and press Escape → reverts to original", async ({ page }) => {
    test.skip(!createdWorkflowId, "Workflow was not created");

    await page.goto(`/workflows/${createdWorkflowId}`);
    await page.waitForSelector(".react-flow", { timeout: 15000 });

    const currentName = (await apiGet(`/workflows/${createdWorkflowId}`)).name;

    await page.getByRole("button", { name: "Edit workflow name" }).click();
    const input = page.getByRole("textbox", { name: "Edit workflow name" });
    await input.fill("This Will Revert");
    await input.press("Escape");

    await expect(page.getByRole("heading", { name: currentName })).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("textbox", { name: "Edit workflow name" })).not.toBeVisible();
  });
});
