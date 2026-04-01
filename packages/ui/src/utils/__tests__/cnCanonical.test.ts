import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cn } from "../helpers";

const UI_ROOT = resolve(__dirname, "..", "..", "..");
const PACKAGE_JSON_PATH = resolve(UI_ROOT, "package.json");
const CANONICAL_HELPER_PATH = resolve(UI_ROOT, "src", "utils", "helpers.ts");

function readFile(filePath: string) {
  return readFileSync(filePath, "utf8");
}

function readPackageJson(): {
  exports?: Record<string, string>;
} {
  return JSON.parse(readFile(PACKAGE_JSON_PATH));
}

describe("RUN-513 canonical ui helper ownership", () => {
  it("keeps the canonical cn implementation in packages/ui", () => {
    expect(existsSync(CANONICAL_HELPER_PATH)).toBe(true);
    expect(readFile(CANONICAL_HELPER_PATH)).toMatch(/export\s+(?:function|const)\s+cn\b/);
  });

  it("exports cn through a simple package path for cross-workspace consumers", () => {
    const packageJson = readPackageJson();

    expect(packageJson.exports).toBeDefined();
    expect(
      packageJson.exports?.["./helpers"],
      "Expected packages/ui/package.json to expose the canonical cn helper via @runsight/ui/helpers",
    ).toBe("./src/utils/helpers.ts");
  });
});

describe("RUN-513 cn behavior stability", () => {
  it("merges conflicting tailwind utility classes with the last value winning", () => {
    expect(cn("px-2", "px-4", "text-sm")).toBe("px-4 text-sm");
  });

  it("preserves clsx-style conditional and nested inputs for existing consumers", () => {
    expect(
      cn("inline-flex", ["items-center", false && "hidden"], {
        "font-medium": true,
        hidden: false,
      }),
    ).toBe("inline-flex items-center font-medium");
  });
});
