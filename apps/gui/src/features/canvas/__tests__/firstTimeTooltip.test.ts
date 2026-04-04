/**
 * RED-TEAM tests for RUN-369: T14 — First-time tooltip (one-shot, localStorage).
 *
 * AC:
 *   - Tooltip visible on first canvas visit
 *   - Auto-dismisses after 8s
 *   - Dismisses on click/keypress
 *   - Never shows again (localStorage)
 *
 * Source-reading tests verify the component exists and follows the expected
 * patterns without requiring DOM rendering.
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

const TOOLTIP_PATH = "features/canvas/FirstTimeTooltip.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. Component exists
// ===========================================================================

describe("FirstTimeTooltip component exists", () => {
  it("FirstTimeTooltip.tsx file exists and is non-empty", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source.length).toBeGreaterThan(0);
  });

  it("exports a FirstTimeTooltip component", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+FirstTimeTooltip/);
  });
});

// ===========================================================================
// 2. localStorage key for one-shot behavior
// ===========================================================================

describe("localStorage persistence (never shows again)", () => {
  it("references a localStorage key for tooltip dismissal", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/localStorage/);
  });

  it("uses a descriptive storage key", () => {
    const source = readSource(TOOLTIP_PATH);
    // Should contain a key like "runsight:firstTimeTooltipDismissed" or similar
    expect(source).toMatch(/runsight[.:_-].*tooltip/i);
  });

  it("reads localStorage on mount to decide visibility", () => {
    const source = readSource(TOOLTIP_PATH);
    // Should call getItem to check if already dismissed
    expect(source).toMatch(/localStorage\.getItem/);
  });

  it("writes localStorage on dismiss", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/localStorage\.setItem/);
  });
});

// ===========================================================================
// 3. Auto-dismiss after 8 seconds
// ===========================================================================

describe("Auto-dismiss after 8s", () => {
  it("uses setTimeout with 8000ms", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/setTimeout\b/);
    expect(source).toMatch(/8000/);
  });

  it("cleans up the timer on unmount (clearTimeout)", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/clearTimeout/);
  });
});

// ===========================================================================
// 4. Event listeners for click/keypress dismissal
// ===========================================================================

describe("Dismiss on click or keypress", () => {
  it("adds a click event listener", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/addEventListener.*click|click.*addEventListener/i);
  });

  it("adds a keydown or keypress event listener", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/addEventListener.*key(down|press)|key(down|press).*addEventListener/i);
  });

  it("removes event listeners on cleanup", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/removeEventListener/);
  });
});

// ===========================================================================
// 5. Accessibility: role="status" and aria-live="polite"
// ===========================================================================

describe("Accessibility attributes", () => {
  it("has role=\"status\"", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/role=["']status["']/);
  });

  it("has aria-live=\"polite\"", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/aria-live=["']polite["']/);
  });
});

// ===========================================================================
// 6. Conditional rendering (null when dismissed)
// ===========================================================================

describe("Conditional rendering", () => {
  it("returns null when tooltip should not be shown", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/return\s+null/);
  });

  it("uses state to track visibility", () => {
    const source = readSource(TOOLTIP_PATH);
    expect(source).toMatch(/useState/);
  });
});

// ===========================================================================
// 7. Rendered in CanvasPage
// ===========================================================================

describe("FirstTimeTooltip is rendered in CanvasPage", () => {
  it("CanvasPage imports FirstTimeTooltip", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import.*FirstTimeTooltip.*from/);
  });

  it("CanvasPage renders <FirstTimeTooltip", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<FirstTimeTooltip/);
  });
});
