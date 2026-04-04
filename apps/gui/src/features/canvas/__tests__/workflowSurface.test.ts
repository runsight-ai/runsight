/**
 * RED-TEAM tests for RUN-592: Build one WorkflowSurface component for
 * workflow and run.
 *
 * This ticket creates the single page-level `WorkflowSurface` component
 * that replaces the separate CanvasPage (workflow editor) and RunDetail
 * (run viewer) with one shared surface driven by WorkflowSurfaceMode.
 *
 * Tests verify:
 * 1. WorkflowSurface.tsx exists and exports a named component
 * 2. Accepts WorkflowSurfaceProps (mode, workflowId, optional runId)
 * 3. Renders all 6 layout slots: topbar, palette, center, inspector,
 *    bottom panel, status bar — using data-testid attributes
 * 4. Mode-driven rendering: palette active/dimmed, canvas editable/
 *    read-only, bottom panel collapsed/expanded per mode
 * 5. Single identifier: workflow mode needs only workflowId, historical
 *    needs both workflowId and runId
 * 6. No separate page architectures: one component, not a wrapper
 *    around CanvasPage + RunDetail
 * 7. Route integration: routes delegate to WorkflowSurface
 *
 * Expected failures: WorkflowSurface.tsx does not exist yet.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const WORKFLOW_SURFACE_PATH = "features/canvas/WorkflowSurface.tsx";
const CONTRACT_PATH = "features/canvas/workflowSurfaceContract.ts";

// ===========================================================================
// 1. WorkflowSurface component exists and is exported (AC1)
// ===========================================================================

describe("WorkflowSurface component exists (RUN-592)", () => {
  it("WorkflowSurface.tsx file exists", () => {
    expect(
      fileExists(WORKFLOW_SURFACE_PATH),
      "Expected features/canvas/WorkflowSurface.tsx to exist",
    ).toBe(true);
  });

  it("exports a named WorkflowSurface component", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+WorkflowSurface/);
  });

  it("is a single component, not a re-export barrel", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Must contain JSX return (actual rendering), not just re-exports
    expect(source).toMatch(/return\s*\(/);
  });
});

// ===========================================================================
// 2. Accepts WorkflowSurfaceProps from the contract (AC2)
// ===========================================================================

describe("WorkflowSurface accepts WorkflowSurfaceProps (RUN-592)", () => {
  it("imports WorkflowSurfaceProps from workflowSurfaceContract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/import.*WorkflowSurfaceProps.*from.*workflowSurfaceContract/);
  });

  it("imports WorkflowSurfaceMode from workflowSurfaceContract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/import.*WorkflowSurfaceMode.*from.*workflowSurfaceContract/);
  });

  it("imports getContractForMode to derive panel rules", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/import.*getContractForMode.*from.*workflowSurfaceContract/);
  });

  it("component signature accepts props matching WorkflowSurfaceProps", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should accept { mode, workflowId, runId? } either via destructuring or typed param
    const hasPropsType =
      /WorkflowSurfaceProps/.test(source) &&
      (/mode/.test(source) && /workflowId/.test(source));
    expect(
      hasPropsType,
      "Expected component to use WorkflowSurfaceProps with mode and workflowId",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Renders all 6 layout slots with data-testid (AC1, DoD)
// ===========================================================================

describe("WorkflowSurface renders all layout slots (RUN-592)", () => {
  it("renders a topbar slot with data-testid", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/data-testid=["']surface-topbar["']/);
  });

  it("renders a palette sidebar slot with data-testid", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/data-testid=["']surface-palette["']/);
  });

  it("renders a center/main slot with data-testid", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/data-testid=["']surface-center["']/);
  });

  it("renders an inspector slot with data-testid", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/data-testid=["']surface-inspector["']/);
  });

  it("renders a bottom panel slot with data-testid", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/data-testid=["']surface-bottom-panel["']/);
  });

  it("renders a status bar slot with data-testid", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/data-testid=["']surface-status-bar["']/);
  });
});

// ===========================================================================
// 4. Mode-driven rendering (AC2 — shared composition, mode-driven density)
// ===========================================================================

describe("WorkflowSurface mode-driven rendering (RUN-592)", () => {
  it("calls getContractForMode with the current mode", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/getContractForMode\s*\(\s*mode\s*\)/);
  });

  it("passes palette dimmed state derived from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should reference palette.dimmed or contract.palette.dimmed
    const hasPaletteDimmed =
      /palette\.dimmed|dimmed/.test(source) && /contract|palette/i.test(source);
    expect(
      hasPaletteDimmed,
      "Expected palette dimmed state to be derived from mode contract",
    ).toBe(true);
  });

  it("passes canvas draggable/connectable state derived from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should reference canvas.draggable or isDraggable or contract.canvas
    const hasCanvasFlags =
      /draggable|isDraggable|connectionsAllowed|canCreateConnections/.test(source);
    expect(
      hasCanvasFlags,
      "Expected canvas draggable/connectable flags derived from mode contract",
    ).toBe(true);
  });

  it("passes bottom panel default state derived from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasBottomPanelState =
      /bottomPanel\.defaultState|getBottomPanelDefault|defaultState/.test(source);
    expect(
      hasBottomPanelState,
      "Expected bottom panel default state derived from mode contract",
    ).toBe(true);
  });

  it("passes inspector trigger derived from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasInspectorTrigger =
      /inspector\.trigger|getInspectorTrigger|trigger/.test(source);
    expect(
      hasInspectorTrigger,
      "Expected inspector trigger derived from mode contract",
    ).toBe(true);
  });

  it("passes topbar name-editable state derived from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasNameEditable =
      /topbar\.nameEditable|nameEditable/.test(source);
    expect(
      hasNameEditable,
      "Expected topbar name-editable state derived from mode contract",
    ).toBe(true);
  });

  it("passes status bar format derived from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasStatusBarFormat =
      /stepCountFormat|getStepCountFormat|metricsVisibility|getMetricsVisibility/.test(source);
    expect(
      hasStatusBarFormat,
      "Expected status bar format derived from mode contract",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Single identifier handling (edge cases)
// ===========================================================================

describe("WorkflowSurface identifier handling (RUN-592 edge cases)", () => {
  it("does not require runId in component props (optional)", () => {
    // Verify the contract defines runId as optional
    const contractSource = readSource(CONTRACT_PATH);
    expect(contractSource).toMatch(/runId\?\s*:\s*string/);
  });

  it("component handles presence or absence of runId", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should reference runId with optional chaining or conditional
    const handlesOptionalRunId =
      /runId/.test(source);
    expect(
      handlesOptionalRunId,
      "Expected WorkflowSurface to handle optional runId",
    ).toBe(true);
  });

  it("component always requires workflowId", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // workflowId should be used without optional chaining — it's required
    expect(source).toMatch(/workflowId/);
  });
});

// ===========================================================================
// 6. No separate page architectures (AC1, AC3)
// ===========================================================================

describe("WorkflowSurface is the single surface (RUN-592 AC1 + AC3)", () => {
  it("does NOT import CanvasPage as a child", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // WorkflowSurface must not wrap or delegate to the old CanvasPage
    expect(source).not.toMatch(/import.*from.*['"]\.\/(CanvasPage|\.\.\/canvas\/CanvasPage)['"]/);
  });

  it("does NOT import RunDetail as a child", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // WorkflowSurface must not wrap or delegate to the old RunDetail
    expect(source).not.toMatch(/import.*from.*['"]\.\.\/(runs\/RunDetail|RunDetail)['"]/);
  });

  it("does NOT conditionally render CanvasPage or RunDetail based on mode", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Must not have <CanvasPage or <RunDetail in JSX
    expect(source).not.toMatch(/<CanvasPage/);
    expect(source).not.toMatch(/<RunDetail/);
  });

  it("uses a single layout structure, not mode-switched page components", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should have ONE grid/flex layout, not two different layouts toggled by mode
    const gridOrFlexCount = (source.match(/className=.*grid|className=.*flex/g) || []).length;
    // There should be layout classes (proving it renders its own layout)
    expect(gridOrFlexCount).toBeGreaterThan(0);
  });
});

// ===========================================================================
// 7. Shared layout includes all child components (DoD — covers topbar,
//    main surface, inspector slot, footer, status bar)
// ===========================================================================

describe("WorkflowSurface shared layout includes child components (RUN-592 DoD)", () => {
  it("renders a topbar component (CanvasTopbar or equivalent)", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should render some topbar — either CanvasTopbar or a new SurfaceTopbar
    const hasTopbar = /Topbar|topbar/i.test(source) && /<[A-Z].*Topbar/.test(source);
    expect(
      hasTopbar,
      "Expected a topbar component to be rendered in WorkflowSurface layout",
    ).toBe(true);
  });

  it("renders a palette sidebar component", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasPalette = /<[A-Z].*Palette|<[A-Z].*Sidebar/.test(source);
    expect(
      hasPalette,
      "Expected a palette/sidebar component to be rendered",
    ).toBe(true);
  });

  it("renders a canvas or editor in the center area", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasCenter = /<[A-Z].*Canvas|<[A-Z].*Editor|ReactFlow/.test(source);
    expect(
      hasCenter,
      "Expected a canvas or editor component in the center area",
    ).toBe(true);
  });

  it("renders an inspector panel", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasInspector = /<[A-Z].*Inspector/.test(source);
    expect(
      hasInspector,
      "Expected an inspector panel component to be rendered",
    ).toBe(true);
  });

  it("renders a bottom panel", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasBottomPanel = /<[A-Z].*BottomPanel|<[A-Z].*Bottom/.test(source);
    expect(
      hasBottomPanel,
      "Expected a bottom panel component to be rendered",
    ).toBe(true);
  });

  it("renders a status bar", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasStatusBar = /<[A-Z].*StatusBar|<[A-Z].*Status/.test(source);
    expect(
      hasStatusBar,
      "Expected a status bar component to be rendered",
    ).toBe(true);
  });
});

// ===========================================================================
// 8. Route integration — routes can delegate to WorkflowSurface (DoD)
// ===========================================================================

describe("Route wrappers can delegate to WorkflowSurface (RUN-592 DoD)", () => {
  it("WorkflowSurface is exported as a named export (usable by route wrappers)", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Named export — not just default export — so route adapters can import it
    expect(source).toMatch(/export\s+(function|const)\s+WorkflowSurface/);
  });

  it("WorkflowSurface does NOT read route params directly (receives props from wrappers)", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The surface component should receive props from thin route wrappers,
    // not call useParams itself — that's the wrapper's job
    expect(source).not.toMatch(/useParams/);
  });
});

// ===========================================================================
// 9. Canvas/YAML toggle follows mode contract (DoD — shared surface)
// ===========================================================================

describe("Canvas/YAML toggle is mode-aware (RUN-592)", () => {
  it("imports or references canvas/YAML toggle visibility from contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasToggleVisibility =
      /getCanvasYamlToggleVisibility|canvasYamlToggle|toggleVisibility/.test(source);
    expect(
      hasToggleVisibility,
      "Expected canvas/YAML toggle to be controlled by mode contract",
    ).toBe(true);
  });
});

// ===========================================================================
// 10. Design system compliance — shared layout tokens
// ===========================================================================

describe("WorkflowSurface uses design system layout tokens (RUN-592)", () => {
  it("uses grid or flex layout for the surface", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hasLayout = /grid|flex/.test(source);
    expect(
      hasLayout,
      "Expected grid or flex layout in WorkflowSurface",
    ).toBe(true);
  });

  it("does NOT use hardcoded hex or rgba colors", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const hexMatches = source.match(/#[0-9a-fA-F]{3,8}\b/g);
    expect(hexMatches).toBeNull();
    expect(source).not.toMatch(/rgba?\s*\(\s*\d+/);
  });
});
