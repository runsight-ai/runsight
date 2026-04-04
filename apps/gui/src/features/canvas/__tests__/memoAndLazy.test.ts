/**
 * RED-TEAM tests for RUN-241: CanvasNode React.memo + Monaco lazy loading.
 *
 * These tests verify:
 * 1. CanvasNode in RunDetail.tsx is wrapped with React.memo (not plain assignment)
 * 2. React.memo has a custom comparator checking data.name, data.status, data.stepType
 * 3. LazyMonacoEditor.tsx exists and uses React.lazy()
 * 4. LazyMonacoEditor.tsx wraps the lazy component in Suspense
 * 5. LazyMonacoEditor.tsx shows "Loading editor" placeholder during load
 * 6. LazyMonacoEditor.tsx imports from @monaco-editor/react
 *
 * All tests are expected to FAIL against the current implementation because:
 * - RunDetail.tsx uses plain assignment `const CanvasNode = CanvasNodeComponent;`
 * - LazyMonacoEditor.tsx does not exist yet
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
// 1. CanvasNode React.memo in RunDetail.tsx
// ===========================================================================

describe("CanvasNode React.memo (RUN-241)", () => {
  const source = readSource("features/runs/RunDetail.tsx");

  it("wraps CanvasNode with memo() instead of plain assignment", () => {
    // Current code: `const CanvasNode = CanvasNodeComponent;`
    // Expected:     `const CanvasNode = memo(CanvasNodeComponent` (with optional comparator)
    expect(source).toMatch(/const\s+CanvasNode\s*=\s*memo\s*\(\s*CanvasNodeComponent/);
  });

  it("does NOT use plain assignment for CanvasNode", () => {
    // The plain assignment pattern should be gone
    const plainAssignment = /const\s+CanvasNode\s*=\s*CanvasNodeComponent\s*;/;
    expect(source).not.toMatch(plainAssignment);
  });

  it("passes a custom comparator as second argument to memo", () => {
    // memo(CanvasNodeComponent, <comparator>) — there should be a comma after CanvasNodeComponent
    // followed by a function (arrow or named)
    expect(source).toMatch(
      /memo\s*\(\s*CanvasNodeComponent\s*,\s*(function|\()/,
    );
  });

  it("comparator checks data.name", () => {
    // The comparator function should reference data.name for shallow comparison
    // Look for a pattern like `prev.data.name` or destructured equivalent
    expect(source).toMatch(/\.data\.name/);
  });

  it("comparator checks data.status", () => {
    expect(source).toMatch(/\.data\.status/);
  });

  it("comparator checks data.stepType", () => {
    expect(source).toMatch(/\.data\.stepType/);
  });

  it("imports memo from react", () => {
    expect(source).toMatch(/import\s+\{[^}]*\bmemo\b[^}]*\}\s+from\s+["']react["']/);
  });
});

// ===========================================================================
// 2. Monaco lazy loading — LazyMonacoEditor.tsx
// ===========================================================================

describe("LazyMonacoEditor — lazy Monaco loading (RUN-241)", () => {
  it("LazyMonacoEditor.tsx file exists", () => {
    expect(fileExists("features/canvas/LazyMonacoEditor.tsx")).toBe(true);
  });

  // All remaining tests in this describe will fail with a read error if file
  // doesn't exist, which is the desired RED behaviour.
  describe("source contents", () => {
    let source: string;

    try {
      source = readSource("features/canvas/LazyMonacoEditor.tsx");
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
