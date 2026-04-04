/**
 * RED-TEAM tests for RUN-559: PriorityBanner migration.
 *
 * Source-reading pattern: verify that old banner components are deleted and
 * CanvasPage integrates the new PriorityBanner.
 *
 * AC6: ExploreBanner and UncommittedBanner are deleted
 * AC7: CanvasPage uses PriorityBanner with EXPLORE + UNCOMMITTED conditions
 *
 * These tests will fail until:
 * - ExploreBanner.tsx and UncommittedBanner.tsx are deleted
 * - CanvasPage imports and renders PriorityBanner
 * - Old banner tests are removed or updated
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

const EXPLORE_BANNER_PATH = "features/canvas/ExploreBanner.tsx";
const UNCOMMITTED_BANNER_PATH = "features/canvas/UncommittedBanner.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const PRIORITY_BANNER_PATH = "components/shared/PriorityBanner.tsx";

// ===========================================================================
// 1. Old banner files are deleted (AC6)
// ===========================================================================

describe("Old banner files are deleted (AC6)", () => {
  it("ExploreBanner.tsx is deleted from canvas feature", () => {
    expect(
      fileExists(EXPLORE_BANNER_PATH),
      "Expected features/canvas/ExploreBanner.tsx to be removed",
    ).toBe(false);
  });

  it("UncommittedBanner.tsx is deleted from canvas feature", () => {
    expect(
      fileExists(UNCOMMITTED_BANNER_PATH),
      "Expected features/canvas/UncommittedBanner.tsx to be removed",
    ).toBe(false);
  });
});

// ===========================================================================
// 2. CanvasPage no longer imports old banners (AC6)
// ===========================================================================

describe("CanvasPage no longer imports old banners (AC6)", () => {
  it("CanvasPage does NOT import ExploreBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).not.toMatch(/import.*ExploreBanner.*from/);
  });

  it("CanvasPage does NOT import UncommittedBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).not.toMatch(/import.*UncommittedBanner.*from/);
  });

  it("CanvasPage does NOT render <ExploreBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).not.toMatch(/<ExploreBanner/);
  });

  it("CanvasPage does NOT render <UncommittedBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).not.toMatch(/<UncommittedBanner/);
  });
});

// ===========================================================================
// 3. CanvasPage integrates PriorityBanner (AC7)
// ===========================================================================

describe("CanvasPage integrates PriorityBanner (AC7)", () => {
  it("CanvasPage imports PriorityBanner from shared components", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(
      /import.*PriorityBanner.*from.*(?:components\/shared\/PriorityBanner|@\/components\/shared)/,
    );
  });

  it("CanvasPage renders <PriorityBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<PriorityBanner/);
  });

  it("CanvasPage passes conditions prop to PriorityBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<PriorityBanner[^>]*conditions\s*=/);
  });

  it("CanvasPage provides an explore condition with active flag", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should build a condition with type: "explore" and an active flag
    // based on provider count (0 providers = active)
    expect(source).toMatch(/["']explore["']/);
  });

  it("CanvasPage provides an uncommitted condition with active flag", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should build a condition with type: "uncommitted" and an active flag
    // based on git status (is_clean === false = active)
    expect(source).toMatch(/["']uncommitted["']/);
  });
});

// ===========================================================================
// 4. PriorityBanner is exported from shared barrel (optional but expected)
// ===========================================================================

describe("PriorityBanner available from shared barrel", () => {
  it("PriorityBanner.tsx exists in components/shared/", () => {
    expect(
      fileExists(PRIORITY_BANNER_PATH),
      "Expected components/shared/PriorityBanner.tsx to exist",
    ).toBe(true);
  });

  it("shared/index.ts re-exports PriorityBanner", () => {
    const source = readSource("components/shared/index.ts");
    expect(source).toMatch(/PriorityBanner/);
  });
});

// ===========================================================================
// 5. No stale references to old banners across the codebase
// ===========================================================================

describe("No stale references to old banner components", () => {
  it("CanvasPage does not reference ExploreBanner in any form", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).not.toMatch(/\bExploreBanner\b/);
  });

  it("CanvasPage does not reference UncommittedBanner in any form", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).not.toMatch(/\bUncommittedBanner\b/);
  });
});
