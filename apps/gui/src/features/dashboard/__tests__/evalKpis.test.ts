/**
 * RED-TEAM tests for RUN-342: A5 — KPI Eval Pass Rate + Regressions — end-to-end.
 *
 * These tests verify frontend acceptance criteria by reading source files
 * as strings and asserting observable structural properties:
 *
 * AC1: StatCard for "Eval Pass" shows percentage format (not "—") when data exists
 * AC2: StatCard for "Regressions" uses "success" variant when 0, "warning" when >0
 * AC3: Eval Pass StatCard uses "success" variant when >= 80%
 *
 * Expected failures (current state):
 *   - Eval Pass card has no variant logic (always "default")
 *   - Regressions card uses "default" when 0, not "success"
 *   - No "success" variant for Eval Pass card at any threshold
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
// 1. Eval Pass shows percentage format when data exists (AC1)
// ===========================================================================

describe("Eval Pass shows percentage format when data exists (AC1)", () => {
  it("formats eval_pass_rate as a percentage string (e.g. '85%')", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should have logic like: `${(eval_pass_rate * 100).toFixed(0)}%`
    // or similar percentage formatting
    expect(source).toMatch(/eval.*pass.*100.*%|toFixed.*%|percent/i);
  });

  it("shows percentage when eval_pass_rate is not null (not em-dash)", () => {
    const source = readSource(DASHBOARD_PATH);
    // Must have a conditional: if eval_pass_rate != null, show percentage, else "—"
    const hasConditionalPercent =
      /eval_pass_rate\s*!=\s*null.*%|eval_pass_rate\s*!==\s*null.*%/.test(source) ||
      /eval.*pass.*!=\s*null.*toFixed/.test(source);
    expect(
      hasConditionalPercent,
      "Expected conditional percentage display for non-null eval_pass_rate",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. Regressions uses "success" variant when 0, "warning" when >0 (AC2)
// ===========================================================================

describe("Regressions StatCard variant logic (AC2)", () => {
  it('uses "warning" variant when regressions > 0', () => {
    const source = readSource(DASHBOARD_PATH);
    // This pattern already exists — verify it stays
    expect(source).toMatch(/regressions.*>.*0.*\?.*["']warning["']/);
  });

  it('uses "success" variant when regressions is 0', () => {
    const source = readSource(DASHBOARD_PATH);
    // Regressions card should show "success" when count is 0 (no regressions = good)
    // Pattern: regressions === 0 ? "success" or regressions != null && regressions === 0 ? "success"
    // or a ternary like: regressions > 0 ? "warning" : "success"
    const hasSuccessForZero =
      /regressions.*===?\s*0.*["']success["']/.test(source) ||
      /regressions.*>\s*0\s*\?\s*["']warning["']\s*:\s*["']success["']/.test(source);
    expect(
      hasSuccessForZero,
      'Expected "success" variant when regressions count is 0',
    ).toBe(true);
  });

  it("regressions card has three-way variant: null=default, 0=success, >0=warning", () => {
    const source = readSource(DASHBOARD_PATH);
    // When regressions is null (no data) -> "default"
    // When regressions is 0 -> "success" (all good)
    // When regressions > 0 -> "warning" (regressions detected)
    // All three variants should be present in the regressions StatCard logic
    const hasDefault = /["']default["']/.test(source);
    const hasSuccess = /["']success["']/.test(source);
    const hasWarning = /["']warning["']/.test(source);
    expect(hasDefault && hasSuccess && hasWarning).toBe(true);
  });
});

// ===========================================================================
// 3. Eval Pass uses "success" variant when >= 80% (AC3)
// ===========================================================================

describe("Eval Pass StatCard uses success variant for high pass rate (AC3)", () => {
  it('Eval Pass card has variant logic (not always "default")', () => {
    const source = readSource(DASHBOARD_PATH);
    // The Eval Pass StatCard should have a variant prop that is conditionally set
    // Currently: <StatCard label="Eval Pass" value={evalPassDisplay} />
    // Expected: <StatCard label="Eval Pass" value={evalPassDisplay} variant={...} />
    //
    // Find the Eval Pass StatCard and check it has a variant prop
    const evalPassCardMatch = source.match(
      /label\s*=\s*["']Eval Pass["'][^>]*>/,
    );
    expect(evalPassCardMatch).not.toBeNull();

    const cardTag = evalPassCardMatch![0];
    expect(cardTag).toMatch(/variant\s*=/);
  });

  it('uses "success" variant when eval_pass_rate >= 0.8', () => {
    const source = readSource(DASHBOARD_PATH);
    // Pattern: eval_pass_rate >= 0.8 ? "success" : "default"
    // or: eval_pass_rate != null && eval_pass_rate >= 0.8 ? "success" : ...
    const hasSuccessThreshold =
      /eval.*pass.*>=?\s*0\.8.*["']success["']/.test(source) ||
      /eval.*pass.*>=?\s*80.*["']success["']/.test(source);
    expect(
      hasSuccessThreshold,
      'Expected "success" variant when eval pass rate >= 80%',
    ).toBe(true);
  });

  it('uses "default" or "neutral" variant when eval_pass_rate < 80%', () => {
    const source = readSource(DASHBOARD_PATH);
    // The eval pass card should not show success when below threshold
    // Should have a conditional: >= 0.8 ? "success" : "default"
    const hasConditional =
      /eval.*pass.*>=?\s*0\.8\s*\?\s*["']success["']\s*:\s*["']default["']/.test(source) ||
      /eval.*pass.*>=?\s*80\s*\?\s*["']success["']\s*:\s*["']default["']/.test(source);
    expect(
      hasConditional,
      "Expected conditional variant with default fallback for < 80% pass rate",
    ).toBe(true);
  });
});
