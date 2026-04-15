/**
 * RUN-862: Verify dependency manifest correctness for packages/ui.
 *
 * These tests read package.json directly — no runtime imports, no install required.
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

describe("RUN-862 packages/ui dependency manifest", () => {
  it("test_no_radix_in_ui_deps — radix-ui must not appear in package.json", () => {
    const radixKeys = Object.keys(allDeps).filter((k) => k === "radix-ui" || k.startsWith("@radix-ui/"));
    expect(radixKeys, `Found radix-ui entries: ${radixKeys.join(", ")}`).toHaveLength(0);
  });

  it("test_no_sonner_in_ui_deps — sonner must not appear in package.json", () => {
    expect(allDeps).not.toHaveProperty("sonner");
  });

  it("test_no_cmdk_in_ui_deps — cmdk must not appear in package.json", () => {
    expect(allDeps).not.toHaveProperty("cmdk");
  });
});
