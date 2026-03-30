/**
 * RED-TEAM tests for RUN-421: Fix — Status bar always shows 0 blocks, 0 edges.
 *
 * Bug: CanvasPage renders <CanvasStatusBar activeTab={activeTab} /> without
 * blockCount/edgeCount props. CanvasStatusBar defaults both to 0.
 *
 * These tests verify the fix acceptance criteria by reading source files:
 *
 * AC1: Status bar shows correct block count
 * AC2: Status bar shows correct edge count
 * AC3: Counts update on YAML change (setYamlContent parses both)
 *
 * Expected failures (current state):
 *   - useCanvasStore has no edgeCount field
 *   - setYamlContent does not parse/count edges from YAML
 *   - CanvasStatusBar does not read counts from the store
 *   - CanvasPage does not pass blockCount/edgeCount to CanvasStatusBar
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

const CANVAS_STORE_PATH = "store/canvas.ts";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const STATUS_BAR_PATH = "features/canvas/CanvasStatusBar.tsx";

// ===========================================================================
// 1. useCanvasStore has edgeCount field (AC2)
// ===========================================================================

describe("useCanvasStore has edgeCount field", () => {
  it("CanvasState interface declares edgeCount: number", () => {
    const source = readSource(CANVAS_STORE_PATH);
    // The interface should have edgeCount as a number field
    expect(source).toMatch(/edgeCount\s*:\s*number/);
  });

  it("initialState includes edgeCount", () => {
    const source = readSource(CANVAS_STORE_PATH);
    // The initial state object should set edgeCount (likely to 0)
    expect(source).toMatch(/edgeCount\s*:\s*0/);
  });
});

// ===========================================================================
// 2. setYamlContent parses both block AND edge counts (AC1, AC2, AC3)
// ===========================================================================

describe("setYamlContent updates both blockCount and edgeCount", () => {
  it("setYamlContent sets edgeCount in the store state", () => {
    const source = readSource(CANVAS_STORE_PATH);
    // The setYamlContent implementation must include edgeCount in the set() call
    // Look for edgeCount being set inside the setYamlContent method
    const setYamlMatch = source.match(
      /setYamlContent\s*:\s*\(content\)\s*=>\s*\{[\s\S]*?\n\s{2}\}/
    );
    expect(
      setYamlMatch,
      "Expected to find setYamlContent method body",
    ).not.toBeNull();

    const methodBody = setYamlMatch![0];
    expect(
      methodBody,
      "Expected setYamlContent to set edgeCount in the store",
    ).toMatch(/edgeCount/);
  });

  it("setYamlContent contains edge/transition parsing logic", () => {
    const source = readSource(CANVAS_STORE_PATH);
    // Extract just the setYamlContent method body (same regex as above)
    const setYamlMatch = source.match(
      /setYamlContent\s*:\s*\(content\)\s*=>\s*\{[\s\S]*?\n\s{2}\}/
    );
    expect(
      setYamlMatch,
      "Expected to find setYamlContent method body",
    ).not.toBeNull();

    const methodBody = setYamlMatch![0];
    // The method should parse edges/transitions from YAML content.
    // Common YAML keys for edges: "transitions", "edges", "connections", "->", "next"
    const hasEdgeParsing =
      /transition|edge|next\s*:|->|target\s*:/.test(methodBody);
    expect(
      hasEdgeParsing,
      "Expected setYamlContent to contain edge/transition parsing logic",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. CanvasStatusBar receives real counts (not defaults) (AC1, AC2)
// ===========================================================================

describe("CanvasStatusBar receives actual counts from the store", () => {
  it("CanvasStatusBar imports useCanvasStore OR CanvasPage passes blockCount and edgeCount props", () => {
    const statusBarSource = readSource(STATUS_BAR_PATH);
    const canvasPageSource = readSource(CANVAS_PAGE_PATH);

    // Option A: CanvasStatusBar reads directly from the store
    const statusBarReadsStore = /useCanvasStore/.test(statusBarSource);

    // Option B: CanvasPage passes both count props to CanvasStatusBar
    // Need both blockCount= and edgeCount= on the CanvasStatusBar JSX
    const pagePassesBlockCount =
      /CanvasStatusBar[\s\S]*?blockCount\s*=/.test(canvasPageSource) ||
      /blockCount=\{/.test(canvasPageSource);
    const pagePassesEdgeCount =
      /CanvasStatusBar[\s\S]*?edgeCount\s*=/.test(canvasPageSource) ||
      /edgeCount=\{/.test(canvasPageSource);
    const pagePassesBothCounts = pagePassesBlockCount && pagePassesEdgeCount;

    expect(
      statusBarReadsStore || pagePassesBothCounts,
      "Expected CanvasStatusBar to read counts from useCanvasStore, or CanvasPage to pass blockCount and edgeCount props",
    ).toBe(true);
  });

  it("if CanvasStatusBar reads from store: it selects both blockCount and edgeCount", () => {
    const source = readSource(STATUS_BAR_PATH);
    const readsStore = /useCanvasStore/.test(source);

    if (!readsStore) {
      // If it doesn't read from the store, then CanvasPage must pass props (covered above).
      // Still need to verify CanvasPage reads them from the store.
      const pageSource = readSource(CANVAS_PAGE_PATH);
      const pageReadsBlockCount = /useCanvasStore[\s\S]*?blockCount/.test(pageSource);
      const pageReadsEdgeCount = /useCanvasStore[\s\S]*?edgeCount/.test(pageSource);
      expect(
        pageReadsBlockCount,
        "Expected CanvasPage to read blockCount from useCanvasStore",
      ).toBe(true);
      expect(
        pageReadsEdgeCount,
        "Expected CanvasPage to read edgeCount from useCanvasStore",
      ).toBe(true);
    } else {
      // CanvasStatusBar reads from store — verify it selects both fields
      expect(
        source,
        "Expected CanvasStatusBar to select blockCount from useCanvasStore",
      ).toMatch(/useCanvasStore\(.*blockCount/s);
      expect(
        source,
        "Expected CanvasStatusBar to select edgeCount from useCanvasStore",
      ).toMatch(/useCanvasStore\(.*edgeCount/s);
    }
  });
});

// ===========================================================================
// 4. CanvasPage no longer renders CanvasStatusBar with only activeTab (AC1, AC2)
// ===========================================================================

describe("CanvasPage wires counts to CanvasStatusBar", () => {
  it("CanvasPage does NOT render CanvasStatusBar with only activeTab (bare render)", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The bug is: <CanvasStatusBar activeTab={activeTab} />
    // After fix, it should either pass count props or the component reads from store.
    // Either way, the bare render pattern should be gone OR CanvasStatusBar should import the store.
    const statusBarSource = readSource(STATUS_BAR_PATH);

    const bareRender = /<CanvasStatusBar\s+activeTab=\{activeTab\}\s*\/>/.test(source);
    const statusBarReadsStore = /useCanvasStore/.test(statusBarSource);

    // If the status bar reads from the store directly, the bare render is acceptable.
    // If it does NOT read from the store, the bare render is the bug.
    if (!statusBarReadsStore) {
      expect(
        bareRender,
        "Expected CanvasPage to pass blockCount and edgeCount to CanvasStatusBar (not just activeTab)",
      ).toBe(false);
    } else {
      // CanvasStatusBar reads from the store — bare render is fine
      expect(statusBarReadsStore).toBe(true);
    }
  });
});
