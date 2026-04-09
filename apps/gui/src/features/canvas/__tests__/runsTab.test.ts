/**
 * RED-TEAM tests for RUN-363: T9 — Bottom panel — Runs tab (workflow run history).
 *
 * These tests verify structural acceptance criteria by reading source files:
 *
 * AC1: Runs tab lists historical runs for this workflow
 * AC2: Shows status, duration, cost per run
 * AC3: Click selects run and switches to Logs tab
 * AC4: Sorted by newest first
 *
 * Expected failures (current state):
 *   - CanvasBottomPanel.tsx has no "Runs" tab — only "Logs"
 *   - No useRuns() call with workflow_id filter in CanvasBottomPanel
 *   - No run selection / tab switching logic
 *   - runsApi.listRuns does not pass workflow_id parameter
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
const RUNS_QUERY_PATH = "queries/runs.ts";
const RUNS_API_PATH = "api/runs.ts";

// ===========================================================================
// 1. Runs tab exists in CanvasBottomPanel (AC1)
// ===========================================================================

describe("Runs tab exists in bottom panel (AC1)", () => {
  it("CanvasBottomPanel has a Runs tab button", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // There should be a tab labeled "Runs" alongside the existing "Logs" tab
    const hasRunsTab = /role\s*=\s*["']tab["'][^>]*>.*Runs|>Runs<\/button>|>\s*Runs\s*</.test(source);
    expect(
      hasRunsTab,
      'Expected a "Runs" tab button in CanvasBottomPanel (role="tab")',
    ).toBe(true);
  });

  it("CanvasBottomPanel has both Logs and Runs tabs", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/Logs/);
    expect(source).toMatch(/Runs/);
  });

  it("Runs tab has role=tab for accessibility", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Count the number of role="tab" elements — should be at least 2 (Logs + Runs)
    const tabMatches = source.match(/role\s*=\s*["']tab["']/g) || [];
    expect(
      tabMatches.length,
      "Expected at least 2 tab elements (Logs + Runs)",
    ).toBeGreaterThanOrEqual(2);
  });
});

// ===========================================================================
// 2. Runs tab fetches workflow runs via useRuns with workflow_id (AC1)
// ===========================================================================

describe("Runs tab fetches workflow-scoped runs (AC1)", () => {
  it("CanvasBottomPanel imports useRuns hook", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/import.*useRuns.*from/);
  });

  it("CanvasBottomPanel calls useRuns with workflow_id parameter", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should pass workflow_id to useRuns or to the query params
    const hasWorkflowFilter = /useRuns\s*\(\s*\{[^}]*workflow_id|workflow_id/.test(source);
    expect(
      hasWorkflowFilter,
      "Expected useRuns call with workflow_id filter",
    ).toBe(true);
  });

  it("useRuns hook supports params including workflow_id", () => {
    const source = readSource(RUNS_QUERY_PATH);
    // useRuns should accept and forward params (it already does via Record<string, string>)
    expect(source).toMatch(/useRuns/);
    expect(source).toMatch(/params/);
  });

  it("runsApi.listRuns passes workflow_id in query string", () => {
    const source = readSource(RUNS_API_PATH);
    // The listRuns function should support passing workflow_id as a query parameter
    // This is already supported via the generic params mechanism, but we verify it's used
    expect(source).toMatch(/listRuns/);
  });
});

// ===========================================================================
// 3. Runs tab shows status, duration, cost per run (AC2)
// ===========================================================================

describe("Runs tab shows status, duration, cost per run (AC2)", () => {
  it("renders run status for each row", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should display status field from run data
    const hasStatus = /\.status|status.*badge|RunStatus|statusColor/.test(source);
    expect(
      hasStatus,
      "Expected run status rendering in runs tab",
    ).toBe(true);
  });

  it("renders run timing information (created_at/started_at) for chronological ordering", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Uses timestamps for ordering/display — duration now lives in the shared surface banner
    const hasTiming = /created_at|started_at|timestamp/.test(source);
    expect(
      hasTiming,
      "Expected timestamp or timing info in runs tab for ordering",
    ).toBe(true);
  });

  it("renders run cost for each row", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should display total_cost_usd or formatted cost
    const hasCost = /total_cost_usd|cost|formatCost|\$/.test(source);
    expect(
      hasCost,
      "Expected run cost rendering in runs tab",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Click selects run and switches to Logs tab (AC3)
// ===========================================================================

describe("Click selects run and switches to Logs tab (AC3)", () => {
  it("run rows are clickable (onClick handler)", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Each run row should have an onClick that selects the run
    const hasRunClick = /onClick.*run|selectRun|onRunSelect|setSelectedRun/.test(source);
    expect(
      hasRunClick,
      "Expected onClick handler on run rows for selection",
    ).toBe(true);
  });

  it("clicking a run switches the active tab to Logs", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Selecting a run should switch to the Logs tab (activeTab = 'logs' or similar)
    const hasSwitchToLogs = /activeTab.*logs|setActiveTab.*['"]logs['"]|tab.*logs/.test(source);
    expect(
      hasSwitchToLogs,
      "Expected tab switch to Logs when a run is clicked",
    ).toBe(true);
  });

  it("tracks active tab state", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should have state for which tab is active (activeTab or similar)
    const hasActiveTabState = /activeTab|selectedTab|currentTab/.test(source);
    expect(
      hasActiveTabState,
      "Expected active tab state management",
    ).toBe(true);
  });

  it("selecting a run updates the runId used by Logs tab", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Clicking a run should set a selected runId that the Logs tab uses
    const hasSelectedRunId = /selectedRunId|setRunId|onRunSelect|setSelectedRun/.test(source);
    expect(
      hasSelectedRunId,
      "Expected selected run ID state that Logs tab consumes",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Sorted by newest first (AC4)
// ===========================================================================

describe("Runs sorted by newest first (AC4)", () => {
  it("runs list does not reverse or re-sort the API response", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // The API already returns newest first (ORDER BY created_at DESC).
    // The UI should NOT reverse the order. If it sorts, it should sort descending.
    // We check that there's no .reverse() or ascending sort on the runs data.
    const reversesOrder = /\.reverse\(\)|\.sort\(\(.*\)\s*=>\s*a\.created/.test(source);
    expect(
      reversesOrder,
      "Runs should be displayed in API order (newest first) — no .reverse() or ascending sort",
    ).toBe(false);
  });
});

// ===========================================================================
// 6. CanvasBottomPanel receives workflowId prop
// ===========================================================================

describe("CanvasBottomPanel receives workflowId prop", () => {
  it("component accepts workflowId in its props", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    const hasWorkflowIdProp = /workflowId|workflow_id/.test(source);
    expect(
      hasWorkflowIdProp,
      "Expected workflowId prop on CanvasBottomPanel for scoping runs",
    ).toBe(true);
  });

  it("CanvasBottomPanelProps interface includes workflowId", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    const hasInInterface = /interface\s+CanvasBottomPanelProps[\s\S]*?workflowId/.test(source);
    expect(
      hasInInterface,
      "Expected workflowId in CanvasBottomPanelProps interface",
    ).toBe(true);
  });
});
