import { describe, expect, it } from "vitest";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { relative, resolve } from "node:path";

const GUI_SRC_ROOT = resolve(__dirname, "..", "..");
const GUI_ROOT = resolve(GUI_SRC_ROOT, "..");
const LOCAL_DUPLICATE_HELPER_PATHS = [
  resolve(GUI_SRC_ROOT, "lib", "utils.ts"),
  resolve(GUI_SRC_ROOT, "utils", "helpers.ts"),
];
const DISALLOWED_GUI_IMPORT_PATHS = ["@/utils/helpers", "@/lib/utils"];

function readFile(filePath: string) {
  return readFileSync(filePath, "utf8");
}

function listSourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const fullPath = resolve(directory, entry);
    const stats = statSync(fullPath);

    if (stats.isDirectory()) {
      return listSourceFiles(fullPath);
    }

    if (!/\.(ts|tsx)$/.test(fullPath) || /\.test\.tsx?$/.test(fullPath)) {
      return [];
    }

    return [fullPath];
  });
}

function collectCnImports() {
  const importPattern = /import\s+(?:type\s+)?([\s\S]*?)\s+from\s+["']([^"']+)["'];?/g;

  return listSourceFiles(GUI_SRC_ROOT).flatMap((filePath) => {
    const source = readFile(filePath);

    return [...source.matchAll(importPattern)]
      .filter(([, clause]) => /\bcn\b/.test(clause))
      .map(([, clause, importPath]) => ({
        filePath,
        importClause: clause.trim(),
        importPath,
      }));
  });
}

function findDuplicateCnExports() {
  return LOCAL_DUPLICATE_HELPER_PATHS.filter((filePath) => {
    if (!existsSync(filePath)) {
      return false;
    }

    return /export\s+(?:function|const)\s+cn\b/.test(readFile(filePath));
  });
}

function isUiOwnedImportPath(importPath: string) {
  return /^@runsight\/ui(?:\/|$)/.test(importPath);
}

describe("RUN-513 GUI cn import convergence", () => {
  it("moves GUI cn consumers onto a packages/ui-owned import path", () => {
    const cnImports = collectCnImports();
    const localImports = cnImports.filter(({ importPath }) =>
      DISALLOWED_GUI_IMPORT_PATHS.includes(importPath),
    );
    const uiOwnedImports = cnImports.filter(({ importPath }) => isUiOwnedImportPath(importPath));

    expect(
      localImports,
      [
        "Expected GUI cn consumers to stop importing from local helper paths.",
        `Found local cn imports: ${localImports
          .map(({ filePath, importPath }) => `${relative(GUI_ROOT, filePath)} -> ${importPath}`)
          .join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
    expect(
      uiOwnedImports.length,
      "Expected GUI cn consumers to use a packages/ui-owned import path",
    ).toBeGreaterThan(0);
    expect(uiOwnedImports).toHaveLength(cnImports.length);
  });
});

describe("RUN-513 GUI duplicate helper removal", () => {
  it("removes the duplicate apps/gui cn helper exports from steady-state code", () => {
    const duplicateExports = findDuplicateCnExports();

    expect(
      duplicateExports.map((filePath) => relative(GUI_ROOT, filePath)),
      [
        "Expected apps/gui duplicate cn helpers to be deleted or stop exporting cn.",
        `Still exporting cn from: ${duplicateExports.map((filePath) => relative(GUI_ROOT, filePath)).join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
  });
});
