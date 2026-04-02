/**
 * RED-TEAM tests for RUN-559: PriorityBanner — unified banner system.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * AC1: Single PriorityBanner component renders at most one banner
 * AC2: Priority order: EXPLORE > UNCOMMITTED > REGRESSIONS
 * AC3: Each type has correct styling (info-blue / warning-amber)
 * AC4: EXPLORE dismiss persists in localStorage
 * AC5: UNCOMMITTED and REGRESSIONS dismiss is session-scoped
 * AC6: ExploreBanner and UncommittedBanner are deleted (see migration test)
 * AC7: CanvasPage uses PriorityBanner with EXPLORE + UNCOMMITTED conditions (see migration test)
 *
 * Edge cases:
 * - No conditions active: renders nothing
 * - Multiple conditions active: only highest-priority renders
 * - Dismiss one banner: next-priority banner does NOT appear
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
// File paths
// ---------------------------------------------------------------------------

const BANNER_PATH = "components/shared/PriorityBanner.tsx";

// ===========================================================================
// 1. PriorityBanner component exists (AC1)
// ===========================================================================

describe("PriorityBanner component exists (AC1)", () => {
  it("PriorityBanner.tsx file exists in components/shared/", () => {
    expect(
      fileExists(BANNER_PATH),
      "Expected components/shared/PriorityBanner.tsx to exist",
    ).toBe(true);
  });

  it("exports PriorityBanner as a named export", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+PriorityBanner/);
  });

  it("exports the BannerCondition type", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/export\s+(interface|type)\s+BannerCondition/);
  });

  it("exports the PriorityBannerProps type", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/export\s+(interface|type)\s+PriorityBannerProps/);
  });
});

// ===========================================================================
// 2. Props interface matches spec
// ===========================================================================

describe("Props interface matches spec", () => {
  it("BannerCondition has a 'type' field with union of explore | uncommitted | regressions", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/type\s*:\s*["']?explore["']?\s*\|/);
    expect(source).toMatch(/uncommitted/);
    expect(source).toMatch(/regressions/);
  });

  it("BannerCondition has an 'active' boolean field", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/active\s*:\s*boolean/);
  });

  it("BannerCondition has an optional 'message' field", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/message\s*\?\s*:\s*string/);
  });

  it("BannerCondition has an optional 'action' field with label and onClick", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/action\s*\?/);
    expect(source).toMatch(/label\s*:\s*string/);
    expect(source).toMatch(/onClick\s*:\s*\(\)/);
  });

  it("PriorityBannerProps has a 'conditions' array of BannerCondition", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/conditions\s*:\s*BannerCondition\[\]/);
  });
});

// ===========================================================================
// 3. Priority ordering: EXPLORE > UNCOMMITTED > REGRESSIONS (AC2)
// ===========================================================================

describe("Priority ordering: EXPLORE > UNCOMMITTED > REGRESSIONS (AC2)", () => {
  it("defines a priority order or ranking for banner types", () => {
    const source = readSource(BANNER_PATH);
    // Should have a priority list, map, or enum defining the order
    const hasPriority =
      /priority|PRIORITY|BANNER_ORDER|BANNER_PRIORITY/.test(source);
    expect(
      hasPriority,
      "Expected a priority ordering definition for banner types",
    ).toBe(true);
  });

  it("explore has higher priority than uncommitted", () => {
    const source = readSource(BANNER_PATH);
    // In the priority list, explore should appear before uncommitted
    const exploreIdx = source.indexOf('"explore"') !== -1
      ? source.indexOf('"explore"')
      : source.indexOf("'explore'");
    const uncommittedIdx = source.indexOf('"uncommitted"') !== -1
      ? source.indexOf('"uncommitted"')
      : source.indexOf("'uncommitted'");
    // If using an array, earlier index = higher priority
    expect(exploreIdx).toBeGreaterThan(-1);
    expect(uncommittedIdx).toBeGreaterThan(-1);
    expect(exploreIdx).toBeLessThan(uncommittedIdx);
  });

  it("uncommitted has higher priority than regressions", () => {
    const source = readSource(BANNER_PATH);
    const uncommittedIdx = source.indexOf('"uncommitted"') !== -1
      ? source.indexOf('"uncommitted"')
      : source.indexOf("'uncommitted'");
    const regressionsIdx = source.indexOf('"regressions"') !== -1
      ? source.indexOf('"regressions"')
      : source.indexOf("'regressions'");
    expect(uncommittedIdx).toBeGreaterThan(-1);
    expect(regressionsIdx).toBeGreaterThan(-1);
    expect(uncommittedIdx).toBeLessThan(regressionsIdx);
  });

  it("selects only one banner to render (at most one banner visible)", () => {
    const source = readSource(BANNER_PATH);
    // Should find the first active condition by priority, not render all
    const hasSingleSelect =
      /find\(|\.find\b|\[0\]|winner|active.*filter|highest|top/.test(source);
    expect(
      hasSingleSelect,
      "Expected logic to select a single winning banner",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Styling: info-blue for EXPLORE, warning-amber for UNCOMMITTED + REGRESSIONS (AC3)
// ===========================================================================

describe("Banner type styling (AC3)", () => {
  it("uses info design tokens for explore banner (info-3, info-7, info-11)", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/info-3/);
    expect(source).toMatch(/info-7/);
    expect(source).toMatch(/info-11/);
  });

  it("uses warning design tokens for uncommitted/regressions banner (warning-3, warning-7, warning-11)", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/warning-3/);
    expect(source).toMatch(/warning-7/);
    expect(source).toMatch(/warning-11/);
  });

  it("maps explore type to info styling", () => {
    const source = readSource(BANNER_PATH);
    // Should have a mapping or conditional that connects explore -> info tokens
    const hasMapping = /explore.*info|info.*explore/s.test(source);
    expect(
      hasMapping,
      "Expected explore type to map to info styling tokens",
    ).toBe(true);
  });

  it("maps uncommitted type to warning styling", () => {
    const source = readSource(BANNER_PATH);
    const hasMapping = /uncommitted.*warning|warning.*uncommitted/s.test(source);
    expect(
      hasMapping,
      "Expected uncommitted type to map to warning styling tokens",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. EXPLORE dismiss persists in localStorage (AC4)
// ===========================================================================

describe("EXPLORE dismiss persists in localStorage (AC4)", () => {
  it("references localStorage for explore dismiss persistence", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/localStorage/);
  });

  it("uses a storage key for explore banner dismiss state", () => {
    const source = readSource(BANNER_PATH);
    // Should have a key string identifying the explore banner dismiss
    expect(source).toMatch(/runsight.*explore.*banner|explore.*dismiss/i);
  });

  it("reads from localStorage on mount for explore type", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/localStorage\.getItem/);
  });

  it("writes to localStorage on dismiss for explore type", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/localStorage\.setItem/);
  });
});

// ===========================================================================
// 6. UNCOMMITTED and REGRESSIONS dismiss is session-scoped (AC5)
// ===========================================================================

describe("UNCOMMITTED and REGRESSIONS dismiss is session-scoped (AC5)", () => {
  it("uses useState for session-scoped dismiss tracking", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/useState/);
  });

  it("does NOT persist uncommitted dismiss to localStorage", () => {
    const source = readSource(BANNER_PATH);
    // The localStorage usage should be specifically for explore, not for
    // uncommitted or regressions. We check there's no "uncommitted" in
    // localStorage key patterns.
    const hasUncommittedStorage =
      /localStorage.*uncommitted|uncommitted.*localStorage/.test(source);
    expect(
      hasUncommittedStorage,
      "Uncommitted dismiss should NOT use localStorage",
    ).toBe(false);
  });

  it("does NOT persist regressions dismiss to localStorage", () => {
    const source = readSource(BANNER_PATH);
    const hasRegressionsStorage =
      /localStorage.*regressions|regressions.*localStorage/.test(source);
    expect(
      hasRegressionsStorage,
      "Regressions dismiss should NOT use localStorage",
    ).toBe(false);
  });
});

// ===========================================================================
// 7. Dismiss handler and dismiss button
// ===========================================================================

describe("Dismiss handler and dismiss button", () => {
  it("renders a dismiss/close button with aria-label", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/aria-label.*[Dd]ismiss/);
  });

  it("has a dismiss handler that tracks dismissed type", () => {
    const source = readSource(BANNER_PATH);
    // The dismiss handler should know which type was dismissed so that
    // the next-priority banner does NOT appear after dismissal
    const hasDismissTracking =
      /dismiss|Dismiss|setDismissed|handleDismiss/.test(source);
    expect(
      hasDismissTracking,
      "Expected dismiss handler that tracks dismissed banner type",
    ).toBe(true);
  });

  it("dismissed banner prevents next-priority from showing (sticky dismiss)", () => {
    const source = readSource(BANNER_PATH);
    // After dismissing the top banner, the component should render nothing,
    // not fall through to the next-priority banner. This requires tracking
    // dismissed types, not just a boolean.
    const tracksDismissedTypes =
      /dismissed.*Set|Set.*dismissed|dismissedTypes|dismissedSet|dismissed\w*\[/.test(source);
    expect(
      tracksDismissedTypes,
      "Expected dismissed types tracking (Set or array) to prevent fallthrough",
    ).toBe(true);
  });
});

// ===========================================================================
// 8. No conditions active: renders nothing
// ===========================================================================

describe("No conditions active renders nothing", () => {
  it("returns null when no conditions are active", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/return\s+null/);
  });

  it("checks active field on conditions before rendering", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/\.active/);
  });
});

// ===========================================================================
// 9. Action button support
// ===========================================================================

describe("Action button support from BannerCondition", () => {
  it("renders the action label when an action is provided", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/action.*label|label.*action/s);
  });

  it("calls action.onClick when the action button is clicked", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/action.*onClick|onClick.*action/s);
  });
});

// ===========================================================================
// 10. Role and accessibility
// ===========================================================================

describe("Accessibility", () => {
  it("uses role='status' for the banner container", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/role\s*=\s*["']status["']/);
  });
});
