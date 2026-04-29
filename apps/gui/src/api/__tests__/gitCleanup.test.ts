/**
 * Source-level git client checks for static API client imports.
 */

import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";

const source = readFileSync(new URL("../git.ts", import.meta.url), "utf-8");

describe("git.ts static import enforcement", () => {
  test("git.ts imports the API client statically", () => {
    expect(source).toMatch(/import\s*\{\s*api\s*\}\s*from\s*["']\.\/client["']/);
  });

  test("git.ts does not load the API client through dynamic import", () => {
    expect(source).not.toContain("await import(");
  });

  test("git.ts no longer carries the static-import migration helper", () => {
    expect(source).not.toContain("ensureStaticClientImport");
  });
});
