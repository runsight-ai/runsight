import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { relative, resolve } from "node:path";

const GUI_SRC_DIR = resolve(__dirname, "..", "..");
const GUI_ROOT = resolve(GUI_SRC_DIR, "..");
const WORKTREE_ROOT = resolve(GUI_ROOT, "..", "..");
const UI_PACKAGE_JSON_PATH = resolve(WORKTREE_ROOT, "packages", "ui", "package.json");

function readFile(filePath: string) {
  return readFileSync(filePath, "utf8");
}

function walkFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const fullPath = resolve(directory, entry);
    const stats = statSync(fullPath);

    if (stats.isDirectory()) {
      return walkFiles(fullPath);
    }

    return [fullPath];
  });
}

function readUiPackageJson(): {
  exports?: Record<string, string | { import?: string; default?: string }>;
} {
  return JSON.parse(readFile(UI_PACKAGE_JSON_PATH));
}

function collectGuiUiImports() {
  const importPattern = /from\s+["']@runsight\/ui\/([^"']+)["']/g;

  return walkFiles(GUI_SRC_DIR)
    .filter((filePath) => /\.(ts|tsx)$/.test(filePath) && !/\.test\.tsx?$/.test(filePath))
    .flatMap((filePath) =>
      [...readFile(filePath).matchAll(importPattern)].map((match) => ({
        filePath,
        subpath: `./${match[1]}`,
      })),
    );
}

function getExplicitUiExports() {
  const exportsMap = readUiPackageJson().exports ?? {};

  return new Set(Object.keys(exportsMap).filter((subpath) => subpath !== "./*" && subpath !== "./styles.css"));
}

describe("RUN-514 GUI runtime uses supported @runsight/ui exports", () => {
  it("does not rely on a wildcard ui export for product runtime imports", () => {
    const wildcardExport = readUiPackageJson().exports?.["./*"];

    expect(
      wildcardExport,
      "Expected packages/ui to stop exposing product runtime imports through a wildcard-only surface",
    ).toBeUndefined();
  });

  it("uses only explicit retained @runsight/ui exports for product runtime imports", () => {
    const explicitUiExports = getExplicitUiExports();
    const unsupportedImports = collectGuiUiImports().filter(({ subpath }) => !explicitUiExports.has(subpath));

    expect(
      unsupportedImports.map(({ filePath, subpath }) => `${relative(GUI_ROOT, filePath)} -> ${subpath}`),
      [
        "Expected every @runsight/ui import used by apps/gui to resolve through an explicit retained export.",
        `Imports missing explicit retained exports: ${unsupportedImports.map(({ filePath, subpath }) => `${relative(GUI_ROOT, filePath)} -> ${subpath}`).join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
  });
});
