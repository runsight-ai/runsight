import { expect, test, type Page, type Request } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { stringify } from "yaml";

const API = "http://localhost:8000/api";
const workspaceDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(workspaceDir, "../..");

function detectApiProjectRoot() {
  if (process.env.RUNSIGHT_E2E_PROJECT_ROOT) {
    return process.env.RUNSIGHT_E2E_PROJECT_ROOT;
  }

  try {
    const pids = execFileSync("lsof", ["-t", "-i", "tcp:8000"], {
      encoding: "utf-8",
    })
      .split(/\s+/)
      .map((value) => value.trim())
      .filter(Boolean);

    for (const pid of pids) {
      const cwdOutput = execFileSync("lsof", ["-a", "-p", pid, "-d", "cwd", "-Fn"], {
        encoding: "utf-8",
      });
      const cwdLine = cwdOutput
        .split("\n")
        .map((line) => line.trim())
        .find((line) => line.startsWith("n/"));
      if (cwdLine) {
        return cwdLine.slice(1);
      }
    }
  } catch {
    return repoRoot;
  }

  return repoRoot;
}

const projectRoot = detectApiProjectRoot();
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
  model_defaults?: Array<{
    provider_id: string;
    model_id: string;
    is_default?: boolean;
  }>;
  fallback_map?: Array<{
    provider_id: string;
    fallback_provider_id: string;
    fallback_model_id: string;
  }>;
};

const OPENAI_ENABLED: ProviderFixture = {
  id: "openai",
  name: "OpenAI",
  type: "openai",
  status: "connected",
  is_active: true,
  models: ["gpt-4o", "gpt-4.1"],
};

const ANTHROPIC_ENABLED: ProviderFixture = {
  id: "anthropic",
  name: "Anthropic",
  type: "anthropic",
  status: "connected",
  is_active: true,
  models: ["claude-sonnet-4", "claude-haiku-4-5"],
};

const ANTHROPIC_DISABLED: ProviderFixture = {
  ...ANTHROPIC_ENABLED,
  is_active: false,
};

const TWO_PROVIDER_DEFAULTS: SettingsFixture = {
  fallback_enabled: false,
  model_defaults: [
    { provider_id: "openai", model_id: "gpt-4o", is_default: true },
    { provider_id: "anthropic", model_id: "claude-sonnet-4", is_default: true },
  ],
};

const ONE_PROVIDER_DEFAULTS: SettingsFixture = {
  fallback_enabled: false,
  model_defaults: [{ provider_id: "openai", model_id: "gpt-4o", is_default: true }],
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

async function apiGet<T>(apiPath: string): Promise<T> {
  const response = await fetch(`${API}${apiPath}`);
  expect(response.ok).toBe(true);
  return response.json() as Promise<T>;
}

async function snapshotWorkspace() {
  originalProviderFiles = new Map<string, string>();
  for (const fileName of await readdir(providersDir)) {
    if (!fileName.endsWith(".yaml")) continue;
    originalProviderFiles.set(fileName, await readFile(path.join(providersDir, fileName), "utf-8"));
  }
  originalSettingsContent = await readOptionalFile(settingsFile);
}

async function restoreWorkspace() {
  await mkdir(providersDir, { recursive: true });
  for (const fileName of await readdir(providersDir)) {
    if (fileName.endsWith(".yaml")) {
      await rm(path.join(providersDir, fileName));
    }
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
  for (const fileName of await readdir(providersDir)) {
    if (fileName.endsWith(".yaml")) {
      await rm(path.join(providersDir, fileName));
    }
  }
  for (const provider of providers) {
    await writeFile(
      path.join(providersDir, `${provider.id}.yaml`),
      stringify({
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
    const data = await apiGet<{ items: Array<{ id: string }>; total: number }>("/settings/models");
    return data.total;
  }).toBe(settings?.model_defaults?.filter((entry) => {
    const provider = providers.find((candidate) => candidate.id === entry.provider_id);
    return provider?.is_active ?? false;
  }).length ?? 0);
}

async function openModelsTab(page: Page) {
  await page.goto("/settings");
  await expect(page.getByRole("tablist")).toBeVisible();
  const modelsTab = page.getByRole("tab", { name: "Models" });
  await modelsTab.click();
  await expect(modelsTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "Models" })).toBeVisible();
}

async function chooseSelectOption(
  page: Page,
  label: string,
  optionText: string,
) {
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

  test("zero providers shows the full Models empty state with no Fallback section", async ({
    page,
  }) => {
    await applyFixture([], { fallback_enabled: false, model_defaults: [] });

    await openModelsTab(page);

    await expect(page.getByText("No model defaults configured")).toBeVisible();
    await expect(
      page.getByText(
        "Model defaults and fallback targets will appear here once providers are connected and models are available.",
      ),
    ).toBeVisible();
    await expect(page.getByText("Fallback", { exact: true })).toHaveCount(0);
    await expect(page.getByLabel("Enable fallback")).toHaveCount(0);
  });

  test("one enabled provider keeps one default-model row and a disabled empty fallback state", async ({
    page,
  }) => {
    await applyFixture([OPENAI_ENABLED], ONE_PROVIDER_DEFAULTS);

    await openModelsTab(page);

    await expect(page.getByText("Default Model per Provider")).toBeVisible();
    await expect(page.getByText("OpenAI", { exact: true })).toBeVisible();
    await expect(page.getByText("Fallback", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Enable fallback")).toBeDisabled();
    await expect(
      page.getByText("Enable at least two providers to configure fallback targets."),
    ).toBeVisible();
    await expect(page.getByLabel("Fallback provider for OpenAI")).toHaveCount(0);
  });

  test("two enabled providers render fallback rows greyed out while the toggle is off by default", async ({
    page,
  }) => {
    await applyFixture([OPENAI_ENABLED, ANTHROPIC_ENABLED], TWO_PROVIDER_DEFAULTS);

    await openModelsTab(page);

    const disabledRows = page.locator('div[style*="opacity: 0.4"][style*="pointer-events: none"]');

    await expect(page.getByLabel("Enable fallback")).toHaveAttribute("aria-checked", "false");
    await expect(disabledRows).toHaveCount(1);
    await expect(page.getByLabel("Fallback provider for OpenAI")).toBeDisabled();
    await expect(page.getByLabel("Fallback provider for Anthropic")).toBeDisabled();
    await expect(page.getByLabel("Fallback model for OpenAI")).toBeDisabled();
    await expect(page.getByLabel("Fallback model for Anthropic")).toBeDisabled();
  });

  test("pair-only save persists across navigation and returns after eligibility is restored", async ({
    page,
  }) => {
    await applyFixture(
      [OPENAI_ENABLED, ANTHROPIC_ENABLED],
      {
        fallback_enabled: true,
        model_defaults: TWO_PROVIDER_DEFAULTS.model_defaults,
        fallback_map: [],
      },
    );

    const modelUpdateBodies: Array<Record<string, unknown>> = [];
    const onRequest = (request: Request) => {
      if (request.method() !== "PUT" || !request.url().includes("/api/settings/models/")) {
        return;
      }
      const body = request.postData();
      modelUpdateBodies.push(body ? (JSON.parse(body) as Record<string, unknown>) : {});
    };
    page.on("request", onRequest);

    await openModelsTab(page);

    await expect(page.getByLabel("Enable fallback")).toHaveAttribute("aria-checked", "true");
    await chooseSelectOption(page, "Fallback provider for OpenAI", "Anthropic");
    await expect(page.getByLabel("Fallback model for OpenAI")).toBeEnabled();
    expect(modelUpdateBodies).toHaveLength(0);

    await chooseSelectOption(page, "Fallback model for OpenAI", "claude-sonnet-4");

    await expect.poll(() => modelUpdateBodies.length).toBe(1);
    expect(modelUpdateBodies[0]).toEqual({
      fallback_provider_id: "anthropic",
      fallback_model_id: "claude-sonnet-4",
    });

    await expect.poll(async () => {
      const data = await apiGet<{
        items: Array<{
          id: string;
          fallback_provider_id: string | null;
          fallback_model_id: string | null;
        }>;
      }>("/settings/models");
      const openaiRow = data.items.find((item) => item.id === "openai");
      return `${openaiRow?.fallback_provider_id ?? "null"}|${openaiRow?.fallback_model_id ?? "null"}`;
    }).toBe("anthropic|claude-sonnet-4");

    await page.getByRole("tab", { name: "Providers" }).click();
    await page.getByRole("tab", { name: "Models" }).click();

    await expect(page.getByLabel("Fallback provider for OpenAI")).toContainText("Anthropic");
    await expect(page.getByLabel("Fallback model for OpenAI")).toContainText("claude-sonnet-4");

    await applyFixture(
      [OPENAI_ENABLED, ANTHROPIC_DISABLED],
      {
        fallback_enabled: true,
        model_defaults: TWO_PROVIDER_DEFAULTS.model_defaults,
        fallback_map: [
          {
            provider_id: "openai",
            fallback_provider_id: "anthropic",
            fallback_model_id: "claude-sonnet-4",
          },
        ],
      },
    );

    await openModelsTab(page);

    await expect(page.getByLabel("Enable fallback")).toBeDisabled();
    await expect(
      page.getByText("Enable at least two providers to configure fallback targets."),
    ).toBeVisible();
    await expect(page.getByLabel("Fallback provider for OpenAI")).toHaveCount(0);
    await expect(page.getByLabel("Fallback provider for Anthropic")).toHaveCount(0);

    await applyFixture(
      [OPENAI_ENABLED, ANTHROPIC_ENABLED],
      {
        fallback_enabled: true,
        model_defaults: TWO_PROVIDER_DEFAULTS.model_defaults,
        fallback_map: [
          {
            provider_id: "openai",
            fallback_provider_id: "anthropic",
            fallback_model_id: "claude-sonnet-4",
          },
        ],
      },
    );

    await openModelsTab(page);

    await expect(page.getByLabel("Enable fallback")).toHaveAttribute("aria-checked", "true");
    await expect(page.getByLabel("Fallback provider for OpenAI")).toContainText("Anthropic");
    await expect(page.getByLabel("Fallback model for OpenAI")).toContainText("claude-sonnet-4");

    page.off("request", onRequest);
  });
});
