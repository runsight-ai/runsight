import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { stringify } from "yaml";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";
const workspaceDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(workspaceDir, "../..");

type ProviderFixture = {
  id: string;
  name: string;
  type: string;
  status: string;
  is_active: boolean;
  models?: string[];
  api_key?: string | null;
};

type SettingsFixture = {
  onboarding_completed: boolean;
  fallback_enabled?: boolean;
};

type WorkflowDetail = {
  id: string;
  name: string;
  yaml?: string | null;
};

const READY_PROVIDER: ProviderFixture = {
  id: "openai",
  name: "OpenAI",
  type: "openai",
  status: "connected",
  is_active: true,
  models: ["gpt-4.1-mini"],
  api_key: null,
};

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

let originalProviderFiles = new Map<string, string>();
let originalSettingsContent: string | null = null;
const createdWorkflowIds = new Set<string>();

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

async function apiDelete(apiPath: string): Promise<void> {
  await fetch(`${API}${apiPath}`, { method: "DELETE" });
}

async function snapshotWorkspace() {
  originalProviderFiles = new Map<string, string>();
  for (const fileName of await listYamlFiles(providersDir)) {
    originalProviderFiles.set(
      fileName,
      await readFile(path.join(providersDir, fileName), "utf-8"),
    );
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
        models: provider.models ?? [],
        api_key: provider.api_key ?? null,
      }),
      "utf-8",
    );
  }
}

async function seedSettings(settings: SettingsFixture) {
  await mkdir(settingsDir, { recursive: true });
  await writeFile(settingsFile, stringify(settings), "utf-8");
}

async function applyFixture(providers: ProviderFixture[], settings: SettingsFixture) {
  await seedProviders(providers);
  await seedSettings(settings);

  await expect
    .poll(async () => {
      const data = await apiGet<{ items: Array<{ id: string }>; total: number }>("/settings/providers");
      return data.items.map((provider) => provider.id).sort().join(",");
    })
    .toBe(providers.map((provider) => provider.id).sort().join(","));

  await expect
    .poll(async () => {
      const data = await apiGet<{ onboarding_completed?: boolean }>("/settings/app");
      return data.onboarding_completed;
    })
    .toBe(settings.onboarding_completed);
}

function extractWorkflowIdFromUrl(page: Page): string {
  const match = page.url().match(/\/workflows\/([^/]+)\/edit(?:\?|$)/);
  expect(match).not.toBeNull();
  return match![1];
}

async function expectEditorRoute(page: Page) {
  await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit(?:\?.*)?$/, { timeout: 15_000 });
}

test.beforeAll(async () => {
  await snapshotWorkspace();
});

test.afterEach(async () => {
  for (const workflowId of createdWorkflowIds) {
    await apiDelete(`/workflows/${workflowId}`);
  }
  createdWorkflowIds.clear();
});

test.afterAll(async () => {
  await restoreWorkspace();
});

test.describe("Onboarding journeys", () => {
  test("first visit with no providers redirects into setup and creates the template in explore mode", async ({
    page,
  }) => {
    await applyFixture([], { onboarding_completed: false });

    await page.goto("/");

    await expect(page).toHaveURL(/\/setup\/start$/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "How do you want to start?" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "Start with a template" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByText("Explore mode")).toBeVisible();
    await expect(page.getByText("Add an API key in Settings to run this workflow")).toBeVisible();

    await page.getByRole("button", { name: "Start Building" }).click();

    await expectEditorRoute(page);
    const workflowId = extractWorkflowIdFromUrl(page);
    createdWorkflowIds.add(workflowId);

    await expect(page.getByRole("button", { name: "Add API Key" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Run" })).toHaveCount(0);

    const workflow = await apiGet<WorkflowDetail>(`/workflows/${workflowId}`);
    expect(workflow.name).toBe("Research & Review");
    expect(workflow.yaml).toContain("quality_gate:");
    expect(workflow.yaml).toContain("draft_report:");
    expect(workflow.yaml).toContain("write_error_stub:");

    const settings = await apiGet<{ onboarding_completed?: boolean }>("/settings/app");
    expect(settings.onboarding_completed).toBe(true);
  });

  test("blank-canvas onboarding creates an untitled workflow and preserves the explore-mode run gate", async ({
    page,
  }) => {
    await applyFixture([], { onboarding_completed: false });

    await page.goto("/setup/start");

    const blankCard = page.getByRole("radio", { name: "Start with a blank canvas" });
    await blankCard.click();
    await expect(blankCard).toHaveAttribute("aria-checked", "true");

    await page.getByRole("button", { name: "Start Building" }).click();

    await expectEditorRoute(page);
    const workflowId = extractWorkflowIdFromUrl(page);
    createdWorkflowIds.add(workflowId);

    await expect(page.getByRole("button", { name: "Add API Key" })).toBeVisible();

    const workflow = await apiGet<WorkflowDetail>(`/workflows/${workflowId}`);
    expect(workflow.name).toBe("Untitled Workflow");
    expect(workflow.yaml).toContain(`id: ${workflowId}`);
    expect(workflow.yaml).toContain("kind: workflow");
  });

  test("provider-present onboarding shows ready-to-run state and redirects setup away after completion", async ({
    page,
  }) => {
    await applyFixture([READY_PROVIDER], { onboarding_completed: false });

    await page.goto("/setup/start");

    await expect(page.getByText("Ready to run").first()).toBeVisible();
    await expect(page.getByText("Explore mode")).toHaveCount(0);

    await page.getByRole("button", { name: "Start Building" }).click();

    await expectEditorRoute(page);
    const workflowId = extractWorkflowIdFromUrl(page);
    createdWorkflowIds.add(workflowId);

    await expect(page.getByRole("button", { name: "Run" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add API Key" })).toHaveCount(0);

    await page.goto("/setup/start");
    await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "Home" }).first()).toBeVisible();
  });
});
