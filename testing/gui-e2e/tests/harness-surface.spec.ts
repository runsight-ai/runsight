import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const workspaceDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function workspacePath(...segments: string[]) {
  return path.join(workspaceDir, ...segments);
}

function workspaceFileExists(...segments: string[]) {
  return fs.existsSync(workspacePath(...segments));
}

function readWorkspaceFile(...segments: string[]) {
  return fs.readFileSync(workspacePath(...segments), "utf8");
}

function readPackageScripts() {
  const packageJson = JSON.parse(readWorkspaceFile("package.json")) as {
    scripts?: Record<string, string>;
  };

  return Object.values(packageJson.scripts ?? {});
}

test.describe("Playwright harness surface", () => {
  test("global setup and teardown helpers are either wired in Playwright config or removed", () => {
    const config = readWorkspaceFile("playwright.config.ts");

    const dormantGlobals = [
      ["global-setup.ts", "globalSetup"],
      ["global-teardown.ts", "globalTeardown"],
    ]
      .filter(
        ([file, configKey]) =>
          workspaceFileExists(file) && !config.includes(configKey)
      )
      .map(
        ([file, configKey]) =>
          `${file} exists without ${configKey} in playwright.config.ts`
      );

    expect(dormantGlobals).toEqual([]);
  });

  test("review screenshot helpers do not remain without an active entrypoint", () => {
    const config = readWorkspaceFile("playwright.config.ts");
    const packageScripts = readPackageScripts();

    const dormantScreenshotHelpers = [
      "scripts/screenshot.cjs",
      "scripts/screenshot-impl.cjs",
    ]
      .filter((file) => workspaceFileExists(file))
      .filter(
        (file) =>
          !config.includes(file) &&
          !packageScripts.some((command) => command.includes(file))
      )
      .map(
        (file) =>
          `${file} exists without a Playwright config reference or package.json script`
      );

    expect(dormantScreenshotHelpers).toEqual([]);
  });

  test("README only documents retained harness entrypoints", () => {
    const readme = readWorkspaceFile("README.md");
    const config = readWorkspaceFile("playwright.config.ts");
    const packageScripts = readPackageScripts();
    const scriptFiles = workspaceFileExists("scripts")
      ? fs.readdirSync(workspacePath("scripts")).map((file) => `scripts/${file}`)
      : [];

    const misleadingClaims = [
      [
        "`global-setup.ts`",
        readme.includes("`global-setup.ts`") &&
          workspaceFileExists("global-setup.ts") &&
          !config.includes("globalSetup"),
      ],
      [
        "`global-teardown.ts`",
        readme.includes("`global-teardown.ts`") &&
          workspaceFileExists("global-teardown.ts") &&
          !config.includes("globalTeardown"),
      ],
      [
        "`scripts/`",
        readme.includes("`scripts/`") &&
          scriptFiles.length > 0 &&
          scriptFiles.every(
            (file) => !packageScripts.some((command) => command.includes(file))
          ),
      ],
    ]
      .filter(([, isMisleading]) => isMisleading)
      .map(([label]) => label);

    expect(misleadingClaims).toEqual([]);
  });
});
