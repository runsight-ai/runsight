/**
 * RED-TEAM tests for RUN-565: Workflow Edit — Regressions tab in bottom panel.
 *
 * Source-reading pattern: verify structural acceptance criteria by reading
 * source files and asserting observable properties.
 *
 * AC1: Regressions tab added to CanvasBottomPanel
 * AC2: Shows all regressions across all runs of the current workflow
 * AC3: Tab label includes count badge
 * AC4: Tab hidden when 0 regressions
 * AC5: PriorityBanner on CanvasPage wired with REGRESSIONS condition
 * AC6: Per-issue rows show node name, type, delta, run #
 *
 * Expected failures (current state):
 *   - CanvasBottomPanel has no "Regressions" tab — only "Logs" and "Runs"
 *   - No useWorkflowRegressions call in CanvasBottomPanel
 *   - No regressions count badge in tab label
 *   - No conditional hiding when count is 0
 *   - CanvasPage bannerConditions array has no "regressions" entry
 *   - No per-issue rows with node name, type, delta, run #
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

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const CANVAS_BOTTOM_PANEL_PATH = "features/canvas/CanvasBottomPanel.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. Regressions tab added to CanvasBottomPanel (AC1)
// ===========================================================================

describe("Regressions tab added to CanvasBottomPanel (AC1)", () => {
  it("CanvasBottomPanel has a Regressions tab button", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // There should be a tab containing the word "Regressions"
    expect(source).toMatch(/Regressions/);
  });

  it("Regressions tab has role=tab for accessibility", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Count role="tab" elements — should be at least 3 (Logs + Runs + Regressions)
    const tabMatches = source.match(/role\s*=\s*["']tab["']/g) || [];
    expect(
      tabMatches.length,
      "Expected at least 3 tab elements (Logs + Runs + Regressions)",
    ).toBeGreaterThanOrEqual(3);
  });

  it("activeTab state type includes regressions variant", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // The activeTab state should include "regressions" as a valid value
    expect(source).toMatch(/["']regressions["']/);
  });
});

// ===========================================================================
// 2. Shows all regressions across all runs (AC2)
// ===========================================================================

describe("Shows all regressions across all runs (AC2)", () => {
  it("CanvasBottomPanel imports useWorkflowRegressions hook", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/import.*useWorkflowRegressions.*from/);
  });

  it("CanvasBottomPanel calls useWorkflowRegressions with workflowId", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/useWorkflowRegressions\s*\(/);
  });

  it("renders regressions content panel when tab is active", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should conditionally render a regressions list when the regressions tab is active
    const hasRegressionsPanel =
      /activeTab\s*===\s*["']regressions["']/.test(source);
    expect(
      hasRegressionsPanel,
      "Expected conditional render for regressions tab content",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Tab label includes count badge (AC3)
// ===========================================================================

describe("Tab label includes count badge (AC3)", () => {
  it("Regressions tab label includes dynamic count", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Tab label should be "Regressions (N)" with a dynamic count value
    // e.g. Regressions ({count}) or Regressions (${count})
    const hasDynamicCount =
      /Regressions\s*\(\s*\{|Regressions\s*\(\s*\$\{|`Regressions \(/.test(
        source,
      );
    expect(
      hasDynamicCount,
      'Expected tab label like "Regressions (N)" with dynamic count',
    ).toBe(true);
  });

  it("count value comes from regressions data", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should reference count or items.length from the regressions response
    const hasCountRef =
      /regressions.*\.count|regressions.*\.items.*\.length|regressionsData.*\.count/.test(
        source,
      );
    expect(
      hasCountRef,
      "Expected count derived from regressions API response",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Tab hidden when 0 regressions (AC4)
// ===========================================================================

describe("Tab hidden when 0 regressions (AC4)", () => {
  it("Regressions tab is conditionally rendered based on count", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // The tab button should only render when there are regressions (count > 0)
    // Look for conditional rendering patterns around the regressions tab
    const hasConditionalTab =
      /count\s*>\s*0.*Regressions|items\.length\s*>\s*0.*Regressions|regressions.*&&.*Regressions|count\s*>\s*0\s*&&|items\.length\s*>\s*0\s*&&/.test(
        source,
      );
    expect(
      hasConditionalTab,
      "Expected regressions tab to be conditionally hidden when count is 0",
    ).toBe(true);
  });

  it("does not show regressions tab when data is loading or empty", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should guard against undefined/null data from the hook
    const hasNullGuard =
      /regressions.*\?\.|regressionsData\?\.|count\s*!=\s*null|count\s*!==\s*undefined/.test(
        source,
      );
    expect(
      hasNullGuard,
      "Expected null/undefined guard on regressions data before rendering tab",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. PriorityBanner on CanvasPage wired with REGRESSIONS condition (AC5)
// ===========================================================================

describe("PriorityBanner wired with REGRESSIONS condition (AC5)", () => {
  it("CanvasPage imports useWorkflowRegressions hook", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import.*useWorkflowRegressions.*from/);
  });

  it("CanvasPage calls useWorkflowRegressions", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/useWorkflowRegressions\s*\(/);
  });

  it('bannerConditions includes a regressions entry with type "regressions"', () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The bannerConditions array should include a condition with type: "regressions"
    // alongside the existing "explore" and "uncommitted" conditions
    const hasRegressionsCondition =
      /type:\s*["']regressions["']/.test(source);
    expect(
      hasRegressionsCondition,
      'Expected bannerConditions to include type: "regressions"',
    ).toBe(true);
  });

  it("regressions banner condition has an active flag based on count", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The regressions condition active flag should be based on count > 0
    const hasActiveFlag =
      /regressions.*active\s*:|active.*regressions.*count|count\s*>\s*0/.test(
        source,
      );
    expect(
      hasActiveFlag,
      "Expected regressions banner condition to have active flag based on count",
    ).toBe(true);
  });

  it("regressions banner condition has a descriptive message", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The message should describe the regressions count
    const hasMessage =
      /regressions.*message\s*:|regression.*detected|regression.*found/.test(
        source,
      );
    expect(
      hasMessage,
      "Expected regressions banner condition to have a user-facing message",
    ).toBe(true);
  });
});

// ===========================================================================
// 6. Per-issue rows show node name, type, delta, run # (AC6)
// ===========================================================================

describe("Per-issue rows show node name, type, delta, run # (AC6)", () => {
  it("renders node_name for each regression row", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Each regression row should display the node name
    const hasNodeName = /node_name|nodeName/.test(source);
    expect(
      hasNodeName,
      "Expected node_name field rendered in regression rows",
    ).toBe(true);
  });

  it("renders regression type (assertion, cost_spike, latency_spike)", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Each row should display the regression type
    const hasType = /\.type|regression.*type|assertion|cost_spike|latency_spike/.test(source);
    // Must specifically reference it in the regressions context, not just generic .type
    // We check for at least one of the regression type enum values or a .type accessor
    // alongside regression-related code
    expect(
      hasType,
      "Expected regression type rendered in regression rows",
    ).toBe(true);
  });

  it("renders delta summary for each regression row", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Each row should display the delta (delta_pct or formatted delta)
    const hasDelta = /delta_pct|delta|deltaPct/.test(source);
    expect(
      hasDelta,
      "Expected delta_pct or delta summary rendered in regression rows",
    ).toBe(true);
  });

  it("renders run number for each regression row", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Each row should display the run number/id
    const hasRunRef = /run_number|run_id|runNumber|run\s*#|run_seq/.test(source);
    expect(
      hasRunRef,
      "Expected run number/id rendered in regression rows",
    ).toBe(true);
  });

  it("renders a warning icon for each regression row", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Each row should have a warning icon (AlertTriangle from lucide or unicode ⚠)
    const hasWarningIcon =
      /AlertTriangle|TriangleAlert|\u26a0|warning.*icon|icon.*warning/.test(
        source,
      );
    expect(
      hasWarningIcon,
      "Expected warning icon (AlertTriangle or similar) in regression rows",
    ).toBe(true);
  });
});
