/**
 * RED-TEAM tests for RUN-367: T12 — Uncommitted changes banner + commit link.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: UncommittedBanner component exists
 * AC2: Uses useGitStatus hook to detect uncommitted changes
 * AC3: Warning styling uses --warning-3 and --warning-7 tokens
 * AC4: Dismiss button hides banner for this session (useState)
 * AC5: "Commit" link text present for navigating to commit flow
 * AC6: Conditional rendering based on is_clean
 * AC7: Stacks below explore banner when both visible (render order in CanvasPage)
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

const BANNER_PATH = "features/canvas/UncommittedBanner.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. UncommittedBanner component exists (AC1)
// ===========================================================================

describe("UncommittedBanner component exists (AC1)", () => {
  it("UncommittedBanner.tsx file exists in canvas feature", () => {
    expect(
      fileExists(BANNER_PATH),
      "Expected features/canvas/UncommittedBanner.tsx to exist",
    ).toBe(true);
  });

  it("exports a named UncommittedBanner component", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+UncommittedBanner/);
  });
});

// ===========================================================================
// 2. Uses useGitStatus hook (AC2)
// ===========================================================================

describe("Uses useGitStatus hook (AC2)", () => {
  it("imports useGitStatus from queries/git", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/import\s+\{[^}]*useGitStatus[^}]*\}\s+from/);
  });

  it("calls useGitStatus inside the component", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/useGitStatus\(/);
  });
});

// ===========================================================================
// 3. Warning styling tokens (AC3)
// ===========================================================================

describe("Warning styling uses design tokens (AC3)", () => {
  it("uses --warning-3 token for background", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/warning-3/);
  });

  it("uses --warning-7 token for border", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/warning-7/);
  });
});

// ===========================================================================
// 4. Dismiss state (AC4)
// ===========================================================================

describe("Dismiss button hides banner for session (AC4)", () => {
  it("has dismiss state via useState", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/useState.*dismissed|dismissed.*useState/i);
  });

  it("renders a dismiss/close button", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/dismiss|close|×|✕|X\b/i);
  });
});

// ===========================================================================
// 5. Commit link text (AC5)
// ===========================================================================

describe("Commit link navigates to commit flow (AC5)", () => {
  it("renders text containing 'Commit'", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/Commit/);
  });

  it("has a clickable element for commit action", () => {
    const source = readSource(BANNER_PATH);
    // Should use a button with onClick callback for commit action (RUN-422)
    expect(source).toMatch(/<button[^>]*onClick|onCommit/);
  });
});

// ===========================================================================
// 6. Conditional on is_clean (AC6)
// ===========================================================================

describe("Conditional rendering based on is_clean (AC6)", () => {
  it("checks is_clean field from git status", () => {
    const source = readSource(BANNER_PATH);
    expect(source).toMatch(/is_clean/);
  });

  it("returns null or empty when repo is clean", () => {
    const source = readSource(BANNER_PATH);
    // Should have early return for clean state
    expect(source).toMatch(/return\s+null/);
  });
});

// ===========================================================================
// 7. Stacking order in CanvasPage (AC7)
// ===========================================================================

describe("Stacks below explore banner in CanvasPage (AC7)", () => {
  it("CanvasPage imports UncommittedBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import\s+\{[^}]*UncommittedBanner[^}]*\}\s+from/);
  });

  it("CanvasPage renders UncommittedBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<UncommittedBanner/);
  });

  it("UncommittedBanner appears after CanvasTopbar in render order", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    const topbarIdx = source.indexOf("<CanvasTopbar");
    const bannerIdx = source.indexOf("<UncommittedBanner");
    expect(topbarIdx).toBeGreaterThan(-1);
    expect(bannerIdx).toBeGreaterThan(-1);
    expect(bannerIdx).toBeGreaterThan(topbarIdx);
  });
});
