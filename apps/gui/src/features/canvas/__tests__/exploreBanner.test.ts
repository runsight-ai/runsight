/**
 * RED-TEAM tests for RUN-366: T11 — Explore mode banner (no API key) + dismiss.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * AC1: Banner visible when 0 providers configured
 * AC2: "add an API key" link opens API key modal
 * AC3: Dismiss persists via localStorage
 * AC4: Hidden when providers exist
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

const BANNER_PATH = "features/canvas/ExploreBanner.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. ExploreBanner component exists
// ===========================================================================

describe("ExploreBanner component exists", () => {
  it("ExploreBanner.tsx file exists", () => {
    expect(
      fileExists(BANNER_PATH),
      "Expected features/canvas/ExploreBanner.tsx to exist",
    ).toBe(true);
  });

  it("exports ExploreBanner as a named export", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+ExploreBanner/);
  });
});

// ===========================================================================
// 2. ExploreBanner imported and rendered in CanvasPage
// ===========================================================================

describe("ExploreBanner integrated into CanvasPage", () => {
  it("CanvasPage imports ExploreBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import.*ExploreBanner.*from.*ExploreBanner/);
  });

  it("CanvasPage renders <ExploreBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ExploreBanner/);
  });
});

// ===========================================================================
// 3. useProviders import for conditional rendering
// ===========================================================================

describe("ExploreBanner uses useProviders hook", () => {
  it("imports useProviders from queries/settings", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/import.*useProviders.*from/);
  });

  it("calls useProviders to get provider data", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/useProviders\(\)/);
  });
});

// ===========================================================================
// 4. localStorage dismiss persistence
// ===========================================================================

describe("Dismiss persists via localStorage (AC3)", () => {
  it("references localStorage in the component", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/localStorage/);
  });

  it("has a dismiss handler or dismiss state", () => {
    const source = readSource(BANNER_PATH);
    const hasDismiss = /dismiss|Dismiss|setDismiss/.test(source);
    expect(hasDismiss, "Expected dismiss state or handler").toBe(true);
  });

  it("uses a storage key for the banner dismiss state", () => {
    const source = readSource(BANNER_PATH);
    // Should have a key string for localStorage
    expect(source).toMatch(/runsight.*explore.*banner|explore.*dismiss/i);
  });
});

// ===========================================================================
// 5. Info styling tokens (--info-3, --info-7, --info-11)
// ===========================================================================

describe("Uses info design tokens for styling", () => {
  it("uses --info-3 token (background)", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/info-3/);
  });

  it("uses --info-7 token (border)", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/info-7/);
  });

  it("uses --info-11 token (text)", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/info-11/);
  });
});

// ===========================================================================
// 6. "add an API key" text present
// ===========================================================================

describe("Banner content and link", () => {
  it("contains 'add an API key' text", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/add an API key/i);
  });

  it("has a clickable element for the API key link", () => {
    const source = readSource(BANNER_PATH);
    // Should have a button or anchor for the link
    const hasClickable = /onClick|<button|<a\s/.test(source);
    expect(hasClickable, "Expected a clickable element for API key link").toBe(true);
  });
});

// ===========================================================================
// 7. Conditional rendering — hidden when providers exist
// ===========================================================================

describe("Conditional rendering based on provider count (AC1, AC4)", () => {
  it("checks provider count or length for conditional render", () => {
    const source = readSource(BANNER_PATH);
    // Should check providers.length === 0 or similar
    const hasCondition = /providers.*length|\.length\s*===?\s*0|!providers|providers\?\.\w/.test(source);
    expect(hasCondition, "Expected conditional check on provider count").toBe(true);
  });

  it("returns null when providers exist (early return pattern)", () => {
    const source = readSource(BANNER_PATH);
    // Should have an early return null when there are providers
    expect(source).toMatch(/return\s+null/);
  });
});
