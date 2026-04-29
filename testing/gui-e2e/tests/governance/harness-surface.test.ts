/**
 * Governance coverage for the Playwright harness surface.
 *
 * These are pure filesystem/config checks, not browser flows. They protect the
 * testing/gui-e2e workspace boundary and should stay here until equivalent
 * lint rules own the same constraints.
 */

import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Path helpers
// ---------------------------------------------------------------------------

// __dirname = testing/gui-e2e/tests/governance
const workspaceDir = path.resolve(__dirname, "../..");

// repoRoot = two levels above workspaceDir (testing/gui-e2e -> testing -> repo root)
const repoRoot = path.resolve(workspaceDir, "../..");
const SOURCE_OWNED_ROOTS = ["apps", "packages", "testing", "tools"];

function workspacePath(...segments: string[]): string {
  return path.join(workspaceDir, ...segments);
}

function workspaceFileExists(...segments: string[]): boolean {
  return fs.existsSync(workspacePath(...segments));
}

function readWorkspaceFile(...segments: string[]): string {
  return fs.readFileSync(workspacePath(...segments), "utf8");
}

function findFilesNamed(
  rootDir: string,
  fileName: string,
  matches: string[] = [],
): string[] {
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

function findSourceOwnedFilesNamed(fileName: string): string[] {
  return SOURCE_OWNED_ROOTS.flatMap((rootName) => {
    const rootDir = path.join(repoRoot, rootName);
    if (!fs.existsSync(rootDir)) {
      return [];
    }
    return findFilesNamed(rootDir, fileName);
  });
}

function hasConfiguredPath(
  config: string,
  configKey: string,
  filePath: string,
): boolean {
  const escapedPath = filePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const configPattern = new RegExp(
    `${configKey}\\s*:\\s*["'\`](?:\\./)?${escapedPath}["'\`]`,
  );
  return configPattern.test(config);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Playwright harness surface", () => {
  it("global setup and teardown helpers are either wired in Playwright config or removed", () => {
    const config = readWorkspaceFile("playwright.config.ts");

    const dormantGlobals = [
      ["global-setup.ts", "globalSetup"],
      ["global-teardown.ts", "globalTeardown"],
    ]
      .filter(
        ([file, configKey]) =>
          workspaceFileExists(file) &&
          !hasConfiguredPath(config, configKey, file),
      )
      .map(
        ([file, configKey]) =>
          `${file} exists without ${configKey} in playwright.config.ts`,
      );

    expect(dormantGlobals).toEqual([]);
  });

  it("review screenshot helpers do not remain without an active entrypoint", () => {
    const dormantScreenshotHelpers = [
      "scripts/screenshot.cjs",
      "scripts/screenshot-impl.cjs",
    ]
      .filter((file) => workspaceFileExists(file))
      .map((file) => `${file} should be deleted`);

    expect(dormantScreenshotHelpers).toEqual([]);
  });

  it("README only documents retained harness entrypoints", () => {
    const readme = readWorkspaceFile("README.md");
    const config = readWorkspaceFile("playwright.config.ts");
    const scriptFiles = workspaceFileExists("scripts")
      ? fs
          .readdirSync(workspacePath("scripts"))
          .map((file) => `scripts/${file}`)
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
      ["`scripts/`", readme.includes("`scripts/`") && scriptFiles.length > 0],
    ]
      .filter(([, isMisleading]) => isMisleading)
      .map(([label]) => label);

    expect(misleadingClaims).toEqual([]);
  });

  it("Playwright harness entrypoints do not reappear outside testing/gui-e2e", () => {
    const harnessEntrypoints = [
      "global-setup.ts",
      "global-teardown.ts",
      "screenshot.cjs",
      "screenshot-impl.cjs",
    ];

    const misplacedEntrypoints = harnessEntrypoints.flatMap((fileName) =>
      findSourceOwnedFilesNamed(fileName).filter(
        (relativePath) => !relativePath.startsWith("testing/gui-e2e/"),
      ),
    );

    expect(misplacedEntrypoints).toEqual([]);
  });
});
