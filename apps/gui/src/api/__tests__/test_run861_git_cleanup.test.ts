/**
 * Red tests for RUN-861: Fix git.ts dynamic import pattern and CORS port mismatch.
 *
 * These tests inspect the source of git.ts to enforce static import conventions.
 * All three tests should FAIL until the green implementation is written.
 */

import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";

const source = readFileSync(new URL("../git.ts", import.meta.url), "utf-8");

describe("RUN-861: git.ts static import enforcement", () => {
  test("test_git_uses_static_import — git.ts contains static import { api } from", () => {
    expect(source).toMatch(/import\s*\{\s*api\s*\}\s*from\s*["']\.\/client["']/);
  });

  test("test_no_dynamic_imports_in_git — git.ts does not contain await import(", () => {
    expect(source).not.toContain("await import(");
  });

  test("test_no_ensure_static_client_import — git.ts does not contain ensureStaticClientImport", () => {
    expect(source).not.toContain("ensureStaticClientImport");
  });
});
