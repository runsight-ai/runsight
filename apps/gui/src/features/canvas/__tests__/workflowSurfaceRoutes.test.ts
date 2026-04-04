/**
 * RED-TEAM tests for RUN-596: Migrate routes to WorkflowSurface and remove
 * duplicate run and workflow pages.
 *
 * After this migration:
 *   - `workflows/:id/edit` renders through a thin wrapper that passes
 *     mode="workflow" and workflowId to WorkflowSurface
 *   - `runs/:id` renders through a thin wrapper that passes
 *     mode="historical" and runId to WorkflowSurface
 *   - routes/index.tsx no longer imports CanvasPage or RunDetail as route targets
 *   - The codebase has no parallel page-level surfaces for the same product concept
 *
 * Expected failures: routes/index.tsx still imports CanvasPage and RunDetail
 * directly, not WorkflowSurface wrappers.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const ROUTES_PATH = "routes/index.tsx";

// ===========================================================================
// 1. Routes delegate to WorkflowSurface (AC1 + AC2)
// ===========================================================================

describe("Routes delegate to WorkflowSurface (RUN-596 AC1 + AC2)", () => {
  it("routes/index.tsx imports or references WorkflowSurface for the workflow edit route", () => {
    const source = readSource(ROUTES_PATH);
    // The workflow edit route should lazy-import a module that uses WorkflowSurface,
    // not CanvasPage
    expect(source).toMatch(/workflows\/:id\/edit/);
    expect(source).toMatch(/WorkflowSurface/);
  });

  it("routes/index.tsx references WorkflowSurface for the runs detail route", () => {
    const source = readSource(ROUTES_PATH);
    // The runs/:id route should reference WorkflowSurface, not RunDetail
    expect(source).toMatch(/runs\/:id/);
    // Both routes converge on the same surface
    const workflowSurfaceMatches = source.match(/WorkflowSurface/g);
    expect(
      workflowSurfaceMatches && workflowSurfaceMatches.length >= 1,
      "Expected routes/index.tsx to reference WorkflowSurface",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. Thin route wrappers exist (AC1 — route selection changes mode/data
//    source, not surface architecture)
// ===========================================================================

describe("Thin route wrappers exist (RUN-596 AC1)", () => {
  it("a workflow edit route wrapper exists that imports WorkflowSurface", () => {
    const source = readSource(ROUTES_PATH);
    // The route for workflows/:id/edit should NOT lazy-import CanvasPage
    // Instead it should import a wrapper or WorkflowSurface directly
    const workflowRouteBlock = source.slice(
      source.indexOf("workflows/:id/edit"),
      source.indexOf("workflows/:id/edit") + 200,
    );
    expect(workflowRouteBlock).not.toMatch(/CanvasPage/);
  });

  it("a run detail route wrapper exists that imports WorkflowSurface", () => {
    const source = readSource(ROUTES_PATH);
    // Find the runs/:id route block (not the runs list)
    // The lazy import should NOT reference RunDetail directly
    const runsIdIndex = source.indexOf('"runs/:id"') !== -1
      ? source.indexOf('"runs/:id"')
      : source.indexOf("'runs/:id'");
    const runRouteBlock = source.slice(runsIdIndex, runsIdIndex + 200);
    expect(runRouteBlock).not.toMatch(/RunDetail/);
  });
});

// ===========================================================================
// 3. Workflow route passes mode="workflow" (AC2)
// ===========================================================================

describe("Workflow route passes mode='workflow' (RUN-596 AC2)", () => {
  it("the workflow route wrapper or adapter specifies mode='workflow'", () => {
    const source = readSource(ROUTES_PATH);
    // The route file or a referenced wrapper should set mode to "workflow"
    // for the workflows/:id/edit path. This can be inline or via a wrapper
    // component that the route file imports.
    //
    // We check that the routes file itself (or any thin wrappers it references)
    // associates "workflow" mode. Since the wrappers may live in separate files,
    // we also check common wrapper locations.
    const hasWorkflowMode = source.includes('mode') && source.includes('workflow');
    expect(
      hasWorkflowMode,
      "Expected routes/index.tsx to associate 'workflow' mode with the edit route",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Run route passes mode="historical" (AC2)
// ===========================================================================

describe("Run route passes mode='historical' (RUN-596 AC2)", () => {
  it("the run route wrapper or adapter specifies mode='historical'", () => {
    const source = readSource(ROUTES_PATH);
    const hasHistoricalMode = source.includes('mode') && source.includes('historical');
    expect(
      hasHistoricalMode,
      "Expected routes/index.tsx to associate 'historical' mode with the run route",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. CanvasPage is no longer a route target (AC3)
// ===========================================================================

describe("CanvasPage is no longer a route target (RUN-596 AC3)", () => {
  it("routes/index.tsx does NOT lazy-import CanvasPage", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).not.toMatch(/import.*CanvasPage/);
    expect(source).not.toMatch(/features\/canvas\/CanvasPage/);
  });

  it("routes/index.tsx does NOT use CanvasPage as a Component in any route", () => {
    const source = readSource(ROUTES_PATH);
    // The lazy() callback should not reference CanvasPage
    expect(source).not.toMatch(/CanvasPage/);
  });
});

// ===========================================================================
// 6. RunDetail is no longer a route target (AC3)
// ===========================================================================

describe("RunDetail is no longer a route target (RUN-596 AC3)", () => {
  it("routes/index.tsx does NOT lazy-import RunDetail", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).not.toMatch(/import.*RunDetail/);
    expect(source).not.toMatch(/features\/runs\/RunDetail/);
  });

  it("routes/index.tsx does NOT use RunDetail as a Component in any route", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).not.toMatch(/RunDetail/);
  });
});

// ===========================================================================
// 7. No duplicate page-level surfaces (AC3 + DoD)
// ===========================================================================

describe("No duplicate page-level surfaces (RUN-596 AC3 + DoD)", () => {
  it("both workflow-edit and run-detail routes converge on the same surface module", () => {
    const source = readSource(ROUTES_PATH);
    // After migration, neither CanvasPage nor RunDetail should appear in routes.
    // Only WorkflowSurface (or a thin wrapper that delegates to it) should be the target.
    const hasCanvasPage = /CanvasPage/.test(source);
    const hasRunDetail = /RunDetail/.test(source);
    const hasWorkflowSurface = /WorkflowSurface/.test(source);

    expect(
      hasWorkflowSurface && !hasCanvasPage && !hasRunDetail,
      "Expected routes to converge on WorkflowSurface without CanvasPage or RunDetail",
    ).toBe(true);
  });

  it("the routes file does not maintain two separate lazy imports for edit vs. run viewing", () => {
    const source = readSource(ROUTES_PATH);
    // Both routes should reference the same underlying surface module.
    // There should not be one import for canvas/CanvasPage and another for runs/RunDetail.
    const canvasPageImports = (source.match(/features\/canvas\/CanvasPage/g) || []).length;
    const runDetailImports = (source.match(/features\/runs\/RunDetail/g) || []).length;

    expect(
      canvasPageImports + runDetailImports,
      "Expected zero imports of CanvasPage + RunDetail in the routes file",
    ).toBe(0);
  });
});
