import { describe, expect, it } from "vitest";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";

const UI_ROOT = resolve(__dirname, "..", "..", "..", "..");
const PACKAGE_JSON_PATH = resolve(UI_ROOT, "package.json");
const STORIES_DIR = resolve(UI_ROOT, "src", "stories");
const UI_TESTS_DIR = resolve(UI_ROOT, "src", "components", "ui", "__tests__");
const GUI_SRC_DIR = resolve(UI_ROOT, "..", "..", "apps", "gui", "src");

function readFile(filePath: string) {
  return readFileSync(filePath, "utf8");
}

function readPackageJson(): {
  exports?: Record<string, string | { import?: string; default?: string }>;
} {
  return JSON.parse(readFile(PACKAGE_JSON_PATH));
}

function escapeForRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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

function getExportTarget(target: string | { import?: string; default?: string }) {
  if (typeof target === "string") {
    return target;
  }

  return target.import ?? target.default ?? null;
}

function getExplicitExportMap() {
  const exportsMap = readPackageJson().exports ?? {};

  return new Map(
    Object.entries(exportsMap)
      .filter(([subpath]) => subpath !== "./*" && subpath !== "./styles.css")
      .map(([subpath, target]) => [subpath, getExportTarget(target)]),
  );
}

function getGuiUiImportSubpaths() {
  const importPattern = /from\s+["']@runsight\/ui\/([^"']+)["']/g;

  return new Set(
    walkFiles(GUI_SRC_DIR)
      .filter((filePath) => /\.(ts|tsx)$/.test(filePath))
      .flatMap((filePath) => [...readFile(filePath).matchAll(importPattern)].map((match) => `./${match[1]}`)),
  );
}

function hasStoryCoverage(componentSubpath: string) {
  const storyName = `${componentSubpath.slice(2).split("-").map((part) => part[0]?.toUpperCase() + part.slice(1)).join("")}.stories.tsx`;

  return existsSync(resolve(STORIES_DIR, storyName));
}

function hasUiTestCoverage(componentSubpath: string) {
  const componentName = componentSubpath.slice(2);
  const componentFilename = `${componentName}.tsx`;
  const exactCoveragePatterns = [
    new RegExp(`from\\s+["'][^"']*${escapeForRegExp(componentName)}["']`),
    new RegExp(`readComponent\\(["']${escapeForRegExp(componentFilename)}["']\\)`),
    new RegExp(`componentExists\\(["']${escapeForRegExp(componentFilename)}["']\\)`),
    new RegExp(`readShared\\(["']${escapeForRegExp(componentFilename)}["']\\)`),
    new RegExp(`resolve\\([^\\n]*["']${escapeForRegExp(componentFilename)}["']`),
  ];

  return walkFiles(UI_TESTS_DIR)
    .filter((filePath) => /\.(ts|tsx)$/.test(filePath))
    .some((filePath) => exactCoveragePatterns.some((pattern) => pattern.test(readFile(filePath))));
}

describe("RUN-514 explicit design-system surface", () => {
  it("does not leave the supported public surface on an unbounded wildcard export", () => {
    const exportsMap = readPackageJson().exports ?? {};

    expect(
      exportsMap["./*"],
      "Expected packages/ui/package.json to replace the implicit ./* export with explicit retained exports",
    ).toBeUndefined();
  });

  it("explicitly exports every @runsight/ui subpath used by product runtime code", () => {
    const explicitExports = getExplicitExportMap();
    const runtimeImports = getGuiUiImportSubpaths();
    const missingRuntimeExports = [...runtimeImports].filter((subpath) => !explicitExports.has(subpath));

    expect(
      missingRuntimeExports,
      [
        "Expected every @runsight/ui subpath used by apps/gui runtime code to be explicitly exported from packages/ui/package.json.",
        `Missing explicit exports for: ${missingRuntimeExports.join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
  });
});

describe("RUN-514 retained vs unsupported public exports", () => {
  it("allows non-runtime exports to remain only when they have intentional story or test coverage", () => {
    const explicitExports = getExplicitExportMap();
    const runtimeImports = getGuiUiImportSubpaths();
    const unsupportedExplicitExports = [...explicitExports.keys()].filter((subpath) => {
      if (!subpath.startsWith("./") || subpath === "./empty-state" || subpath === "./utils") {
        return false;
      }

      if (runtimeImports.has(subpath)) {
        return false;
      }

      return !hasStoryCoverage(subpath) && !hasUiTestCoverage(subpath);
    });

    expect(
      unsupportedExplicitExports,
      [
        "Expected non-runtime public exports to stay only when they have story or test coverage.",
        `Unsupported explicit exports: ${unsupportedExplicitExports.join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
  });

  it("does not leave key-value public only through the implicit wildcard surface", () => {
    const exportsMap = readPackageJson().exports ?? {};
    const explicitExports = getExplicitExportMap();
    const hasWildcard = "./*" in exportsMap;
    const hasExplicitKeyValueExport = explicitExports.has("./key-value");
    const keyValueHasCoverage = hasStoryCoverage("./key-value") || hasUiTestCoverage("./key-value");

    expect(keyValueHasCoverage).toBe(true);
    expect(
      hasWildcard && !hasExplicitKeyValueExport,
      "Expected key-value to be either explicitly retained under the supported surface rule or removed from the public surface altogether",
    ).toBe(false);
  });
});
