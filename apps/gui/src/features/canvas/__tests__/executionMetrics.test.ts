/**
 * RED+GREEN tests for RUN-372: T17 — Execution completed/failed — topbar metrics summary.
 *
 * Acceptance Criteria:
 *   AC1: Metrics shown on completion (cost, tokens, duration)
 *   AC2: Failed state shows error indicator
 *   AC3: Metrics auto-hide after 5s
 *   AC4: Run button returns to idle
 *
 * Tests are source-reading style, verifying the ExecutionMetrics component
 * and its integration with CanvasTopbar.
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
// Paths
// ---------------------------------------------------------------------------

const EXECUTION_METRICS_PATH = "features/canvas/ExecutionMetrics.tsx";
const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";

// ===========================================================================
// 1. ExecutionMetrics component exists
// ===========================================================================

describe("ExecutionMetrics component exists (RUN-372)", () => {
  it("ExecutionMetrics.tsx file exists", () => {
    expect(
      fileExists(EXECUTION_METRICS_PATH),
      "Expected features/canvas/ExecutionMetrics.tsx to exist",
    ).toBe(true);
  });

  it("exports ExecutionMetrics as a named export", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+ExecutionMetrics/);
  });

  it("CanvasTopbar renders ExecutionMetrics", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/<ExecutionMetrics/);
  });

  it("CanvasTopbar imports ExecutionMetrics", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/import.*ExecutionMetrics.*from/);
  });
});

// ===========================================================================
// 2. Metrics display — cost, tokens, duration (AC1)
// ===========================================================================

describe("ExecutionMetrics displays cost, tokens, duration (RUN-372 AC1)", () => {
  it("displays cost metric (total_cost_usd)", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/cost|total_cost_usd/i);
  });

  it("displays token count metric (total_tokens)", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/tokens|total_tokens/i);
  });

  it("displays duration metric (duration_seconds)", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/duration|duration_seconds/i);
  });

  it("formats cost as USD currency", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    // Should show dollar sign or format as currency
    expect(source).toMatch(/\$|USD|toFixed/);
  });

  it("formats duration in human-readable form", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    // Should convert seconds to readable format (e.g., "2.3s" or "1m 30s")
    expect(source).toMatch(/[sm]"|'s'|"s"/);
  });
});

// ===========================================================================
// 3. Uses useRun hook for status polling (AC1)
// ===========================================================================

describe("ExecutionMetrics uses useRun for data (RUN-372)", () => {
  it("imports useRun from queries/runs", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/import.*useRun.*from.*queries\/runs/);
  });

  it("imports useCanvasStore for activeRunId", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/import.*useCanvasStore.*from.*store\/canvas/);
  });

  it("reads activeRunId from canvas store", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/activeRunId/);
  });
});

// ===========================================================================
// 4. Conditional rendering based on run completion (AC1)
// ===========================================================================

describe("ExecutionMetrics renders conditionally (RUN-372)", () => {
  it("checks for completed status", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/completed/);
  });

  it("checks for failed status", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/failed/);
  });

  it("returns null when no terminal run state", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    // Should early-return null if status is not completed/failed
    expect(source).toMatch(/return\s+null/);
  });
});

// ===========================================================================
// 5. Failed state shows error indicator (AC2)
// ===========================================================================

describe("ExecutionMetrics error indicator for failed runs (RUN-372 AC2)", () => {
  it("shows error styling or indicator for failed runs", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    // Should have error/danger/red styling for failed state
    const hasErrorIndicator =
      /error|danger|destructive|red-|AlertCircle|XCircle|AlertTriangle/.test(source);
    expect(
      hasErrorIndicator,
      "Expected error indicator for failed runs",
    ).toBe(true);
  });

  it("differentiates visually between completed and failed states", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    // Should have different styling for completed vs failed
    const hasBranching =
      /failed.*completed|completed.*failed|status\s*===/.test(source);
    expect(
      hasBranching,
      "Expected conditional styling based on completed vs failed",
    ).toBe(true);
  });
});

// ===========================================================================
// 6. Auto-hide after 5 seconds (AC3)
// ===========================================================================

describe("ExecutionMetrics auto-hide after 5s (RUN-372 AC3)", () => {
  it("uses setTimeout with 5000ms delay", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/setTimeout/);
    expect(source).toMatch(/5000/);
  });

  it("uses useEffect for the auto-hide timer", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/useEffect/);
  });

  it("has a visibility state that controls rendering", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    // Should have a boolean state controlling whether metrics are shown
    const hasVisibilityState =
      /visible|show|hidden|setVisible|setShow|setHidden/.test(source);
    expect(
      hasVisibilityState,
      "Expected visibility state for auto-hide behavior",
    ).toBe(true);
  });

  it("cleans up the timeout on unmount (clearTimeout)", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).toMatch(/clearTimeout/);
  });
});

// ===========================================================================
// 7. Run button returns to idle (AC4)
// ===========================================================================

describe("Run button returns to idle after completion (RUN-372 AC4)", () => {
  it("RunButton already clears activeRunId on terminal states", () => {
    // This is already implemented in RunButton.tsx (RUN-359)
    // Verify it still works — the setActiveRunId(null) on completed/failed/cancelled
    const source = readSource("features/canvas/RunButton.tsx");
    expect(source).toMatch(/setActiveRunId\(\s*null\s*\)/);
  });

  it("RunButton handles completed status", () => {
    const source = readSource("features/canvas/RunButton.tsx");
    expect(source).toMatch(/completed/);
  });

  it("RunButton handles failed status", () => {
    const source = readSource("features/canvas/RunButton.tsx");
    expect(source).toMatch(/failed/);
  });
});

// ===========================================================================
// 8. Styling and design tokens
// ===========================================================================

describe("ExecutionMetrics uses design system tokens (RUN-372)", () => {
  it("does NOT use hardcoded hex colors", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    const hexMatches = source.match(/#[0-9a-fA-F]{3,8}\b/g);
    expect(hexMatches).toBeNull();
  });

  it("does NOT use hardcoded rgba colors", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    expect(source).not.toMatch(/rgba?\s*\(\s*\d+/);
  });

  it("uses accessible aria labels or roles", () => {
    const source = readSource(EXECUTION_METRICS_PATH);
    const hasAccessibility = /aria-label|role=|aria-live/.test(source);
    expect(
      hasAccessibility,
      "Expected accessibility attributes on metrics display",
    ).toBe(true);
  });
});
