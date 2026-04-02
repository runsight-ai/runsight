/**
 * RED-TEAM tests for RUN-560: Run Detail — bottom panel tabs (Logs, Runs, Regressions).
 *
 * These tests verify the 7 acceptance criteria:
 *
 * AC1: Bottom panel shows Logs, Runs, Regressions tabs (no Agent Feed or Artifacts)
 * AC2: Runs tab shows all runs for the same workflow, current run highlighted
 * AC3: Clicking a different run navigates to /runs/:id
 * AC4: Regressions tab shows per-issue rows with node name, type, delta
 * AC5: Regressions tab label includes count badge
 * AC6: Regressions tab hidden when 0 regressions
 * AC7: No backwards compat shims for removed tabs
 *
 * Expected failures (current state):
 *   - RunBottomPanel still has "agent-feed" and "artifacts" tabs
 *   - "runs" and "regressions" tabs do not exist
 *   - useRunRegressions hook does not exist in queries/runs.ts
 *   - RunBottomPanel does not accept runId, workflowId, or currentRunId props
 *   - No regressions query key in keys.ts
 *   - No regressions API endpoint in api/runs.ts
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");
const RUNS_FEATURE_DIR = resolve(__dirname, "..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function readFeatureFile(filename: string): string {
  return readFileSync(resolve(RUNS_FEATURE_DIR, filename), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const BOTTOM_PANEL_PATH = "features/runs/RunBottomPanel.tsx";
const RUN_DETAIL_PATH = "features/runs/RunDetail.tsx";
const QUERIES_RUNS_PATH = "queries/runs.ts";
const API_RUNS_PATH = "api/runs.ts";
const QUERY_KEYS_PATH = "queries/keys.ts";

// ===========================================================================
// AC1: Bottom panel shows Logs, Runs, Regressions tabs
//      (no Agent Feed or Artifacts)
// ===========================================================================

describe("AC1: Bottom panel tab definitions (RUN-560)", () => {
  it("tabs array includes a 'logs' tab", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/id:\s*["']logs["']/);
  });

  it("tabs array includes a 'runs' tab", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/id:\s*["']runs["']/);
  });

  it("tabs array includes a 'regressions' tab", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/id:\s*["']regressions["']/);
  });

  it("tabs array does NOT include 'agent-feed'", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).not.toMatch(/id:\s*["']agent-feed["']/);
  });

  it("tabs array does NOT include 'artifacts'", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).not.toMatch(/id:\s*["']artifacts["']/);
  });

  it("no 'coming soon' placeholder text exists", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src.toLowerCase()).not.toContain("coming soon");
  });

  it("Runs tab has a label of 'Runs'", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should have both id: "runs" and label: "Runs" in the tab definition
    expect(src).toMatch(/label:\s*["']Runs["']/);
  });

  it("Regressions tab has a label containing 'Regressions'", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/["']Regressions["']/);
  });
});

// ===========================================================================
// AC2: Runs tab — shows all runs for the same workflow, current run highlighted
// ===========================================================================

describe("AC2: Runs tab content (RUN-560)", () => {
  it("RunBottomPanel accepts a workflowId prop", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/workflowId/);
  });

  it("RunBottomPanel accepts a currentRunId prop", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/currentRunId/);
  });

  it("RunBottomPanel imports useRuns hook", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/import.*useRuns.*from/);
  });

  it("RunBottomPanel calls useRuns with workflow_id filter", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/useRuns\s*\(/);
    expect(src).toMatch(/workflow_id/);
  });

  it("Runs tab renders a mini table with commit SHA column", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // The runs tab should render commit SHA for each run row
    expect(src).toMatch(/commit_sha|commitSha|commit\.sha|sha/i);
  });

  it("current run row uses --surface-selected background", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/surface-selected/);
  });

  it("runs are sorted by started descending", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should have sorting logic for started_at or created_at desc
    const hasSorting = /sort|\.toSorted|\.reverse|desc/i.test(src);
    expect(hasSorting, "Expected sorting logic for runs by started desc").toBe(true);
  });
});

// ===========================================================================
// AC3: Clicking a different run navigates to /runs/:id
// ===========================================================================

describe("AC3: Runs tab navigation (RUN-560)", () => {
  it("RunBottomPanel uses useNavigate or Link for run navigation", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    const hasNavigation = /useNavigate|<Link|navigate\s*\(/.test(src);
    expect(hasNavigation, "Expected navigation capability for run clicks").toBe(true);
  });

  it("navigation targets /runs/:id pattern", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should construct a /runs/{id} URL
    expect(src).toMatch(/\/runs\//);
  });

  it("run rows are clickable (onClick handler or Link wrapping run data)", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should have click handlers specifically on run rows — not just generic onClick on tab buttons
    // The navigate call or Link element must reference the /runs/ route
    const hasRunRowClick = /navigate\s*\(\s*[`"']\/runs\//.test(src) || /<Link\s+to=.*\/runs\//.test(src);
    expect(hasRunRowClick, "Expected clickable run rows that navigate to /runs/:id").toBe(true);
  });
});

// ===========================================================================
// AC4: Regressions tab — per-issue rows with node name, type, delta
// ===========================================================================

describe("AC4: Regressions tab content (RUN-560)", () => {
  it("RunBottomPanel accepts a runId prop", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Props interface should include runId for fetching regressions
    expect(src).toMatch(/runId/);
  });

  it("RunBottomPanel imports useRunRegressions hook", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/import.*useRunRegressions.*from/);
  });

  it("RunBottomPanel calls useRunRegressions", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/useRunRegressions\s*\(/);
  });

  it("Regressions tab renders warning icon per issue row", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should render a warning/alert icon per regression row
    const hasWarningIcon = /AlertTriangle|AlertCircle|TriangleAlert|warning.*icon/i.test(src);
    expect(hasWarningIcon, "Expected warning icon in regression rows").toBe(true);
  });

  it("Regressions tab renders node name", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should reference node_name or nodeName in regression rendering
    expect(src).toMatch(/node_name|nodeName|node\.name/);
  });

  it("Regressions tab renders regression type", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should reference regression type field (e.g., regression.type, item.regression_type)
    expect(src).toMatch(/regression_type|regressionType|regression.*\.type/);
  });

  it("Regressions tab renders delta summary", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/delta/);
  });
});

// ===========================================================================
// AC5: Regressions tab label includes count badge
// ===========================================================================

describe("AC5: Regressions count badge (RUN-560)", () => {
  it("Regressions tab label includes a dynamic count", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should render "Regressions (N)" or use a Badge component alongside "Regressions"
    // The count must be derived from the regressions data, not from unrelated logs.length
    const hasRegressionCount = /Regressions\s*\(|regressions.*count|regressionCount|regressions.*\.length/.test(src);
    expect(hasRegressionCount, "Expected regression count in Regressions tab label").toBe(true);
  });

  it("imports Badge component for count display", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).toMatch(/import.*Badge.*from/);
  });
});

// ===========================================================================
// AC6: Regressions tab hidden when 0 regressions
// ===========================================================================

describe("AC6: Regressions tab hidden when 0 regressions (RUN-560)", () => {
  it("conditionally filters tabs based on regression count", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Should filter tabs or conditionally include regressions tab
    const hasConditionalTab = /\.filter|\.length\s*[>!==]=?\s*0|regressions.*\.length|visibleTabs|filteredTabs/.test(src);
    expect(
      hasConditionalTab,
      "Expected conditional logic to hide regressions tab when count is 0",
    ).toBe(true);
  });

  it("regressions tab is not rendered when regressions array is empty", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // The tab array should be dynamically computed, not static
    // The current static `as const` array must be replaced with dynamic filtering
    const isStaticTabArray = /const\s+tabs\s*=\s*\[[\s\S]*?\]\s*as\s+const/.test(src);
    // If tabs are still declared as a static `as const` tuple, they can't be conditionally filtered
    // The implementation needs dynamic tab computation
    const hasDynamicTabs = /useMemo|\.filter|computed|visibleTabs/.test(src);
    expect(
      hasDynamicTabs,
      "Expected dynamic tab computation (useMemo, filter, or similar) to hide empty regressions",
    ).toBe(true);
  });
});

// ===========================================================================
// AC7: No backwards compat shims for removed tabs
// ===========================================================================

describe("AC7: No backwards compat shims (RUN-560)", () => {
  it("no 'Agent Feed' text in the component", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).not.toContain("Agent Feed");
  });

  it("no 'Artifacts' text in the component", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).not.toContain("Artifacts");
  });

  it("no Bot icon import (was used for Agent Feed)", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Bot icon was imported for the Agent Feed tab — should be removed
    // Check for Bot in any import block (multi-line destructured imports)
    expect(src).not.toMatch(/\bBot\b/);
  });

  it("no Package icon import (was used for Artifacts)", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    // Package icon was imported for the Artifacts tab — should be removed
    // Check for Package in any import block (multi-line destructured imports)
    expect(src).not.toMatch(/\bPackage\b/);
  });

  it("no fallback rendering for agent-feed tab content", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).not.toMatch(/activeTab\s*===\s*["']agent-feed["']/);
  });

  it("no fallback rendering for artifacts tab content", () => {
    const src = readSource(BOTTOM_PANEL_PATH);
    expect(src).not.toMatch(/activeTab\s*===\s*["']artifacts["']/);
  });
});

// ===========================================================================
// Hook: useRunRegressions exists in queries/runs.ts
// ===========================================================================

describe("useRunRegressions hook (RUN-560)", () => {
  it("queries/runs.ts exports useRunRegressions", () => {
    const src = readSource(QUERIES_RUNS_PATH);
    expect(src).toMatch(/export\s+function\s+useRunRegressions/);
  });

  it("useRunRegressions calls GET /runs/:id/regressions", () => {
    const src = readSource(QUERIES_RUNS_PATH);
    expect(src).toMatch(/regressions/);
  });

  it("useRunRegressions uses the regressions query key", () => {
    const src = readSource(QUERIES_RUNS_PATH);
    expect(src).toMatch(/queryKeys\.runs\.regressions|queryKey.*regressions/);
  });
});

// ===========================================================================
// API: regressions endpoint in api/runs.ts
// ===========================================================================

describe("Regressions API endpoint (RUN-560)", () => {
  it("api/runs.ts has a getRunRegressions method", () => {
    const src = readSource(API_RUNS_PATH);
    expect(src).toMatch(/getRunRegressions/);
  });

  it("getRunRegressions calls /runs/:id/regressions", () => {
    const src = readSource(API_RUNS_PATH);
    expect(src).toMatch(/\/runs\/.*\/regressions/);
  });
});

// ===========================================================================
// Query keys: regressions key exists
// ===========================================================================

describe("Regressions query key (RUN-560)", () => {
  it("queryKeys.runs includes a regressions key factory", () => {
    const src = readSource(QUERY_KEYS_PATH);
    expect(src).toMatch(/regressions/);
  });
});

// ===========================================================================
// RunDetail wiring: passes new props to RunBottomPanel
// ===========================================================================

describe("RunDetail passes new props to RunBottomPanel (RUN-560)", () => {
  it("RunDetail passes runId to RunBottomPanel", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // The RunBottomPanel usage should include runId prop
    expect(src).toMatch(/<RunBottomPanel[\s\S]*?runId/);
  });

  it("RunDetail passes workflowId to RunBottomPanel", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).toMatch(/<RunBottomPanel[\s\S]*?workflowId/);
  });

  it("RunDetail passes currentRunId to RunBottomPanel", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).toMatch(/<RunBottomPanel[\s\S]*?currentRunId/);
  });
});
