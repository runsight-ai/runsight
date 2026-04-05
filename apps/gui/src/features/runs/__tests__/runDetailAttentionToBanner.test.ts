/**
 * RED-TEAM tests for RUN-561: Replace attention cards with PriorityBanner.
 *
 * These tests verify the 5 acceptance criteria:
 *
 * AC1: Attention items card section removed from Run Detail
 * AC2: PriorityBanner renders below header with REGRESSIONS condition
 * AC3: Banner shows "N regressions found" when run has regressions
 * AC4: Banner dismissible with x, session-scoped
 * AC5: No attention cards remain — data lives in Regressions tab instead
 *
 * Expected failures (current state):
 *   - RunDetail still imports useAttentionItems from queries/dashboard
 *   - RunDetail still renders the attention Card section
 *   - PriorityBanner is not imported or rendered in RunDetail
 *   - useRunRegressions is not wired into RunDetail
 *   - AlertTriangle / Activity icons for attention section still present
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

const RUN_DETAIL_PATH = "features/runs/RunDetail.tsx";

// ===========================================================================
// AC1: Attention items card section removed from Run Detail
// ===========================================================================

describe("AC1: Attention items card section removed (RUN-561)", () => {
  it("does NOT import useAttentionItems from queries/dashboard", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).not.toMatch(/import.*useAttentionItems.*from/);
  });

  it("does NOT call useAttentionItems", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).not.toMatch(/useAttentionItems\s*\(/);
  });

  it("does NOT reference attentionItems variable", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).not.toMatch(/attentionItems/);
  });

  it("does NOT reference attentionData variable", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).not.toMatch(/attentionData/);
  });

  it("does NOT contain attentionItems.length > 0 guard", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).not.toMatch(/attentionItems\.length\s*>\s*0/);
  });

  it("does NOT import Card from @runsight/ui/card (no longer needed for attention)", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // Card was imported for the attention items section and the error card.
    // After refactor, if Card is still used for the error boundary card, that's OK.
    // But the attention section's Card rendering must be gone.
    expect(src).not.toMatch(/attentionItems\.map/);
  });
});

// ===========================================================================
// AC2: PriorityBanner renders below header with REGRESSIONS condition
// ===========================================================================

describe("AC2: PriorityBanner renders below header with REGRESSIONS condition (RUN-561)", () => {
  it("imports PriorityBanner from shared components", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).toMatch(/import.*PriorityBanner.*from/);
  });

  it("renders <PriorityBanner> in JSX", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).toMatch(/<PriorityBanner[\s/>]/);
  });

  it("passes conditions prop with regressions type to PriorityBanner", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // The conditions array must include a condition with type "regressions"
    expect(src).toMatch(/type:\s*["']regressions["']/);
  });

  it("imports useRunRegressions to feed PriorityBanner", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).toMatch(/import.*useRunRegressions.*from/);
  });

  it("calls useRunRegressions in RunDetail", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).toMatch(/useRunRegressions\s*\(/);
  });

  it("PriorityBanner appears after RunDetailHeader in the JSX tree", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // PriorityBanner must render below RunDetailHeader, not above or inside it
    const headerIdx = src.indexOf("<RunDetailHeader");
    const bannerIdx = src.indexOf("<PriorityBanner");
    expect(headerIdx).toBeGreaterThan(-1);
    expect(bannerIdx).toBeGreaterThan(-1);
    expect(bannerIdx).toBeGreaterThan(headerIdx);
  });
});

// ===========================================================================
// AC3: Banner shows "N regressions found" when run has regressions
// ===========================================================================

describe("AC3: Banner message includes regression count (RUN-561)", () => {
  it("builds a message string containing 'regressions found'", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // The message passed to the regressions condition should include the count
    // e.g. `${count} regressions found` or `${count} regression(s) found`
    expect(src).toMatch(/regressions?\s*found/i);
  });

  it("regression count is derived from useRunRegressions data", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // Should reference the regression data length or a count property
    const hasCount = /regressions.*\.length|regressionCount|regression.*count/i.test(src);
    expect(hasCount, "Expected regression count derived from useRunRegressions").toBe(true);
  });
});

// ===========================================================================
// AC4: Banner dismissible with x, session-scoped
// ===========================================================================

describe("AC4: Banner is dismissible, session-scoped (RUN-561)", () => {
  it("PriorityBanner component has a dismiss button with aria-label", () => {
    // This verifies the PriorityBanner component itself (already created in RUN-559)
    const src = readSource("components/shared/PriorityBanner.tsx");
    expect(src).toMatch(/aria-label.*[Dd]ismiss/);
  });

  it("regressions condition uses session-scoped dismiss (not localStorage)", () => {
    // PriorityBanner uses dismissedSet (useState Set) for non-explore types,
    // which is session-scoped. The regressions type must NOT use localStorage.
    const src = readSource("components/shared/PriorityBanner.tsx");
    // Only "explore" type uses localStorage — confirm regressions doesn't
    expect(src).not.toMatch(/regressions.*localStorage|localStorage.*regressions/);
  });
});

// ===========================================================================
// AC5: No attention cards remain — data lives in Regressions tab
// ===========================================================================

describe("AC5: No attention cards remain in RunDetail (RUN-561)", () => {
  it("does NOT import AlertTriangle for attention section", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // AlertTriangle was imported from lucide-react for the attention section.
    // After removal, it should no longer be imported in RunDetail
    // (PriorityBanner handles its own icons internally).
    expect(src).not.toMatch(/import.*AlertTriangle.*from.*lucide/);
  });

  it("does NOT import Activity icon (was used in attention cards)", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).not.toMatch(/import.*Activity.*from.*lucide/);
  });

  it("does NOT contain 'Attention' heading in JSX", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // The old section had an "Attention" h2 heading rendered in JSX
    expect(src).not.toMatch(/>\s*Attention\s*</);
  });

  it("does NOT import from queries/dashboard", () => {
    const src = readSource(RUN_DETAIL_PATH);
    expect(src).not.toMatch(/from\s+["']@\/queries\/dashboard["']/);
  });

  it("does NOT render severity-based Badge for attention items", () => {
    const src = readSource(RUN_DETAIL_PATH);
    // The old attention section used Badge with variant={isInfo ? "info" : "warning"}
    // for item.type display. This pattern should be gone.
    expect(src).not.toMatch(/item\.type\.replaceAll/);
  });
});
