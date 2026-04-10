import { expect, test, type Page } from "@playwright/test";
import {
  apiGet,
  applyFixture,
  captureWorkspace,
  gotoShellRoute,
  restoreWorkspace,
  type ProviderFixture,
  type SettingsFixture,
  type WorkspaceSnapshot,
} from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });

const READY_SETTINGS: SettingsFixture = {
  onboarding_completed: true,
  fallback_enabled: false,
};

async function stubProviderConnection(
  page: Page,
  result: {
    success: boolean;
    message: string;
    models?: string[];
  } = {
    success: true,
    message: "Connection successful",
    models: ["gpt-4.1-mini"],
  },
) {
  let credentialChecks = 0;
  let savedProviderChecks = 0;

  await page.route(/\/api\/settings\/providers\/test$/, async (route) => {
    credentialChecks += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: result.success,
        message: result.message,
        models: result.models ?? [],
        model_count: result.models?.length ?? 0,
        latency_ms: 8,
      }),
    });
  });

  await page.route(/\/api\/settings\/providers\/[^/]+\/test$/, async (route) => {
    savedProviderChecks += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: result.success,
        message: result.message,
        models: result.models ?? [],
        model_count: result.models?.length ?? 0,
        latency_ms: 9,
      }),
    });
  });

  return {
    get credentialChecks() {
      return credentialChecks;
    },
    get savedProviderChecks() {
      return savedProviderChecks;
    },
  };
}

test.describe("Settings: Providers CRUD", () => {
  let snapshot: WorkspaceSnapshot;

  test.beforeAll(async () => {
    snapshot = await captureWorkspace();
  });

  test.afterAll(async () => {
    await restoreWorkspace(snapshot);
  });

  test.beforeEach(async () => {
    await applyFixture([], READY_SETTINGS);
  });

  test("providers page lists providers from the local API", async ({ page }) => {
    const seededProvider: ProviderFixture = {
      id: "qa-openai-seed",
      name: "QA OpenAI Seed",
      type: "openai",
      status: "unknown",
      is_active: true,
      models: [],
      api_key: null,
    };

    await applyFixture([seededProvider], READY_SETTINGS);
    await gotoShellRoute(page, "/settings");

    await expect(page.getByText("QA OpenAI Seed", { exact: true })).toBeVisible();
    await expect(
      page.getByLabel("Provider QA OpenAI Seed status Unknown"),
    ).toBeVisible();
    await expect(page.getByText("0 models", { exact: true })).toBeVisible();
  });

  test("add provider via form appears in list and API without third-party access", async ({
    page,
  }) => {
    const calls = await stubProviderConnection(page);

    await gotoShellRoute(page, "/settings");

    await page
      .locator("button:visible", { hasText: "Add Provider" })
      .first()
      .click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();

    const saveButton = modal.getByRole("button", { name: "Save" });
    await expect(saveButton).toBeDisabled();

    await modal.getByPlaceholder("sk-proj-...").fill("sk-test-local-only");
    await expect(modal.getByRole("status")).toContainText("Connected", {
      timeout: 5000,
    });
    await expect(saveButton).toBeEnabled();

    await saveButton.click();
    await expect(modal).not.toBeVisible();

    await expect(page.getByText("OpenAI", { exact: true })).toBeVisible();
    await expect.poll(() => calls.credentialChecks).toBeGreaterThan(0);
    await expect.poll(() => calls.savedProviderChecks).toBe(1);

    const data = await apiGet<{ items: Array<{ id: string; name: string }> }>(
      "/settings/providers",
    );
    expect(data.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "openai", name: "OpenAI" }),
      ]),
    );
  });

  test("test connection triggers the local test endpoint and surfaces feedback", async ({
    page,
  }) => {
    const seededProvider: ProviderFixture = {
      id: "qa-openai-check",
      name: "QA OpenAI Check",
      type: "openai",
      status: "unknown",
      is_active: true,
      models: [],
      api_key: null,
    };

    await applyFixture([seededProvider], READY_SETTINGS);
    const calls = await stubProviderConnection(page, {
      success: true,
      message: "Connection successful",
      models: ["gpt-4.1-mini"],
    });

    await gotoShellRoute(page, "/settings");

    await page
      .getByRole("button", { name: "Test QA OpenAI Check connection" })
      .click();

    await expect.poll(() => calls.savedProviderChecks).toBe(1);
    await expect(page.getByText("Connection successful", { exact: true })).toBeVisible();
  });

  test("delete provider removes it after explicit confirmation", async ({ page }) => {
    const seededProvider: ProviderFixture = {
      id: "qa-delete-provider",
      name: "QA Delete Provider",
      type: "openai",
      status: "unknown",
      is_active: true,
      models: [],
      api_key: null,
    };

    await applyFixture([seededProvider], READY_SETTINGS);
    await gotoShellRoute(page, "/settings");

    await page
      .getByRole("button", { name: "Delete QA Delete Provider provider" })
      .click();

    const dialog = page.getByTestId("delete-confirm-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('QA Delete Provider');

    await dialog.getByTestId("delete-confirm-submit-button").click();

    await expect(dialog).not.toBeVisible();
    await expect(page.getByText("QA Delete Provider", { exact: true })).toHaveCount(0);

    const data = await apiGet<{ items: Array<{ id: string }> }>("/settings/providers");
    expect(data.items).toEqual([]);
  });
});
