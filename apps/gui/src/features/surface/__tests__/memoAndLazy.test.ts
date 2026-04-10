/**
 * RED-TEAM tests for RUN-241: SurfaceYamlEditor Monaco lazy loading.
 *
 * These tests verify:
 * 1. SurfaceYamlEditor.tsx exists and uses React.lazy()
 * 2. SurfaceYamlEditor.tsx wraps the lazy component in Suspense
 * 3. SurfaceYamlEditor.tsx shows "Loading editor" placeholder during load
 * 4. SurfaceYamlEditor.tsx imports from @monaco-editor/react
 *
 * All tests are expected to FAIL against the current implementation because:
 * - SurfaceYamlEditor.tsx does not exist yet
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readSource(relativePath: string): string {
  const root = resolve(__dirname, "..", "..", "..");
  return readFileSync(resolve(root, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  try {
    const root = resolve(__dirname, "..", "..", "..");
    readFileSync(resolve(root, relativePath), "utf-8");
    return true;
  } catch {
    return false;
  }
}

// ===========================================================================
// 1. Monaco lazy loading — LazyMonacoEditor.tsx
// ===========================================================================

describe("SurfaceYamlEditor — lazy Monaco loading (RUN-241)", () => {
  it("SurfaceYamlEditor.tsx file exists", () => {
    expect(fileExists("features/surface/SurfaceYamlEditor.tsx")).toBe(true);
  });

  // All remaining tests in this describe will fail with a read error if file
  // doesn't exist, which is the desired RED behaviour.
  describe("source contents", () => {
    let source: string;

    try {
      source = readSource("features/surface/SurfaceYamlEditor.tsx");
    } catch {
      // File doesn't exist yet — set source to empty so assertions fail clearly
      source = "";
    }

    it("uses React.lazy or lazy() to defer-load Monaco", () => {
      expect(source).toMatch(/(?:React\.lazy|lazy)\s*\(/);
    });

    it("uses Suspense to wrap the lazy component", () => {
      expect(source).toMatch(/Suspense/);
    });

    it('shows "Loading editor" placeholder text in the fallback', () => {
      expect(source).toMatch(/Loading editor/i);
    });

    it("imports from @monaco-editor/react", () => {
      expect(source).toMatch(/@monaco-editor\/react/);
    });

    it("exports a component (default or named)", () => {
      expect(source).toMatch(/export\s+(default\s+)?(?:function|const|class)\s+\w+/);
    });
  });
});
