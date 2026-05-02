import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const UI_ROOT = resolve(__dirname, "..", "..", "..", "..");
const PACKAGE_JSON_PATH = resolve(UI_ROOT, "package.json");

function readFile(filePath: string) {
  return readFileSync(filePath, "utf8");
}

function readPackageJson(): {
  exports?: Record<string, string | { import?: string; default?: string }>;
} {
  return JSON.parse(readFile(PACKAGE_JSON_PATH));
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

describe("explicit design-system surface", () => {
  it("does not leave the supported public surface on an unbounded wildcard export", () => {
    const exportsMap = readPackageJson().exports ?? {};

    expect(
      exportsMap["./*"],
      "Expected packages/ui/package.json to replace the implicit ./* export with explicit retained exports",
    ).toBeUndefined();
  });
});

describe("retained vs unsupported public exports", () => {
  it("keeps every retained component export explicit", () => {
    const explicitExports = getExplicitExportMap();
    const componentExportsWithoutTargets = [...explicitExports.entries()]
      .filter(([subpath]) => subpath !== "./utils")
      .filter(([, target]) => !target);

    expect(
      componentExportsWithoutTargets,
      [
        "Expected retained component public exports to resolve through explicit package-owned targets.",
        `Exports without explicit targets: ${componentExportsWithoutTargets.map(([subpath]) => subpath).join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
  });

  it("does not leave key-value public only through the implicit wildcard surface", () => {
    const exportsMap = readPackageJson().exports ?? {};
    const explicitExports = getExplicitExportMap();
    const hasWildcard = "./*" in exportsMap;
    const hasExplicitKeyValueExport = explicitExports.has("./key-value");

    expect(hasExplicitKeyValueExport).toBe(true);
    expect(
      hasWildcard && !hasExplicitKeyValueExport,
      "Expected key-value to be either explicitly retained under the supported surface rule or removed from the public surface altogether",
    ).toBe(false);
  });
});
