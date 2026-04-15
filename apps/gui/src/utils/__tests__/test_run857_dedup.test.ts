/**
 * RUN-857 — [CLEANUP] Extract duplicated utility functions
 *
 * Source-inspection tests: assert that duplicate local function definitions
 * have been removed from feature files and that canonical exports exist in
 * @/utils/formatting.ts.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// ── helpers ──────────────────────────────────────────────────────────────────

// __dirname = apps/gui/src/utils/__tests__
// ../../.. lands at apps/gui/src/
function readSrc(relativePath: string): string {
  return readFileSync(
    resolve(__dirname, "../..", relativePath),
    "utf-8",
  );
}

// ── 1. formatCommit exported from @/utils/formatting ────────────────────────

describe("test_formatCommit_exported_from_utils", () => {
  it("exports formatCommit from @/utils/formatting.ts", async () => {
    const mod = await import("../formatting");
    expect(typeof (mod as Record<string, unknown>).formatCommit).toBe("function");
  });
});

// ── 2. getSourceVariant exported from a shared location ─────────────────────

describe("test_getSourceVariant_exported_from_shared", () => {
  it("exports getSourceVariant from @/utils/formatting.ts", async () => {
    const mod = await import("../formatting");
    expect(typeof (mod as Record<string, unknown>).getSourceVariant).toBe("function");
  });
});

// ── 3. No local formatCommit in WorkflowRow ──────────────────────────────────

describe("test_no_formatCommit_in_WorkflowRow", () => {
  it("WorkflowRow.tsx does not define a local formatCommit function", () => {
    const src = readSrc("features/flows/WorkflowRow.tsx");
    // Must not contain a local function declaration for formatCommit
    expect(src).not.toMatch(/function formatCommit\s*\(/);
  });
});

// ── 4. No local formatCommit in RunRow ───────────────────────────────────────

describe("test_no_formatCommit_in_RunRow", () => {
  it("RunRow.tsx does not define a local formatCommit function", () => {
    const src = readSrc("features/runs/RunRow.tsx");
    expect(src).not.toMatch(/function formatCommit\s*\(/);
  });
});

// ── 5. No local getSourceVariant in RunRow ───────────────────────────────────

describe("test_no_getSourceVariant_in_RunRow", () => {
  it("RunRow.tsx does not define a local getSourceVariant function", () => {
    const src = readSrc("features/runs/RunRow.tsx");
    expect(src).not.toMatch(/function getSourceVariant\s*\(/);
  });
});

// ── 6. No local getSourceVariant in SurfaceRunRow ────────────────────────────

describe("test_no_getSourceVariant_in_SurfaceRunRow", () => {
  it("SurfaceRunRow.tsx does not define a local getSourceVariant function", () => {
    const src = readSrc("features/surface/SurfaceRunRow.tsx");
    expect(src).not.toMatch(/function getSourceVariant\s*\(/);
  });
});

// ── 7. No local formatRelativeTime in WorkflowRow ────────────────────────────

describe("test_no_formatRelativeTime_in_WorkflowRow", () => {
  it("WorkflowRow.tsx does not define a local formatRelativeTime function", () => {
    const src = readSrc("features/flows/WorkflowRow.tsx");
    expect(src).not.toMatch(/function formatRelativeTime\s*\(/);
  });
});

// ── 8. No local formatRelativeTime in SoulLibraryPage ────────────────────────

describe("test_no_formatRelativeTime_in_SoulLibraryPage", () => {
  it("SoulLibraryPage.tsx does not define a local formatRelativeTime function", () => {
    const src = readSrc("features/souls/SoulLibraryPage.tsx");
    expect(src).not.toMatch(/function formatRelativeTime\s*\(/);
  });
});

// ── 9. formatCommit handles null ─────────────────────────────────────────────

describe("test_formatCommit_handles_null", () => {
  it("returns 'uncommitted' for null input", async () => {
    const mod = await import("../formatting");
    const formatCommit = (mod as Record<string, unknown>).formatCommit as (
      sha: string | null | undefined,
    ) => string;
    expect(formatCommit(null)).toBe("uncommitted");
    expect(formatCommit(undefined)).toBe("uncommitted");
  });
});

// ── 10. formatCommit truncates to 7 characters ───────────────────────────────

describe("test_formatCommit_truncates_to_7_chars", () => {
  it("slices a full SHA to 7 characters", async () => {
    const mod = await import("../formatting");
    const formatCommit = (mod as Record<string, unknown>).formatCommit as (
      sha: string | null | undefined,
    ) => string;
    const fullSha = "abc1234def5678";
    expect(formatCommit(fullSha)).toBe("abc1234");
    expect(formatCommit(fullSha).length).toBe(7);
  });
});
