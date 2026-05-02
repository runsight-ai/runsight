/**
 * Compact governance coverage for the Playwright harness workspace surface.
 *
 * Boundary: testing/gui-e2e owns its active harness entrypoints and docs.
 * Exit criteria: replace with repo-level tooling once harness entrypoints are
 * declared in a typed manifest.
 */

import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const workspaceDir = path.resolve(__dirname, "../..");

function workspacePath(...segments: string[]): string {
  return path.join(workspaceDir, ...segments);
}

function workspaceFileExists(...segments: string[]): boolean {
  return fs.existsSync(workspacePath(...segments));
}

function readWorkspaceFile(...segments: string[]): string {
  return fs.readFileSync(workspacePath(...segments), "utf8");
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

describe("Playwright harness surface smoke", () => {
  it("keeps retained workspace entrypoints wired or absent", () => {
    const config = readWorkspaceFile("playwright.config.ts");
    const readme = readWorkspaceFile("README.md");
    const scriptFiles = workspaceFileExists("scripts")
      ? fs.readdirSync(workspacePath("scripts")).map((file) => `scripts/${file}`)
      : [];

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

    const orphanedReviewHelpers = [
      "scripts/screenshot.cjs",
      "scripts/screenshot-impl.cjs",
    ].filter((file) => workspaceFileExists(file));

    const misleadingReadmeClaims = [
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

    expect({
      dormantGlobals,
      orphanedReviewHelpers,
      misleadingReadmeClaims,
    }).toEqual({
      dormantGlobals: [],
      orphanedReviewHelpers: [],
      misleadingReadmeClaims: [],
    });
  });
});
