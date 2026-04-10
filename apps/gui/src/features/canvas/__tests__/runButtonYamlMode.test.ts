/**
 * RED-TEAM tests for RUN-419: Run button permanently disabled in YAML mode.
 *
 * Bug: RunButton.tsx uses `useCanvasStore((s) => s.nodes)` and checks
 * `isEmpty = !nodes.length`. In YAML mode, nodes are never populated so the
 * Run button is permanently disabled even when YAML has blocks.
 *
 * Fix: RunButton should derive isEmpty from `blockCount` (store) OR
 * `nodes.length`, whichever is > 0.
 *
 * AC:
 *   AC1: Run button enabled when YAML has at least one block (blockCount > 0)
 *   AC2: Run button disabled when YAML is empty (blockCount === 0 AND nodes.length === 0)
 *   AC3: Works in both YAML mode and canvas mode
 *
 * All tests are expected to FAIL because:
 *   - RunButton currently only reads `nodes` from the store, not `blockCount`
 *   - isEmpty is derived solely from `!nodes.length`
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

const RUN_BUTTON_PATH = "features/surface/RunButton.tsx";

// ===========================================================================
// 1. RunButton reads blockCount from the store (AC1, AC3)
// ===========================================================================

describe("RunButton reads blockCount from canvas store (RUN-419)", () => {
  it("subscribes to blockCount from useCanvasStore", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // RunButton must select blockCount from the store, e.g.:
    //   const blockCount = useCanvasStore((s) => s.blockCount);
    //   OR useCanvasStore((s) => s.blockCount)
    expect(source).toMatch(/useCanvasStore\(\s*\(s\)\s*=>\s*s\.blockCount\s*\)/);
  });

  it("has a local binding for blockCount", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // There should be a `blockCount` variable assignment in the component
    expect(source).toMatch(/(?:const|let)\s+blockCount\s*=/);
  });
});

// ===========================================================================
// 2. isEmpty logic considers blockCount, not just nodes.length (AC1, AC2)
// ===========================================================================

describe("RunButton isEmpty considers blockCount (RUN-419)", () => {
  it("isEmpty is NOT derived solely from nodes.length", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The current bug: `const isEmpty = !nodes.length;`
    // After fix, isEmpty must also consider blockCount.
    // This test fails if isEmpty is ONLY based on nodes.length.
    const isEmptyLine = source.match(/const\s+isEmpty\s*=\s*(.+);/);
    expect(isEmptyLine, "Expected an isEmpty assignment").toBeTruthy();

    const isEmptyExpr = isEmptyLine![1];
    expect(
      isEmptyExpr,
      "isEmpty expression must reference blockCount, not just nodes",
    ).toMatch(/blockCount/);
  });

  it("isEmpty is false when blockCount > 0 even if nodes is empty", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The isEmpty derivation must combine both signals:
    //   e.g. `const isEmpty = !nodes.length && !blockCount;`
    //   or   `const isEmpty = nodes.length === 0 && blockCount === 0;`
    // Either way, blockCount > 0 should make isEmpty false.
    const isEmptyLine = source.match(/const\s+isEmpty\s*=\s*(.+);/);
    expect(isEmptyLine).toBeTruthy();

    const expr = isEmptyLine![1];
    // Must be a compound expression that uses both nodes and blockCount
    const usesNodes = /nodes/.test(expr);
    const usesBlockCount = /blockCount/.test(expr);
    expect(
      usesNodes && usesBlockCount,
      `isEmpty expression must combine nodes AND blockCount. Got: "${expr}"`,
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Button not disabled in YAML mode when blockCount > 0 (AC1)
// ===========================================================================

describe("RunButton enabled in YAML mode with blocks (RUN-419 AC1)", () => {
  it("disabled prop references isEmpty which accounts for blockCount", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The disabled prop is `disabled={isEmpty && !isRunning}`
    // This is fine as long as isEmpty accounts for blockCount.
    // Verify the full chain: isEmpty must include blockCount in its derivation.
    const isEmptyLine = source.match(/const\s+isEmpty\s*=\s*(.+);/);
    expect(isEmptyLine).toBeTruthy();

    const expr = isEmptyLine![1];
    // After fix: `!nodes.length && !blockCount` or equivalent
    // The expression should produce false when blockCount > 0
    // We verify by checking that blockCount is negated or compared to 0
    const blockCountNegated =
      /!blockCount|blockCount\s*===\s*0|blockCount\s*<=\s*0|blockCount\s*<\s*1/.test(
        expr,
      );
    expect(
      blockCountNegated,
      `isEmpty must treat blockCount > 0 as "not empty". Got: "${expr}"`,
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Tooltip also respects blockCount (AC1, AC2)
// ===========================================================================

describe("RunButton tooltip respects blockCount (RUN-419)", () => {
  it("tooltip wrapper condition uses isEmpty which includes blockCount", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The tooltip wrapping condition is: `if (isEmpty && !isRunning)`
    // This is correct as long as isEmpty includes blockCount.
    // We re-verify the isEmpty derivation includes blockCount to ensure
    // the tooltip also disappears when YAML has blocks.
    const isEmptyLine = source.match(/const\s+isEmpty\s*=\s*(.+);/);
    expect(isEmptyLine).toBeTruthy();
    expect(isEmptyLine![1]).toMatch(/blockCount/);
  });
});

// ===========================================================================
// 5. Works in canvas mode too — nodes.length still considered (AC3)
// ===========================================================================

describe("RunButton still works in canvas mode (RUN-419 AC3)", () => {
  it("isEmpty still considers nodes.length for canvas mode", () => {
    const source = readSource(RUN_BUTTON_PATH);
    const isEmptyLine = source.match(/const\s+isEmpty\s*=\s*(.+);/);
    expect(isEmptyLine).toBeTruthy();

    const expr = isEmptyLine![1];
    // Must still reference nodes (for canvas mode where nodes are populated)
    expect(expr).toMatch(/nodes/);
  });

  it("nodes selector is still present for canvas mode", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The existing nodes selector should remain
    expect(source).toMatch(/useCanvasStore\(\s*\(s\)\s*=>\s*s\.nodes\s*\)/);
  });
});
