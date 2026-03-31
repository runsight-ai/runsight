/**
 * RED-TEAM tests for RUN-242: CrudListPage<T> Generic Component.
 *
 * The CRUD list pages share ~95% identical
 * code — search, create/edit modals, delete confirmation, loading/error/empty
 * states. This ticket extracts the pattern into a config-driven generic
 * CrudListPage<T> and a reusable DeleteConfirmDialog.
 *
 * These tests MUST FAIL until the Green Team implements:
 *  - CrudListPage.tsx: generic config-driven component
 *  - DeleteConfirmDialog.tsx: reusable delete confirmation dialog
 *  - list surfaces refactored to use CrudListPage where they still exist
 *
 * Environment: Vitest + Node (no DOM). Tests verify source code structure only.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SHARED_DIR = resolve(__dirname, "..");
const SIDEBAR_DIR = resolve(__dirname, "../../../features/sidebar");

function readSource(dir: string, filename: string): string {
  return readFileSync(resolve(dir, filename), "utf-8");
}

function countLines(source: string): number {
  return source.split("\n").length;
}

// ---------------------------------------------------------------------------
// 1. CrudListPage module — exports and structure (AC2-5)
// ---------------------------------------------------------------------------

describe("CrudListPage module", () => {
  let source: string;

  it("CrudListPage.tsx exists and is readable", () => {
    // This will throw if the file doesn't exist, causing the test to fail
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toBeDefined();
    expect(source.length).toBeGreaterThan(0);
  });

  it("exports CrudListPage", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/export\s+(function|const)\s+CrudListPage/);
  });

  it("uses a TypeScript generic type parameter", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    // Should have generic syntax like CrudListPage<T> or CrudListPageProps<T>
    expect(source).toMatch(/<T[\s,>]/);
  });

  it("defines a config interface with resourceName", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/resourceName\s*[?:]?\s*:\s*string/);
  });

  it("defines a config interface with columns", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/columns\s*[?:]?\s*:/);
  });

  it("defines a config interface with useList hook reference", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/useList\s*[?:]?\s*:/);
  });

  it("defines a config interface with useDelete hook reference", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/useDelete\s*[?:]?\s*:/);
  });

  it("composes with DataTable component", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/import.*DataTable.*from/);
  });

  it("composes with PageHeader component", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/import.*PageHeader.*from/);
  });

  it("composes with EmptyState component", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/import.*EmptyState.*from/);
  });

  it("has search functionality", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    // Should have search state and filtering logic
    expect(source).toMatch(/search/i);
    expect(source).toMatch(/filter/i);
  });

  it("handles loading state", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/isLoading|loading/i);
  });

  it("handles error state", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    expect(source).toMatch(/error/i);
  });

  it("handles empty state", () => {
    source = readSource(SHARED_DIR, "CrudListPage.tsx");
    // Should render EmptyState when no items
    expect(source).toMatch(/EmptyState/);
    expect(source).toMatch(/\.length\s*===\s*0/);
  });
});

// ---------------------------------------------------------------------------
// 2. DeleteConfirmDialog module (AC3)
// ---------------------------------------------------------------------------

describe("DeleteConfirmDialog module", () => {
  let source: string;

  it("DeleteConfirmDialog.tsx exists and is readable", () => {
    source = readSource(SHARED_DIR, "DeleteConfirmDialog.tsx");
    expect(source).toBeDefined();
    expect(source.length).toBeGreaterThan(0);
  });

  it("exports DeleteConfirmDialog", () => {
    source = readSource(SHARED_DIR, "DeleteConfirmDialog.tsx");
    expect(source).toMatch(/export\s+(function|const)\s+DeleteConfirmDialog/);
  });

  it("accepts a resourceName prop", () => {
    source = readSource(SHARED_DIR, "DeleteConfirmDialog.tsx");
    expect(source).toMatch(/resourceName\s*[?:]?\s*:\s*string/);
  });

  it("uses Dialog from shadcn", () => {
    source = readSource(SHARED_DIR, "DeleteConfirmDialog.tsx");
    expect(source).toMatch(/import.*Dialog.*from.*["'](@runsight\/ui\/dialog|@\/components\/ui\/dialog)["']/);
  });

  it("shows confirmation message with resource name", () => {
    source = readSource(SHARED_DIR, "DeleteConfirmDialog.tsx");
    // Should interpolate the resource name into a confirmation message
    expect(source).toMatch(/resourceName|itemName/);
    expect(source).toMatch(/cannot be undone|are you sure/i);
  });

  it("has cancel and confirm actions", () => {
    source = readSource(SHARED_DIR, "DeleteConfirmDialog.tsx");
    expect(source).toMatch(/Cancel/);
    expect(source).toMatch(/Delete|Confirm/);
  });
});

// ---------------------------------------------------------------------------
// 3. SoulList migration (AC1-2)
// ---------------------------------------------------------------------------

describe("SoulList migration", () => {
  let source: string;

  it("SoulList.tsx is under 100 lines", () => {
    source = readSource(SIDEBAR_DIR, "SoulList.tsx");
    const lines = countLines(source);
    expect(lines).toBeLessThanOrEqual(100);
  });

  it("imports and uses CrudListPage", () => {
    source = readSource(SIDEBAR_DIR, "SoulList.tsx");
    expect(source).toMatch(/import.*CrudListPage.*from/);
  });

  it("renders CrudListPage in its return", () => {
    source = readSource(SIDEBAR_DIR, "SoulList.tsx");
    expect(source).toMatch(/<CrudListPage/);
  });

  it("passes a config object with resourceName", () => {
    source = readSource(SIDEBAR_DIR, "SoulList.tsx");
    // Should have resourceName: "Soul" or similar in the config
    expect(source).toMatch(/resourceName.*["']Soul["']/i);
  });

  it("does not have local useState for searchQuery", () => {
    source = readSource(SIDEBAR_DIR, "SoulList.tsx");
    // Search state should now live inside CrudListPage
    expect(source).not.toMatch(/useState.*searchQuery|searchQuery.*useState/);
    expect(source).not.toMatch(/setSearchQuery/);
  });

  it("does not have local useMemo for filtering", () => {
    source = readSource(SIDEBAR_DIR, "SoulList.tsx");
    expect(source).not.toMatch(/useMemo/);
  });

  it("does not have inline delete confirmation dialog", () => {
    source = readSource(SIDEBAR_DIR, "SoulList.tsx");
    // Should not import Dialog directly — DeleteConfirmDialog handles that
    expect(source).not.toMatch(
      /import.*\{[^}]*Dialog[^}]*\}.*from.*["'](@runsight\/ui\/dialog|@\/components\/ui\/dialog)["']/
    );
  });
});
