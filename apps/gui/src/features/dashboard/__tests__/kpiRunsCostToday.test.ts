/**
 * RED-TEAM tests for RUN-338: A2 — KPI Runs Today + Cost Today — end-to-end.
 *
 * These tests verify ALL frontend acceptance criteria by reading source files
 * as strings and asserting observable structural properties:
 *
 * AC1: Dashboard imports and renders StatCard components
 * AC2: 4 StatCards render with correct labels (runs today, eval pass rate, cost today, regressions)
 * AC3: useDashboardKPIs hook exists and calls /dashboard
 * AC4: Null eval fields display as "—"
 * AC5: Uses generated Zod schema (DashboardKPIsResponseSchema)
 * AC6: 4 StatCards in a responsive row
 * AC7: Regressions card uses warning variant when regressions > 0
 *
 * Expected failures (current state):
 *   - DashboardOrOnboarding.tsx is a 30-line shell with no StatCards
 *   - useDashboardKPIs hook does not exist (only useDashboardSummary)
 *   - DashboardKPIsResponseSchema does not exist in generated Zod
 *   - api/dashboard.ts uses DashboardResponseSchema, not DashboardKPIsResponseSchema
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");
const SHARED_ZOD_PATH = resolve(
  __dirname,
  "../../../../../../packages/shared/src/zod.ts",
);

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const DASHBOARD_PATH = "features/dashboard/DashboardOrOnboarding.tsx";
const QUERIES_DASHBOARD_PATH = "queries/dashboard.ts";
const API_DASHBOARD_PATH = "api/dashboard.ts";
const QUERY_KEYS_PATH = "queries/keys.ts";

// ===========================================================================
// 1. Dashboard renders StatCard components (AC1)
// ===========================================================================

describe("Dashboard renders StatCard components (AC1)", () => {
  it("imports StatCard from components/ui/stat-card", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*StatCard.*from.*stat-card/);
  });

  it("renders at least 4 StatCard elements", () => {
    const source = readSource(DASHBOARD_PATH);
    const statCardCount = (source.match(/<StatCard\b/g) || []).length;
    expect(statCardCount).toBeGreaterThanOrEqual(4);
  });
});

// ===========================================================================
// 2. StatCard labels (AC2)
// ===========================================================================

describe("4 StatCards with correct labels (AC2)", () => {
  it('has a StatCard with label "runs today"', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/label\s*=\s*["']runs today["']/i);
  });

  it('has a StatCard with label "eval pass rate"', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/label\s*=\s*["']eval pass rate["']/i);
  });

  it('has a StatCard with label "cost today"', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/label\s*=\s*["']cost today["']/i);
  });

  it('has a StatCard with label containing "regressions"', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/label\s*=\s*["']regressions["']/i);
  });
});

// ===========================================================================
// 3. useDashboardKPIs hook (AC3)
// ===========================================================================

describe("useDashboardKPIs hook exists and is wired (AC3)", () => {
  it("queries/dashboard.ts exports a useDashboardKPIs function", () => {
    const source = readSource(QUERIES_DASHBOARD_PATH);
    expect(source).toMatch(/export\s+function\s+useDashboardKPIs/);
  });

  it("useDashboardKPIs calls /dashboard endpoint", () => {
    const source = readSource(QUERIES_DASHBOARD_PATH);
    // The hook should fetch from the /dashboard endpoint
    expect(source).toMatch(/useDashboardKPIs/);
    expect(source).toMatch(/["'`]\/dashboard["'`]/);
  });

  it("Dashboard page imports useDashboardKPIs (not useDashboardSummary)", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/useDashboardKPIs/);
    expect(source).not.toMatch(/useDashboardSummary/);
  });

  it("query keys include dashboard.kpis", () => {
    const source = readSource(QUERY_KEYS_PATH);
    expect(source).toMatch(/kpis/);
  });
});

// ===========================================================================
// 4. Null eval fields display as "—" (AC4)
// ===========================================================================

describe('Null eval fields display as "—" (AC4)', () => {
  it('renders "—" fallback for eval pass rate when null', () => {
    const source = readSource(DASHBOARD_PATH);
    // Should have a pattern like: evalPassRate ? formatPercent(evalPassRate) : "—"
    // or evalPassRate ?? "—" or similar null-handling with em-dash
    expect(source).toMatch(/["']\u2014["']/); // em-dash character
  });

  it("uses nullish coalescing or ternary for eval_pass_rate", () => {
    const source = readSource(DASHBOARD_PATH);
    // Pattern: something like eval_pass_rate ?? "—" or evalPassRate ? ... : "—"
    const hasNullishCoalescing = /eval.*pass.*\?\?/.test(source);
    const hasTernary = /eval.*pass.*\?.*:.*\u2014/.test(source);
    expect(
      hasNullishCoalescing || hasTernary,
      "Expected nullish coalescing (??) or ternary with em-dash for eval_pass_rate",
    ).toBe(true);
  });

  it("uses nullish coalescing or ternary for regressions", () => {
    const source = readSource(DASHBOARD_PATH);
    const hasNullishCoalescing = /regressions.*\?\?/.test(source);
    const hasTernary = /regressions.*\?.*:.*\u2014/.test(source);
    expect(
      hasNullishCoalescing || hasTernary,
      "Expected nullish coalescing (??) or ternary with em-dash for regressions",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Uses generated Zod schema (AC5)
// ===========================================================================

describe("Uses generated Zod schema DashboardKPIsResponseSchema (AC5)", () => {
  it("generated/zod.ts exports DashboardKPIsResponseSchema", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    expect(source).toMatch(/export\s+(const|type)\s+DashboardKPIsResponseSchema/);
  });

  it("DashboardKPIsResponseSchema has runs_today field", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    // The schema should contain runs_today as a z.number() field
    expect(source).toMatch(/runs_today:\s*z\.number\(\)/);
  });

  it("DashboardKPIsResponseSchema has cost_today_usd field", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    expect(source).toMatch(/cost_today_usd:\s*z\.number\(\)/);
  });

  it("DashboardKPIsResponseSchema has eval_pass_rate nullable field", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    expect(source).toMatch(/eval_pass_rate:\s*z\.number\(\)\.nullable\(\)/);
  });

  it("DashboardKPIsResponseSchema has regressions nullable field", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    expect(source).toMatch(/regressions:\s*z\.number\(\)\.nullable\(\)/);
  });

  it("DashboardKPIsResponseSchema has period_hours with default 24", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    expect(source).toMatch(/period_hours:\s*z\.number\(\).*\.default\(24\)/);
  });

  it("api/dashboard.ts imports DashboardKPIsResponseSchema (not old DashboardResponseSchema)", () => {
    const source = readSource(API_DASHBOARD_PATH);
    expect(source).toMatch(/DashboardKPIsResponseSchema/);
  });

  it("api/dashboard.ts uses DashboardKPIsResponseSchema.parse for validation", () => {
    const source = readSource(API_DASHBOARD_PATH);
    expect(source).toMatch(/DashboardKPIsResponseSchema\.parse/);
  });

  it("old DashboardResponseSchema is removed from generated/zod.ts", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    expect(source).not.toMatch(/export\s+const\s+DashboardResponseSchema/);
  });
});

// ===========================================================================
// 6. 4 StatCards in a responsive row (AC6)
// ===========================================================================

describe("StatCards arranged in responsive row (AC6)", () => {
  it("wraps StatCards in a grid or flex container for responsive layout", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should use a grid (grid-cols) or flex row for the 4 cards
    const hasGrid = /grid-cols/.test(source);
    const hasFlex = /flex.*gap|flex-wrap/.test(source);
    expect(
      hasGrid || hasFlex,
      "Expected grid-cols or flex layout for StatCard row",
    ).toBe(true);
  });

  it("has exactly 4 StatCard elements in the dashboard", () => {
    const source = readSource(DASHBOARD_PATH);
    const count = (source.match(/<StatCard\b/g) || []).length;
    expect(count).toBe(4);
  });
});

// ===========================================================================
// 7. Regressions card uses warning variant when > 0 (AC7)
// ===========================================================================

describe("Regressions StatCard uses warning variant (AC7)", () => {
  it('regressions card has conditional variant logic with "warning"', () => {
    const source = readSource(DASHBOARD_PATH);
    // Pattern: variant={regressions > 0 ? "warning" : "default"}
    // or similar conditional variant assignment
    expect(source).toMatch(/variant.*warning/);
  });

  it("regressions variant depends on regressions value being > 0", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/regressions.*>.*0.*\?.*["']warning["']/);
  });
});

// ===========================================================================
// 8. Cost formatting (supplementary)
// ===========================================================================

describe("Cost formatting for spent today", () => {
  it("uses a formatCurrency or dollar-formatting function for cost_today_usd", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should format cost as currency, e.g., formatCurrency(costTodayUsd) or $-prefixed
    const hasFormatCurrency = /formatCurrency/.test(source);
    const hasDollarTemplate = /\$.*cost/i.test(source);
    const hasToFixed = /cost.*toFixed|toFixed.*cost/i.test(source);
    expect(
      hasFormatCurrency || hasDollarTemplate || hasToFixed,
      "Expected currency formatting for cost_today_usd display",
    ).toBe(true);
  });
});

// ===========================================================================
// 9. Old dashboard hooks are replaced with new one
// ===========================================================================

describe("Old dashboard hooks are replaced with useDashboardKPIs", () => {
  it("queries/dashboard.ts exports useDashboardKPIs (not just useDashboardSummary)", () => {
    const source = readSource(QUERIES_DASHBOARD_PATH);
    // The old useDashboardSummary should be replaced by useDashboardKPIs
    expect(source).toMatch(/export\s+function\s+useDashboardKPIs/);
    expect(source).not.toMatch(/export\s+function\s+useDashboardSummary/);
  });

  it("queries/dashboard.ts no longer exports DashboardSummary interface", () => {
    const source = readSource(QUERIES_DASHBOARD_PATH);
    expect(source).not.toMatch(/export\s+interface\s+DashboardSummary/);
  });
});
