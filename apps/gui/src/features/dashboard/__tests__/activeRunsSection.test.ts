/**
 * RED-TEAM tests for RUN-339: A3 — Active Runs section with SSE (end-to-end).
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Dashboard imports and uses StatusDot component
 * AC2: "ACTIVE RUNS" section label exists in the dashboard
 * AC3: useActiveRuns hook exists and queries with status filter
 * AC4: StatusDot has animate="pulse" for running runs
 * AC5: Click navigates to /workflows/:id/edit
 * AC6: Section hidden when no active runs (conditional rendering)
 * AC7: useNavigate used for run click navigation
 * AC9: Run removed from active list when completed/failed via SSE
 *
 * Expected failures (current state):
 *   - DashboardOrOnboarding.tsx is a minimal 30-line shell with no active runs section
 *   - No useActiveRuns hook exists in queries/runs.ts
 *   - No StatusDot import in the dashboard
 *   - No "ACTIVE RUNS" label anywhere
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

const DASHBOARD_PATH = "features/dashboard/DashboardOrOnboarding.tsx";
const RUNS_QUERIES_PATH = "queries/runs.ts";
const RUNS_API_PATH = "api/runs.ts";

// ===========================================================================
// 1. useActiveRuns hook exists (AC3)
// ===========================================================================

describe("useActiveRuns hook (AC3: queries with status filter)", () => {
  let source: string;

  it("exports a useActiveRuns function from queries/runs.ts", () => {
    source = readSource(RUNS_QUERIES_PATH);
    expect(source).toMatch(/export\s+function\s+useActiveRuns/);
  });

  it("useActiveRuns passes status filter params (running, pending)", () => {
    source = readSource(RUNS_QUERIES_PATH);
    // Should construct query params with status=running and status=pending
    expect(source).toMatch(/status/);
    expect(source).toMatch(/running/);
    expect(source).toMatch(/pending/);
  });

  it("useActiveRuns uses a polling interval (refetchInterval)", () => {
    source = readSource(RUNS_QUERIES_PATH);
    // The hook should poll at an interval (e.g. 5000ms)
    // Look for refetchInterval in the context of useActiveRuns
    const hookMatch = source.match(
      /function\s+useActiveRuns[\s\S]*?^}/m
    );
    expect(hookMatch).not.toBeNull();
    expect(hookMatch![0]).toMatch(/refetchInterval/);
  });
});

// ===========================================================================
// 2. Dashboard imports StatusDot (AC1)
// ===========================================================================

describe("Dashboard imports StatusDot (AC1)", () => {
  let source: string;

  it("imports StatusDot from components/ui/status-dot", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*StatusDot.*from/);
    expect(source).toMatch(/status-dot/);
  });

  it("uses StatusDot in JSX", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/<StatusDot\b/);
  });
});

// ===========================================================================
// 3. "ACTIVE RUNS" section label (AC2)
// ===========================================================================

describe("ACTIVE RUNS section label (AC2)", () => {
  let source: string;

  it("contains 'ACTIVE RUNS' text in the dashboard", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/ACTIVE RUNS/);
  });

  it("uses monospace and muted styling for the label", () => {
    source = readSource(DASHBOARD_PATH);
    // The label should have mono font and muted text color per spec
    expect(source).toMatch(/font-mono|mono/);
    expect(source).toMatch(/text-muted|--text-muted/);
  });
});

// ===========================================================================
// 4. StatusDot pulses for running runs (AC4)
// ===========================================================================

describe("StatusDot animate='pulse' for running (AC4)", () => {
  let source: string;

  it("passes animate='pulse' to StatusDot for running status", () => {
    source = readSource(DASHBOARD_PATH);
    // Should have animate="pulse" conditional on running status
    expect(source).toMatch(/animate\s*=\s*["'{].*pulse/);
  });

  it("does NOT pulse for pending status", () => {
    source = readSource(DASHBOARD_PATH);
    // For pending runs, animate should be "none" or absent — not "pulse"
    // We check that there's a conditional: running → pulse, pending → something else
    // This means there should be a ternary or condition around pulse
    const hasPulseConditional =
      /running.*pulse|status.*===.*["']running["'].*pulse/.test(source);
    expect(
      hasPulseConditional,
      "Expected pulse animation to be conditional on running status"
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Click navigates to workflow canvas (AC5, AC7)
// ===========================================================================

describe("Click navigates to /workflows/:id/edit (AC5, AC7)", () => {
  let source: string;

  it("imports useNavigate from react-router", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*useNavigate.*from\s*["']react-router["']/);
  });

  it("navigates to /workflows/:id/edit using run's workflow_id", () => {
    source = readSource(DASHBOARD_PATH);
    // Should build a path like `/workflows/${run.workflow_id}/edit`
    // This must reference workflow_id from the run object (not from workflow creation)
    expect(source).toMatch(/workflow_id.*\/edit|\/workflows\/\$\{.*workflow_id/);
  });

  it("has an onClick handler on the active run row", () => {
    source = readSource(DASHBOARD_PATH);
    // The run row needs a click handler that navigates — there should be at
    // least two onClick handlers: one for New Workflow and one for run rows.
    const matches = source.match(/onClick/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });
});

// ===========================================================================
// 6. Conditional rendering — hidden when no active runs (AC6)
// ===========================================================================

describe("Section hidden when no active runs (AC6)", () => {
  let source: string;

  it("imports useActiveRuns hook in the dashboard", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*useActiveRuns.*from/);
  });

  it("conditionally renders the active runs section", () => {
    source = readSource(DASHBOARD_PATH);
    // Should have conditional rendering: check for array length or data existence
    // Patterns like: {activeRuns?.length > 0 && ...} or {data?.items?.length ? ... : null}
    const hasConditional =
      /activeRuns.*&&|\.length\s*[>!]|\.items\?\.length|data\s*&&/.test(
        source
      );
    expect(
      hasConditional,
      "Expected conditional rendering based on active runs data"
    ).toBe(true);
  });
});

// ===========================================================================
// 7. Dashboard uses useActiveRuns (wiring check)
// ===========================================================================

describe("Dashboard wiring (useActiveRuns integration)", () => {
  let source: string;

  it("calls useActiveRuns() in the component", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/useActiveRuns\s*\(/);
  });

  it("displays workflow name for each active run", () => {
    source = readSource(DASHBOARD_PATH);
    // Should render the workflow_name from the run
    expect(source).toMatch(/workflow_name/);
  });

  it("displays elapsed time for each active run", () => {
    source = readSource(DASHBOARD_PATH);
    // Should have elapsed time logic — referencing started_at or elapsed
    const hasElapsed = /elapsed|started_at|duration/.test(source);
    expect(
      hasElapsed,
      "Expected elapsed time display referencing started_at or elapsed"
    ).toBe(true);
  });

  it("displays cost for each active run", () => {
    source = readSource(DASHBOARD_PATH);
    // Should reference total_cost_usd or cost
    expect(source).toMatch(/total_cost_usd|cost/);
  });
});

// ===========================================================================
// 8. SSE subscription removes runs on completion/failure (AC9)
// ===========================================================================

describe("SSE removes completed/failed runs from active list (AC9)", () => {
  let dashSource: string;
  let queriesSource: string;

  it("references EventSource or SSE stream in dashboard or queries layer", () => {
    dashSource = readSource(DASHBOARD_PATH);
    queriesSource = readSource(RUNS_QUERIES_PATH);
    const combined = dashSource + queriesSource;
    // There must be an EventSource instantiation or a /stream endpoint reference
    const hasSSE = /EventSource|\/stream|event-source|useSSE|useSse/.test(
      combined
    );
    expect(
      hasSSE,
      "Expected EventSource or /stream reference for SSE subscription"
    ).toBe(true);
  });

  it("connects SSE per active run (uses run id in stream URL)", () => {
    dashSource = readSource(DASHBOARD_PATH);
    queriesSource = readSource(RUNS_QUERIES_PATH);
    const combined = dashSource + queriesSource;
    // The SSE connection should be per-run, referencing the run's id in the URL
    // e.g. /api/v1/runs/${run.id}/stream or similar pattern
    const hasPerRunStream =
      /runs\/\$\{.*\.id\}\/stream|runs\/\$\{.*id\}\/stream|run\.id.*stream|runId.*stream/.test(
        combined
      );
    expect(
      hasPerRunStream,
      "Expected per-run SSE connection using run id in the stream URL"
    ).toBe(true);
  });

  it("handles run_completed or completed event to remove run from list", () => {
    dashSource = readSource(DASHBOARD_PATH);
    queriesSource = readSource(RUNS_QUERIES_PATH);
    const combined = dashSource + queriesSource;
    // Should listen for a completed event and remove/filter the run
    const handlesCompleted =
      /run_completed|["']completed["'].*remove|completed.*filter|onmessage.*completed|addEventListener.*completed/.test(
        combined
      );
    expect(
      handlesCompleted,
      "Expected handler for run_completed/completed SSE event that removes run"
    ).toBe(true);
  });

  it("handles run_failed or failed event to remove run from list", () => {
    dashSource = readSource(DASHBOARD_PATH);
    queriesSource = readSource(RUNS_QUERIES_PATH);
    const combined = dashSource + queriesSource;
    // Should listen for a failed event and remove/filter the run
    const handlesFailed =
      /run_failed|["']failed["'].*remove|failed.*filter|onmessage.*failed|addEventListener.*failed/.test(
        combined
      );
    expect(
      handlesFailed,
      "Expected handler for run_failed/failed SSE event that removes run"
    ).toBe(true);
  });
});
