import { expect, test, type Page, type Request } from "@playwright/test";

import {
  apiGet,
  captureWorkspace,
  restoreWorkspace,
  seedProviders,
  seedSettings,
  type ProviderFixture,
  type WorkspaceSnapshot,
} from "./helpers/shellReady";

type SettingsFixture = {
  fallback_enabled?: boolean;
  onboarding_completed?: boolean;
  fallback_map?: Array<{
    provider_id: string;
    fallback_provider_id: string;
    fallback_model_id: string;
  }>;
};

const PRIMARY_ENABLED: ProviderFixture = {
  id: "primary-fixture-provider",
  name: "Primary Fixture",
  type: "primary-fixture-provider",
  status: "connected",
  is_active: true,
  models: ["primary-fast", "primary-deep"],
};

const BACKUP_ENABLED: ProviderFixture = {
  id: "backup-fixture-provider",
  name: "Backup Fixture",
  type: "backup-fixture-provider",
  status: "connected",
  is_active: true,
  models: ["backup-balanced", "backup-fast"],
};

const BACKUP_DISABLED: ProviderFixture = {
  ...BACKUP_ENABLED,
  is_active: false,
};

let originalWorkspace: WorkspaceSnapshot | null = null;

async function applyFixture(providers: ProviderFixture[], settings: SettingsFixture) {
  await seedProviders(providers);
  await seedSettings({
    ...settings,
    onboarding_completed: settings.onboarding_completed ?? true,
  });
  await expect.poll(async () => {
    const data = await apiGet<{ items: Array<{ id: string }>; total: number }>("/settings/providers");
    return data.items.map((provider) => provider.id).sort().join(",");
  }).toBe(providers.map((provider) => provider.id).sort().join(","));
  await expect.poll(async () => {
    const data = await apiGet<{ items: Array<{ id: string }>; total: number }>("/settings/fallbacks");
    return data.total;
  }).toBe(providers.filter((provider) => provider.is_active).length);
}

async function openFallbackTab(page: Page) {
  await page.goto("/settings");
  await expect(page.getByRole("tablist")).toBeVisible();
  const fallbackTab = page.getByRole("tab", { name: "Fallback" });
  await fallbackTab.click();
  await expect(fallbackTab).toHaveAttribute("aria-selected", "true");
}

async function chooseSelectOption(page: Page, label: string, optionText: string) {
  await page.getByLabel(label).click();
  await page.getByRole("option", { name: optionText, exact: true }).click();
}

test.describe("Per-provider fallback configuration", () => {
  test.beforeAll(async () => {
    originalWorkspace = await captureWorkspace();
  });

  test.afterAll(async () => {
    if (originalWorkspace) {
      await restoreWorkspace(originalWorkspace);
    }
  });

  test("zero providers shows the fallback empty state", async ({ page }) => {
    await applyFixture([], { fallback_enabled: false, fallback_map: [] });

    await openFallbackTab(page);

    await expect(page.getByRole("tab", { name: "Fallback" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("No providers configured")).toBeVisible();
    await expect(page.getByLabel("Enable fallback")).toHaveCount(0);
  });

  test("one enabled provider keeps fallback disabled and hides rows", async ({ page }) => {
    await applyFixture([PRIMARY_ENABLED], { fallback_enabled: false, fallback_map: [] });

    await openFallbackTab(page);

    await expect(page.getByRole("tab", { name: "Fallback" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByLabel("Enable fallback")).toBeDisabled();
    await expect(
      page.getByText(
        "Enable at least two providers to configure runtime fallback. Once two providers are enabled, you can choose one fallback target per provider.",
      ),
    ).toBeVisible();
    await expect(page.getByLabel("Fallback provider for Primary Fixture")).toHaveCount(0);
  });

  test("two enabled providers render rows greyed out while the toggle is off by default", async ({
    page,
  }) => {
    await applyFixture(
      [PRIMARY_ENABLED, BACKUP_ENABLED],
      { fallback_enabled: false, fallback_map: [] },
    );

    await openFallbackTab(page);

    const disabledRows = page.locator('div[style*="opacity: 0.4"][style*="pointer-events: none"]');

    await expect(page.getByLabel("Enable fallback")).toHaveAttribute("aria-checked", "false");
    await expect(disabledRows).toHaveCount(1);
    await expect(page.getByLabel("Fallback provider for Primary Fixture")).toBeDisabled();
    await expect(page.getByLabel("Fallback provider for Backup Fixture")).toBeDisabled();
    await expect(page.getByLabel("Fallback model for Primary Fixture")).toBeDisabled();
    await expect(page.getByLabel("Fallback model for Backup Fixture")).toBeDisabled();
  });

  test("pair-only save persists across navigation and returns after eligibility is restored", async ({
    page,
  }) => {
    await applyFixture(
      [PRIMARY_ENABLED, BACKUP_ENABLED],
      {
        fallback_enabled: true,
        fallback_map: [],
      },
    );

    const updateBodies: Array<Record<string, unknown>> = [];
    const onRequest = (request: Request) => {
      if (request.method() !== "PUT" || !request.url().includes("/api/settings/fallbacks/")) {
        return;
      }
      const body = request.postData();
      updateBodies.push(body ? (JSON.parse(body) as Record<string, unknown>) : {});
    };
    page.on("request", onRequest);

    await openFallbackTab(page);

    await expect(page.getByLabel("Enable fallback")).toHaveAttribute("aria-checked", "true");
    await chooseSelectOption(page, "Fallback provider for Primary Fixture", "Backup Fixture");
    await expect(page.getByLabel("Fallback model for Primary Fixture")).toBeEnabled();
    expect(updateBodies).toHaveLength(0);

    await chooseSelectOption(page, "Fallback model for Primary Fixture", "backup-balanced");

    await expect.poll(() => updateBodies.length).toBe(1);
    expect(updateBodies[0]).toEqual({
      fallback_provider_id: "backup-fixture-provider",
      fallback_model_id: "backup-balanced",
    });

    await expect.poll(async () => {
      const data = await apiGet<{
        items: Array<{
          id: string;
          fallback_provider_id: string | null;
          fallback_model_id: string | null;
        }>;
      }>("/settings/fallbacks");
      const primaryRow = data.items.find((item) => item.id === "primary-fixture-provider");
      return `${primaryRow?.fallback_provider_id ?? "null"}|${primaryRow?.fallback_model_id ?? "null"}`;
    }).toBe("backup-fixture-provider|backup-balanced");

    await page.getByRole("tab", { name: "Providers" }).click();
    await page.getByRole("tab", { name: "Fallback" }).click();

    await expect(page.getByLabel("Fallback provider for Primary Fixture")).toContainText("Backup Fixture");
    await expect(page.getByLabel("Fallback model for Primary Fixture")).toContainText("backup-balanced");

    await applyFixture(
      [PRIMARY_ENABLED, BACKUP_DISABLED],
      {
        fallback_enabled: true,
        fallback_map: [
          {
            provider_id: "primary-fixture-provider",
            fallback_provider_id: "backup-fixture-provider",
            fallback_model_id: "backup-balanced",
          },
        ],
      },
    );

    await openFallbackTab(page);

    await expect(page.getByLabel("Enable fallback")).toBeDisabled();
    await expect(
      page.getByText(
        "Enable at least two providers to configure runtime fallback. Once two providers are enabled, you can choose one fallback target per provider.",
      ),
    ).toBeVisible();
    await expect(page.getByLabel("Fallback provider for Primary Fixture")).toHaveCount(0);

    await applyFixture(
      [PRIMARY_ENABLED, BACKUP_ENABLED],
      {
        fallback_enabled: true,
        fallback_map: [
          {
            provider_id: "primary-fixture-provider",
            fallback_provider_id: "backup-fixture-provider",
            fallback_model_id: "backup-balanced",
          },
        ],
      },
    );

    await openFallbackTab(page);

    await expect(page.getByLabel("Enable fallback")).toHaveAttribute("aria-checked", "true");
    await expect(page.getByLabel("Fallback provider for Primary Fixture")).toContainText("Backup Fixture");
    await expect(page.getByLabel("Fallback model for Primary Fixture")).toContainText("backup-balanced");

    page.off("request", onRequest);
  });
});
