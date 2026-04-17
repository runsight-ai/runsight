import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(configDir, "../..");
const e2eProjectRoot = path.join(configDir, ".runtime");

process.env.RUNSIGHT_BASE_PATH = e2eProjectRoot;
process.env.RUNSIGHT_E2E_PROJECT_ROOT = e2eProjectRoot;

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["html", { outputFolder: "./playwright-report", open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      name: "api",
      command:
        "bash -lc 'rm -rf \"$RUNSIGHT_BASE_PATH\" && uv run python -c \"import os, subprocess; from pathlib import Path; from runsight_api.core.project import scaffold_project; base = Path(os.environ[\\\"RUNSIGHT_BASE_PATH\\\"]); base.mkdir(parents=True, exist_ok=True); scaffold_project(base); subprocess.run([\\\"git\\\", \\\"branch\\\", \\\"-M\\\", \\\"main\\\"], cwd=base, check=True)\" && uv run runsight --host 127.0.0.1 --port 8000'",
      cwd: repoRoot,
      env: {
        RUNSIGHT_BASE_PATH: e2eProjectRoot,
        RUNSIGHT_E2E_PROJECT_ROOT: e2eProjectRoot,
      },
      url: "http://localhost:8000/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      name: "gui",
      command: "pnpm -C ../../apps/gui dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
