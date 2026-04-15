/**
 * RED-TEAM tests for RUN-851: Decompose WorkflowSurface god component (520+ lines)
 *
 * WorkflowSurface.tsx is currently 659 lines (component body 522 lines) with:
 *   - 13 useState hooks
 *   - 8 useEffect hooks
 *   - Mixed concerns: mode management, canvas hydration, overlay YAML fetching,
 *     readonly YAML fetching, run status polling, node status mapping,
 *     commit dialog, inspector panel, API key modal
 *
 * These tests verify structural properties of the code after the refactor:
 * 1. Five custom hooks are extracted and importable
 * 2. The main component body is ≤80 non-blank, non-comment lines
 * 3. The main component has ≤5 useState and ≤3 useEffect calls
 * 4. Behavioral regression guards (WorkflowSurface is still exported + callable)
 *
 * Test groups 1, 2, and 3 FAIL against the current implementation.
 * Test group 4 PASSES now and must continue to pass after the refactor.
 *
 * Do NOT import React or render components — all assertions are structural/import-only.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ===========================================================================
// 1. Custom hook extraction — each import will fail (module not found) until
//    the hook files are created by the Green team.
// ===========================================================================

describe("RUN-851: Custom hook extraction", () => {
  it("useOverlayYaml hook exists and is exported", async () => {
    const mod = await import("../useOverlayYaml");
    expect(typeof mod.useOverlayYaml).toBe("function");
  });

  it("useReadonlyRunYaml hook exists and is exported", async () => {
    const mod = await import("../useReadonlyRunYaml");
    expect(typeof mod.useReadonlyRunYaml).toBe("function");
  });

  it("useCanvasHydration hook exists and is exported", async () => {
    const mod = await import("../useCanvasHydration");
    expect(typeof mod.useCanvasHydration).toBe("function");
  });

  it("useRunStatusSync hook exists and is exported", async () => {
    const mod = await import("../useRunStatusSync");
    expect(typeof mod.useRunStatusSync).toBe("function");
  });

  it("useNodeStatusMapping hook exists and is exported", async () => {
    const mod = await import("../useNodeStatusMapping");
    expect(typeof mod.useNodeStatusMapping).toBe("function");
  });
});

// ===========================================================================
// 2. Main component thinness — component body must be ≤80 non-blank,
//    non-comment lines after decomposition.
//    Currently FAILS: the component body has ~520 lines of logic.
// ===========================================================================

describe("RUN-851: Main component thinness", () => {
  it("WorkflowSurface component body is ≤80 lines of logic", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");

    // Capture from `export function WorkflowSurface` to the matching closing `}` at column 0.
    // The `^}` in multiline mode anchors to a `}` that starts the line.
    const match = source.match(/export function WorkflowSurface\b[\s\S]*?^}/m);
    expect(match).not.toBeNull();

    const componentSource = match![0];
    const logicLines = componentSource.split("\n").filter((line) => {
      const trimmed = line.trim();
      return (
        trimmed.length > 0
        && !trimmed.startsWith("//")
        && !trimmed.startsWith("*")
        && !trimmed.startsWith("/*")
      );
    });

    expect(logicLines.length).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 3. Hook count reduction — extracted hooks must remove useState / useEffect
//    calls from the main component body.
//    Currently FAILS: 13 useState + 8 useEffect in component body.
// ===========================================================================

describe("RUN-851: Hook reduction in main component", () => {
  it("WorkflowSurface has ≤5 useState calls", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");

    const match = source.match(/export function WorkflowSurface\b[\s\S]*?^}/m);
    expect(match).not.toBeNull();

    const useStateCount = (match![0].match(/useState[<(]/g) ?? []).length;
    expect(useStateCount).toBeLessThanOrEqual(5);
  });

  it("WorkflowSurface has ≤3 useEffect calls", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");

    const match = source.match(/export function WorkflowSurface\b[\s\S]*?^}/m);
    expect(match).not.toBeNull();

    const useEffectCount = (match![0].match(/useEffect\(/g) ?? []).length;
    expect(useEffectCount).toBeLessThanOrEqual(3);
  });
});

// ===========================================================================
// 4. Behavioral regression guards — these PASS now and must still pass after
//    the refactor. If any of these fail post-refactor, the refactor broke the
//    public contract.
//
//    All checks use source inspection (readFileSync) rather than dynamic import
//    so they work without a jsdom/bundler environment. The file still uses React
//    internals that require a DOM context to fully resolve at import time.
// ===========================================================================

describe("RUN-851: Behavioral preservation", () => {
  it("WorkflowSurface.tsx still exports the WorkflowSurface function", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");
    // Must export the function by name (not just re-export)
    expect(source).toMatch(/export function WorkflowSurface\b/);
  });

  it("WorkflowSurface.tsx accepts the standard WorkflowSurfaceProps shape", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");
    // Props signature must still reference mode, workflowId, runId
    expect(source).toMatch(/WorkflowSurfaceProps/);
    expect(source).toMatch(/\bmode\b/);
    expect(source).toMatch(/\bworkflowId\b/);
  });

  it("WorkflowSurface.tsx still imports CommitDialog", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");
    expect(source).toMatch(/CommitDialog/);
  });

  it("WorkflowSurface.tsx still imports SurfaceInspectorPanel", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");
    expect(source).toMatch(/SurfaceInspectorPanel/);
  });

  it("WorkflowSurface.tsx still references ProviderModal (API key modal)", () => {
    const filePath = resolve(__dirname, "..", "WorkflowSurface.tsx");
    const source = readFileSync(filePath, "utf-8");
    expect(source).toMatch(/ProviderModal/);
  });
});
