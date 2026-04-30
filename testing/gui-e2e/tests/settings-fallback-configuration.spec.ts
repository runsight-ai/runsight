import { expect, test, type Page, type Request } from "@playwright/test";
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { stringify } from "yaml";

import { getE2ERuntimeRoot } from "./helpers/runtimeRoot";

const API = "http://localhost:8000/api";

const projectRoot = getE2ERuntimeRoot();
const providersDir = path.join(projectRoot, "custom", "providers");
const settingsDir = path.join(projectRoot, ".runsight");
const settingsFile = path.join(settingsDir, "settings.yaml");

type ProviderFixture = {
  id: string;
  name: string;
  type: string;
  status: string;
  is_active: boolean;
  models: string[];
};

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

let originalProviderFiles = new Map<string, string>();
let originalSettingsContent: string | null = null;

async function readOptionalFile(filePath: string): Promise<string | null> {
  try {
    return await readFile(filePath, "utf-8");
  } catch {
    return null;
  }
}

async function listYamlFiles(dir: string): Promise<string[]> {
  try {
    return (await readdir(dir)).filter((fileName) => fileName.endsWith(".yaml"));
  } catch {
    return [];
  }
}

async function apiGet<T>(apiPath: string): Promise<T> {
  const response = await fetch(`${API}${apiPath}`);
  expect(response.ok).toBe(true);
  return response.json() as Promise<T>;
}

async function snapshotWorkspace() {
  originalProviderFiles = new Map<string, string>();
  for (const fileName of await listYamlFiles(providersDir)) {
    originalProviderFiles.set(fileName, await readFile(path.join(providersDir, fileName), "utf-8"));
  }
  originalSettingsContent = await readOptionalFile(settingsFile);
}

async function restoreWorkspace() {
  await mkdir(providersDir, { recursive: true });
  for (const fileName of await listYamlFiles(providersDir)) {
    await rm(path.join(providersDir, fileName));
  }
  for (const [fileName, content] of originalProviderFiles.entries()) {
    await writeFile(path.join(providersDir, fileName), content, "utf-8");
  }

  await mkdir(settingsDir, { recursive: true });
  if (originalSettingsContent === null) {
    await rm(settingsFile, { force: true });
  } else {
    await writeFile(settingsFile, originalSettingsContent, "utf-8");
  }
}

async function seedProviders(providers: ProviderFixture[]) {
  await mkdir(providersDir, { recursive: true });
  for (const fileName of await listYamlFiles(providersDir)) {
    await rm(path.join(providersDir, fileName));
  }
  for (const provider of providers) {
    await writeFile(
      path.join(providersDir, `${provider.id}.yaml`),
      stringify({
        id: provider.id,
        kind: "provider",
        name: provider.name,
        type: provider.type,
        status: provider.status,
        is_active: provider.is_active,
        models: provider.models,
      }),
      "utf-8",
    );
  }
}

async function seedSettings(settings: SettingsFixture | null) {
  await mkdir(settingsDir, { recursive: true });
  if (settings === null) {
    await rm(settingsFile, { force: true });
    return;
  }
  await writeFile(
    settingsFile,
    stringify({
      onboarding_completed: true,
      ...settings,
    }),
    "utf-8",
  );
}

async function applyFixture(providers: ProviderFixture[], settings: SettingsFixture | null) {
  await seedProviders(providers);
  await seedSettings(settings);
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
    await snapshotWorkspace();
  });

  test.afterAll(async () => {
    await restoreWorkspace();
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
