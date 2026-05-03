import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: packages/ui public-export tests own package manifest smoke only.
 * Owner: packages/ui component public export coverage.
 * Boundary: package.json exports for package-local runtime surfaces; app
 * runtime import scanning belongs to apps/gui and Storybook coverage belongs
 * to src/stories/__tests__.
 * Exit criteria: remove this once package exports are generated from a typed
 * manifest.
 */

type PackageJson = {
  exports: Record<string, string>;
};

const packageJson = JSON.parse(
  readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "package.json"),
    "utf-8",
  ),
) as PackageJson;

const PUBLIC_EXPORT_SMOKE = [
  ["./styles.css", "./src/styles/globals.css"],
  ["./button", "./src/components/ui/button.tsx"],
  ["./badge", "./src/components/ui/badge.tsx"],
  ["./input", "./src/components/ui/input.tsx"],
  ["./table", "./src/components/ui/table.tsx"],
  ["./tabs", "./src/components/ui/tabs.tsx"],
] as const;

describe("package ui public export manifest smoke", () => {
  it.each(PUBLIC_EXPORT_SMOKE)("%s points at the package-owned runtime file", (subpath, target) => {
    expect(packageJson.exports[subpath]).toBe(target);
  });

  it("keeps package exports out of app, Storybook, and test workspaces", () => {
    for (const [subpath, target] of Object.entries(packageJson.exports)) {
      expect(`${subpath}:${target}`).not.toMatch(/apps\/gui|stories|__tests__/);
    }
  });
});
