/**
 * RED-TEAM tests for RUN-855: Decompose oversized DashboardOrOnboarding component.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * AC2: DashboardOrOnboarding decomposed — KPIs, attention items, active runs
 *      each as separate components
 * AC3: Each sub-component ≤80 lines of logic
 * AC4: All existing tests still pass (behavioral: DashboardOrOnboarding still exported)
 *
 * Expected failures (current state):
 *   - DashboardKPIs component does not exist
 *   - AttentionItems component does not exist
 *   - ActiveRunsTable component does not exist
 *   - DashboardOrOnboarding.tsx exceeds 80 lines
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DASHBOARD_DIR = resolve(__dirname, "..");
const COMPONENTS_DIR = resolve(DASHBOARD_DIR, "components");

function readSource(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function fileExists(filePath: string): boolean {
  return existsSync(filePath);
}

function countLines(source: string): number {
  // Count non-empty, non-comment-only lines
  return source
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .length;
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const DASHBOARD_PATH = resolve(DASHBOARD_DIR, "DashboardOrOnboarding.tsx");
const DASHBOARD_KPIS_PATH = resolve(COMPONENTS_DIR, "DashboardKPIs.tsx");
const ATTENTION_ITEMS_PATH = resolve(COMPONENTS_DIR, "AttentionItems.tsx");
const ACTIVE_RUNS_TABLE_PATH = resolve(COMPONENTS_DIR, "ActiveRunsTable.tsx");

// ===========================================================================
// 1. New sub-component files exist (AC2)
// ===========================================================================

describe("New sub-component files exist (AC2)", () => {
  it("components/DashboardKPIs.tsx exists", () => {
    expect(
      fileExists(DASHBOARD_KPIS_PATH),
      "Expected features/dashboard/components/DashboardKPIs.tsx to exist",
    ).toBe(true);
  });

  it("components/AttentionItems.tsx exists", () => {
    expect(
      fileExists(ATTENTION_ITEMS_PATH),
      "Expected features/dashboard/components/AttentionItems.tsx to exist",
    ).toBe(true);
  });

  it("components/ActiveRunsTable.tsx exists", () => {
    expect(
      fileExists(ACTIVE_RUNS_TABLE_PATH),
      "Expected features/dashboard/components/ActiveRunsTable.tsx to exist",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. DashboardKPIs component structure (AC2)
// ===========================================================================

describe("DashboardKPIs component structure (AC2)", () => {
  it("exports DashboardKPIs function", () => {
    const source = readSource(DASHBOARD_KPIS_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+DashboardKPIs/);
  });

  it("renders StatCard components", () => {
    const source = readSource(DASHBOARD_KPIS_PATH);
    expect(source).toMatch(/StatCard/);
  });

  it("handles isPending/loading state with Skeleton", () => {
    const source = readSource(DASHBOARD_KPIS_PATH);
    expect(source).toMatch(/isPending|isLoading|Skeleton/);
  });

  it("contains KPI logic: runs today, eval pass rate, cost, regressions", () => {
    const source = readSource(DASHBOARD_KPIS_PATH);
    expect(source).toMatch(/runs.*today|runsToday/i);
    expect(source).toMatch(/eval.*pass|evalPass/i);
    expect(source).toMatch(/cost/i);
    expect(source).toMatch(/regressions/i);
  });

  it("is ≤80 non-empty lines", () => {
    const source = readSource(DASHBOARD_KPIS_PATH);
    const lines = countLines(source);
    expect(lines, `DashboardKPIs.tsx has ${lines} non-empty lines, expected ≤80`).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 3. AttentionItems component structure (AC2)
// ===========================================================================

describe("AttentionItems component structure (AC2)", () => {
  it("exports AttentionItems function", () => {
    const source = readSource(ATTENTION_ITEMS_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+AttentionItems/);
  });

  it("accepts items prop or uses useAttentionItems", () => {
    const source = readSource(ATTENTION_ITEMS_PATH);
    const hasItemsProp = /items\s*:/.test(source);
    const hasHook = /useAttentionItems/.test(source);
    expect(
      hasItemsProp || hasHook,
      "Expected AttentionItems to accept items prop or use useAttentionItems hook",
    ).toBe(true);
  });

  it("renders Card components for each attention item", () => {
    const source = readSource(ATTENTION_ITEMS_PATH);
    expect(source).toMatch(/Card/);
  });

  it("uses AlertTriangle or Activity icons", () => {
    const source = readSource(ATTENTION_ITEMS_PATH);
    expect(source).toMatch(/AlertTriangle|Activity/);
  });

  it("renders Badge for attention item type", () => {
    const source = readSource(ATTENTION_ITEMS_PATH);
    expect(source).toMatch(/Badge/);
  });

  it("is ≤80 non-empty lines", () => {
    const source = readSource(ATTENTION_ITEMS_PATH);
    const lines = countLines(source);
    expect(lines, `AttentionItems.tsx has ${lines} non-empty lines, expected ≤80`).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 4. ActiveRunsTable component structure (AC2)
// ===========================================================================

describe("ActiveRunsTable component structure (AC2)", () => {
  it("exports ActiveRunsTable function", () => {
    const source = readSource(ACTIVE_RUNS_TABLE_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+ActiveRunsTable/);
  });

  it("renders Table component", () => {
    const source = readSource(ACTIVE_RUNS_TABLE_PATH);
    expect(source).toMatch(/Table/);
  });

  it("shows StatusDot for run status", () => {
    const source = readSource(ACTIVE_RUNS_TABLE_PATH);
    expect(source).toMatch(/StatusDot/);
  });

  it("displays elapsed time and cost columns", () => {
    const source = readSource(ACTIVE_RUNS_TABLE_PATH);
    expect(source).toMatch(/elapsed|Elapsed/i);
    expect(source).toMatch(/cost|Cost/i);
  });

  it("handles loading state with Skeleton", () => {
    const source = readSource(ACTIVE_RUNS_TABLE_PATH);
    expect(source).toMatch(/isLoading|Skeleton/);
  });

  it("is ≤80 non-empty lines", () => {
    const source = readSource(ACTIVE_RUNS_TABLE_PATH);
    const lines = countLines(source);
    expect(lines, `ActiveRunsTable.tsx has ${lines} non-empty lines, expected ≤80`).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 5. DashboardOrOnboarding main component line count (AC3)
// ===========================================================================

describe("DashboardOrOnboarding main component ≤80 lines (AC3)", () => {
  it("DashboardOrOnboarding.tsx has ≤80 non-empty lines after decomposition", () => {
    const source = readSource(DASHBOARD_PATH);
    const lines = countLines(source);
    expect(lines, `DashboardOrOnboarding.tsx has ${lines} non-empty lines, expected ≤80`).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 6. DashboardOrOnboarding still exported + uses sub-components (AC4)
// ===========================================================================

describe("DashboardOrOnboarding still exported (AC4)", () => {
  it("Component function is still exported from DashboardOrOnboarding.tsx", () => {
    const source = readSource(DASHBOARD_PATH);
    // File uses named export `Component` for React Router lazy loading
    expect(source).toMatch(/export\s+function\s+Component|export\s*\{[^}]*Component[^}]*\}/);
  });

  it("DashboardOrOnboarding imports DashboardKPIs sub-component", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/DashboardKPIs/);
  });

  it("DashboardOrOnboarding imports AttentionItems sub-component", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/AttentionItems/);
  });

  it("DashboardOrOnboarding imports ActiveRunsTable sub-component", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/ActiveRunsTable/);
  });

  it("DashboardOrOnboarding still handles 3-branch routing (hasNoWorkflows, runsToday===0, full)", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/hasNoWorkflows|workflows.*length.*===.*0/);
    expect(source).toMatch(/runsToday.*===.*0|runs.*today.*===.*0/i);
  });
});

// ===========================================================================
// 7. Formatter utilities extracted to a shared file (AC3 — DRY)
// ===========================================================================

describe("Formatter utilities do not bloat DashboardOrOnboarding.tsx", () => {
  it("DashboardOrOnboarding.tsx does not define more than 3 standalone format functions", () => {
    const source = readSource(DASHBOARD_PATH);
    // Count top-level `function format` declarations
    const formatFnCount = (source.match(/^function format/gm) || []).length;
    expect(
      formatFnCount,
      `DashboardOrOnboarding.tsx defines ${formatFnCount} format functions inline, expected ≤3`,
    ).toBeLessThanOrEqual(3);
  });
});
