import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const workspaceDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(workspaceDir, "../..");

function workspacePath(...segments: string[]) {
  return path.join(workspaceDir, ...segments);
}

function workspaceFileExists(...segments: string[]) {
  return fs.existsSync(workspacePath(...segments));
}

function readWorkspaceFile(...segments: string[]) {
  return fs.readFileSync(workspacePath(...segments), "utf8");
}

function findFilesNamed(rootDir: string, fileName: string, matches: string[] = []) {
  for (const entry of fs.readdirSync(rootDir, { withFileTypes: true })) {
    if (
      entry.name === "node_modules" ||
      entry.name === ".git" ||
      entry.name === "playwright-report" ||
      entry.name === "test-results"
    ) {
      continue;
    }

    const fullPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      findFilesNamed(fullPath, fileName, matches);
      continue;
    }

    if (entry.isFile() && entry.name === fileName) {
      matches.push(path.relative(repoRoot, fullPath));
    }
  }

  return matches;
}

function hasConfiguredPath(config: string, configKey: string, filePath: string) {
  const escapedPath = filePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const configPattern = new RegExp(
    `${configKey}\\s*:\\s*["'\`](?:\\./)?${escapedPath}["'\`]`
  );

  return configPattern.test(config);
}

function hasAnyConfiguredPath(config: string, filePath: string) {
  const escapedPath = filePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const configPattern = new RegExp(`:\\s*["'\`](?:\\./)?${escapedPath}["'\`]`);

  return configPattern.test(config);
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
          workspaceFileExists(file) && !hasConfiguredPath(config, configKey, file)
      )
      .map(
        ([file, configKey]) =>
          `${file} exists without ${configKey} in playwright.config.ts`
      );

    expect(dormantGlobals).toEqual([]);
  });

  test("review screenshot helpers do not remain without an active entrypoint", () => {
    const config = readWorkspaceFile("playwright.config.ts");

    const dormantScreenshotHelpers = [
      "scripts/screenshot.cjs",
      "scripts/screenshot-impl.cjs",
    ]
      .filter((file) => workspaceFileExists(file))
      .filter((file) => !hasAnyConfiguredPath(config, file))
      .map(
        (file) =>
          `${file} exists without a Playwright config reference`
      );

    expect(dormantScreenshotHelpers).toEqual([]);
  });

  test("README only documents retained harness entrypoints", () => {
    const readme = readWorkspaceFile("README.md");
    const config = readWorkspaceFile("playwright.config.ts");
    const scriptFiles = workspaceFileExists("scripts")
      ? fs.readdirSync(workspacePath("scripts")).map((file) => `scripts/${file}`)
      : [];

    const misleadingClaims = [
      [
        "`global-setup.ts`",
        readme.includes("`global-setup.ts`") &&
          workspaceFileExists("global-setup.ts") &&
          !hasConfiguredPath(config, "globalSetup", "global-setup.ts"),
      ],
      [
        "`global-teardown.ts`",
        readme.includes("`global-teardown.ts`") &&
          workspaceFileExists("global-teardown.ts") &&
          !hasConfiguredPath(config, "globalTeardown", "global-teardown.ts"),
      ],
      [
        "`scripts/`",
        readme.includes("`scripts/`") &&
          scriptFiles.length > 0 &&
          scriptFiles.every((file) => !hasAnyConfiguredPath(config, file)),
      ],
    ]
      .filter(([, isMisleading]) => isMisleading)
      .map(([label]) => label);

    expect(misleadingClaims).toEqual([]);
  });

  test("Playwright harness entrypoints do not reappear outside testing/gui-e2e", () => {
    const harnessEntrypoints = [
      "global-setup.ts",
      "global-teardown.ts",
      "screenshot.cjs",
      "screenshot-impl.cjs",
    ];

    const misplacedEntrypoints = harnessEntrypoints.flatMap((fileName) =>
      findFilesNamed(repoRoot, fileName).filter(
        (relativePath) => !relativePath.startsWith("testing/gui-e2e/")
      )
    );

    expect(misplacedEntrypoints).toEqual([]);
  });
});
