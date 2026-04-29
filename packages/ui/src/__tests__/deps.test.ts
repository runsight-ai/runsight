/**
 * Dependency manifest contract checks for packages/ui.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

const pkgPath = join(__dirname, "../../package.json");
const pkg = JSON.parse(readFileSync(pkgPath, "utf-8")) as {
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
};

const allDeps = {
  ...pkg.dependencies,
  ...pkg.devDependencies,
};

describe("packages/ui dependency manifest", () => {
  it("does not depend on radix-ui umbrella packages", () => {
    const radixKeys = Object.keys(allDeps).filter((k) => k === "radix-ui" || k.startsWith("@radix-ui/"));
    expect(radixKeys, `Found radix-ui entries: ${radixKeys.join(", ")}`).toHaveLength(0);
  });

  it("does not depend on sonner", () => {
    expect(allDeps).not.toHaveProperty("sonner");
  });

  it("declares cmdk for command primitives", () => {
    expect(allDeps).toHaveProperty("cmdk");
  });
});
