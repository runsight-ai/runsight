import { expect } from "@playwright/test";
import type { Page, test as PlaywrightTest } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { stringify } from "yaml";

export const API = "http://localhost:8000/api";

export type ProviderFixture = {
  id: string;
  name: string;
  type: string;
  status: string;
  is_active: boolean;
  models?: string[];
  api_key?: string | null;
};

export type SettingsFixture = {
  onboarding_completed: boolean;
  fallback_enabled?: boolean;
};

export type WorkspaceSnapshot = {
  providerFiles: Map<string, string>;
  settingsContent: string | null;
};

const workspaceDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const repoRoot = path.resolve(workspaceDir, "..", "..");

const READY_PROVIDER: ProviderFixture = {
  id: "openai",
  name: "OpenAI",
  type: "openai",
  status: "connected",
  is_active: true,
  models: ["gpt-4.1-mini"],
  api_key: null,
};

export function buildBlankWorkflowYaml(id: string, name = "Untitled Workflow") {
  return stringify({
    version: "1.0",
    id,
    kind: "workflow",
    enabled: false,
    blocks: {},
    workflow: {
      name,
      entry: "start",
      transitions: [],
    },
  });
}

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

export async function apiGet<T>(apiPath: string): Promise<T> {
  const response = await fetch(`${API}${apiPath}`);
  expect(response.ok).toBe(true);
  return response.json() as Promise<T>;
}

export async function apiPost<T>(apiPath: string, body: unknown): Promise<T> {
  const response = await fetch(`${API}${apiPath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  expect(response.ok).toBe(true);
  return response.json() as Promise<T>;
}

export async function apiPut<T>(apiPath: string, body: unknown): Promise<T> {
  const response = await fetch(`${API}${apiPath}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  expect(response.ok).toBe(true);
  return response.json() as Promise<T>;
}

export async function apiDelete(apiPath: string): Promise<void> {
  const response = await fetch(`${API}${apiPath}`, { method: "DELETE" });
  expect(response.ok).toBe(true);
}

export async function captureWorkspace(): Promise<WorkspaceSnapshot> {
  const providerFiles = new Map<string, string>();
  for (const fileName of await listYamlFiles(providersDir)) {
    providerFiles.set(
      fileName,
      await readFile(path.join(providersDir, fileName), "utf-8"),
    );
  }

  return {
    providerFiles,
    settingsContent: await readOptionalFile(settingsFile),
  };
}

export async function restoreWorkspace(snapshot: WorkspaceSnapshot) {
  await mkdir(providersDir, { recursive: true });
  for (const fileName of await listYamlFiles(providersDir)) {
    await rm(path.join(providersDir, fileName));
  }
  for (const [fileName, content] of snapshot.providerFiles.entries()) {
    await writeFile(path.join(providersDir, fileName), content, "utf-8");
  }

  await mkdir(settingsDir, { recursive: true });
  if (snapshot.settingsContent === null) {
    await rm(settingsFile, { force: true });
  } else {
    await writeFile(settingsFile, snapshot.settingsContent, "utf-8");
  }
}

export async function seedProviders(providers: ProviderFixture[]) {
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

export async function seedSettings(settings: SettingsFixture) {
  await mkdir(settingsDir, { recursive: true });
  await writeFile(settingsFile, stringify(settings), "utf-8");
}

export async function applyFixture(
  providers: ProviderFixture[],
  settings: SettingsFixture,
) {
  await seedProviders(providers);
  await seedSettings(settings);

  await expect
    .poll(async () => {
      const data = await apiGet<{ items: Array<{ id: string }> }>("/settings/providers");
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

export function setupShellReadyWorkspace(
  testInstance: Pick<typeof PlaywrightTest, "beforeAll" | "afterAll">,
) {
  testInstance.beforeAll(async () => {
    await applyFixture([READY_PROVIDER], {
      onboarding_completed: true,
      fallback_enabled: false,
    });
  });

  testInstance.afterAll(async () => {});
}

export async function gotoShellRoute(page: Page, targetPath: string) {
  await page.goto(targetPath);
  await expect(page).not.toHaveURL(/\/setup\/start/);
  await page.waitForLoadState("networkidle");
}
