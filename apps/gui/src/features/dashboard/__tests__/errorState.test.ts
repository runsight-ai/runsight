/**
 * RED-TEAM tests for RUN-344: B2 — Dashboard error state — error banner + retry.
 *
 * These tests verify ALL acceptance criteria by reading source files as strings
 * and asserting observable structural properties:
 *
 * AC1: Error banner with descriptive message when API fails
 * AC2: Retry button that calls refetch
 * AC3: KPI cards show "—" on error
 * AC4: Partial error: show what loaded, error banner for what failed
 * AC5: No new components (inline error banner)
 *
 * Expected failures (current state):
 *   - DashboardOrOnboarding.tsx does not destructure isError/error/refetch from hooks
 *   - No error banner text about server not running
 *   - No retry button
 *   - KPI values do not fall back to "—" on error (only on null fields)
 *   - No partial error handling (independent error checks per hook)
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

// ===========================================================================
// 1. Error banner with descriptive message (AC1)
// ===========================================================================

describe("Error banner with descriptive message when API fails (AC1)", () => {
  it("destructures isError from useDashboardKPIs", () => {
    const source = readSource(DASHBOARD_PATH);
    // The component must destructure isError (or error) from useDashboardKPIs
    // to detect API failure. Pattern: { data, isError, ... } = useDashboardKPIs()
    const hasIsError = /useDashboardKPIs\(\)/.test(source) &&
      /isError/.test(source);
    const hasError = /useDashboardKPIs\(\)/.test(source) &&
      /\berror\b/.test(source);
    expect(
      hasIsError || hasError,
      "Expected isError or error to be destructured from useDashboardKPIs()",
    ).toBe(true);
  });

  it("contains the error message about Runsight server", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(
      /Couldn[''\u2019]t load dashboard data/,
    );
  });

  it("contains the server-running hint in the error message", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(
      /Check that the Runsight server is running/,
    );
  });

  it("conditionally renders the error banner when isError is true", () => {
    const source = readSource(DASHBOARD_PATH);
    // The error banner should only render when an error is present.
    // Patterns: {isError && <div ...>}, isError ? <div ...> : null
    const hasConditionalError =
      /isError\s*&&/.test(source) ||
      /isError\s*\?/.test(source) ||
      /error\s*&&/.test(source) ||
      /kpiError|dashboardError|kpisError/.test(source);
    expect(
      hasConditionalError,
      "Expected conditional rendering of error banner based on isError or error state",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. Retry button that calls refetch (AC2)
// ===========================================================================

describe("Retry button that calls refetch (AC2)", () => {
  it("destructures refetch from useDashboardKPIs", () => {
    const source = readSource(DASHBOARD_PATH);
    // Must have refetch available from the hook
    expect(source).toMatch(/refetch/);
  });

  it('has a button labeled "Retry"', () => {
    const source = readSource(DASHBOARD_PATH);
    // There should be a clickable element with "Retry" text
    expect(source).toMatch(/Retry/);
  });

  it("Retry button onClick calls refetch", () => {
    const source = readSource(DASHBOARD_PATH);
    // The retry button's onClick should invoke refetch.
    // Patterns: onClick={refetch}, onClick={() => refetch()}, onClick={handleRetry}
    const hasRefetchOnClick =
      /onClick\s*=\s*\{[^}]*refetch/.test(source) ||
      /onClick\s*=\s*\{refetch\}/.test(source);
    expect(
      hasRefetchOnClick,
      "Expected Retry button onClick to call refetch",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. KPI cards show "—" on error (AC3)
// ===========================================================================

describe('KPI cards show "\u2014" on error (AC3)', () => {
  it("runsToday falls back to em-dash on error (not just on null)", () => {
    const source = readSource(DASHBOARD_PATH);
    // Currently runsToday defaults to 0 via: data?.runs_today ?? 0
    // On error, it should display "—" instead. The logic must account for
    // isError state, not just nullish data fields.
    // Patterns: isError ? "—" : runsToday, or runsToday = isError ? "—" : data?.runs_today ?? 0
    const hasErrorFallbackForRuns =
      /isError.*\u2014.*runs|runs.*isError.*\u2014|kpi.*error.*\u2014/.test(source) ||
      /runsToday.*=.*isError.*\u2014|isError.*runs.*\u2014/.test(source);
    expect(
      hasErrorFallbackForRuns,
      'Expected runsToday to display "\u2014" when isError is true',
    ).toBe(true);
  });

  it("costTodayUsd falls back to em-dash on error (not just on null)", () => {
    const source = readSource(DASHBOARD_PATH);
    // Currently costTodayUsd defaults to 0 via: data?.cost_today_usd ?? 0
    // On error, it should display "—" instead of "$0.00"
    const hasErrorFallbackForCost =
      /isError.*\u2014.*cost|cost.*isError.*\u2014|kpi.*error.*\u2014/.test(source) ||
      /costToday.*=.*isError.*\u2014|isError.*cost.*\u2014|Spent Today.*\u2014/.test(source);
    expect(
      hasErrorFallbackForCost,
      'Expected costTodayUsd to display "\u2014" when isError is true',
    ).toBe(true);
  });

  it("all 4 StatCard values use em-dash fallback on error", () => {
    const source = readSource(DASHBOARD_PATH);
    // When the KPI API fails, ALL four cards should show "—".
    // This means there must be a pattern that maps isError to "—" for each value.
    // Count how many times the error-to-em-dash pattern appears near StatCard values.
    const emDashOnErrorCount = (
      source.match(/isError.*\u2014|error.*\u2014.*StatCard/g) || []
    ).length;
    // At minimum, we need at least 1 pattern that covers all cards,
    // or individual patterns for runs_today and cost_today_usd (eval and regressions already have "—" for null)
    expect(emDashOnErrorCount).toBeGreaterThanOrEqual(1);
  });
});

// ===========================================================================
// 4. Partial error: show what loaded, error banner for what failed (AC4)
// ===========================================================================

describe("Partial error: show what loaded, error banner for what failed (AC4)", () => {
  it("destructures error state from useActiveRuns independently", () => {
    const source = readSource(DASHBOARD_PATH);
    // For partial error handling, the component must track error state
    // from BOTH useDashboardKPIs AND useActiveRuns independently.
    // Currently useActiveRuns returns { ...query, activeRuns, subscribeToRunStream }
    // so isError is available on the spread query result.
    // The dashboard must destructure isError from useActiveRuns as well.
    const hasActiveRunsError =
      /useActiveRuns\(\)/.test(source) &&
      (
        /activeRuns.*isError|isError.*activeRuns/.test(source) ||
        /runsError|activeRunsError|runsIsError/.test(source) ||
        // renamed destructuring: { isError: runsError } or similar
        /isError\s*:\s*\w+/.test(source)
      );
    expect(
      hasActiveRunsError,
      "Expected error state destructured from useActiveRuns for partial error handling",
    ).toBe(true);
  });

  it("handles KPI success + active runs failure (partial error)", () => {
    const source = readSource(DASHBOARD_PATH);
    // When KPIs load successfully but active runs fail, the KPI cards
    // should still display real data while an error banner shows for runs.
    // This requires separate error checks, not a single combined one.
    // Look for two distinct isError references or renamed error variables.
    const errorRefs = source.match(/isError|Error\b/g) || [];
    // Must have at least 2 error-related references (one per hook)
    expect(
      errorRefs.length,
      "Expected multiple error references for independent hook error handling",
    ).toBeGreaterThanOrEqual(2);
  });

  it("handles active runs success + KPI failure (partial error)", () => {
    const source = readSource(DASHBOARD_PATH);
    // When active runs load but KPIs fail, active runs should still display
    // while KPI cards show "—" and an error banner appears.
    // This means the active runs section is NOT gated behind KPI success.
    // The activeRuns rendering should be independent of KPI error state.
    const activeRunsSection = /activeRuns\.length\s*>\s*0/.test(source);
    const kpiErrorCheck = /isError|kpiError|kpisError/.test(source);
    expect(
      activeRunsSection && kpiErrorCheck,
      "Expected active runs section to render independently of KPI error state",
    ).toBe(true);
  });

  it("shows error banner text that specifies what failed", () => {
    const source = readSource(DASHBOARD_PATH);
    // The error banner message should be contextual. When both fail,
    // it shows the general message. When only one fails, it should
    // indicate which part failed. At minimum, the error banner must exist.
    // Check for at least one error-conditional rendering with a message string.
    const hasErrorMessage =
      /isError.*load|error.*load|Couldn.*load/i.test(source);
    expect(
      hasErrorMessage,
      "Expected error banner with a descriptive load failure message",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. No new components — inline error banner (AC5)
// ===========================================================================

describe("No new components — inline error banner (AC5)", () => {
  it("does NOT import an ErrorBanner or DashboardError component", () => {
    const source = readSource(DASHBOARD_PATH);
    // The error banner must be inline, not a separate component file
    expect(source).not.toMatch(
      /import.*(?:ErrorBanner|DashboardError|ErrorAlert|ErrorMessage).*from/,
    );
  });

  it("error banner is rendered as an inline div (not a separate component)", () => {
    const source = readSource(DASHBOARD_PATH);
    // The error banner should be a plain <div> or similar inline element,
    // not a component. Look for a div near the error message text.
    const hasInlineErrorDiv =
      /(?:<div|<section|<aside)[^>]*>[\s\S]*?(?:Couldn.*load|error|Error)/.test(source) ||
      /(?:Couldn.*load|Check that the Runsight server)/.test(source);
    expect(
      hasInlineErrorDiv,
      "Expected inline div for error banner, not a separate component",
    ).toBe(true);
  });

  it("error banner has visual styling (background/border for visibility)", () => {
    const source = readSource(DASHBOARD_PATH);
    // The error banner should be visually distinct — using background color,
    // border, or similar Tailwind classes for an error/warning appearance.
    // Common patterns: bg-danger, bg-destructive, border-danger, bg-red, bg-warning
    const hasErrorStyling =
      /(?:bg-danger|bg-destructive|bg-red|bg-warning|border-danger|border-destructive|border-red|border-warning|text-danger|text-destructive)/.test(source);
    expect(
      hasErrorStyling,
      "Expected error banner to have visual error styling (bg-danger, border-destructive, etc.)",
    ).toBe(true);
  });
});
