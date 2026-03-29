/**
 * RED-TEAM tests for RUN-144: RunDetail polling & data display.
 *
 * These tests verify:
 * 1. NodeSummary transport schema has exactly 5 fields (no `killed`)
 * 2. RunDetail uses conditional refetchInterval with useRun — polling when
 *    status is "running"/"pending", stopped when terminal
 * 3. RunDetail renders total_tokens from the run response
 * 4. Edge case: run completes between polls (transition scenario)
 * 5. Integration: useRun hook accepts conditional refetchInterval
 *
 * Approach: We test observable behavior through schema validation, source
 * analysis, and hook contract verification — not internal export names.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { NodeSummarySchema, RunResponseSchema } from "@runsight/shared/zod";

// Read RunDetail source once for behavioral source-level assertions.
// This verifies what the component *does*, not what it *exports*.
const RUN_DETAIL_SOURCE = readFileSync(
  resolve(__dirname, "../RunDetail.tsx"),
  "utf-8"
);

// ---------------------------------------------------------------------------
// 1. Transport NodeSummary schema alignment (frontend)
// ---------------------------------------------------------------------------

describe("NodeSummary transport schema (RUN-144)", () => {
  it("has exactly 5 fields: total, completed, running, pending, failed", () => {
    const shape = NodeSummarySchema.shape;
    const keys = Object.keys(shape).sort();
    expect(keys).toEqual(["completed", "failed", "pending", "running", "total"]);
  });

  it("does NOT have a killed field", () => {
    const shape = NodeSummarySchema.shape;
    expect(shape).not.toHaveProperty("killed");
  });

  it("parses a valid 5-field summary", () => {
    const result = NodeSummarySchema.safeParse({
      total: 5,
      completed: 2,
      running: 1,
      pending: 1,
      failed: 1,
    });
    expect(result.success).toBe(true);
  });

  it("rejects a summary with killed field (strict)", () => {
    const result = NodeSummarySchema.strict().safeParse({
      total: 5,
      completed: 2,
      running: 1,
      pending: 1,
      failed: 1,
      killed: 0,
    });
    expect(result.success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 2. RunDetail polling — useRun must be called with conditional refetchInterval
// ---------------------------------------------------------------------------

describe("RunDetail polling behavior (RUN-144)", () => {
  it("does NOT hardcode refetchInterval: false in the useRun call", () => {
    // RunDetail.tsx currently has: refetchInterval: false
    // This must be changed to a conditional value that polls for active runs.
    //
    // We check the source for the useRun call pattern. The refetchInterval
    // must NOT be a literal `false` — it should be dynamic based on run status.

    // Find the useRun call and its options
    const useRunCallMatch = RUN_DETAIL_SOURCE.match(
      /useRun\s*\(\s*[^,]+,\s*\{[^}]*refetchInterval\s*:\s*([^,}\n]+)/
    );

    expect(useRunCallMatch).not.toBeNull();

    const refetchIntervalValue = useRunCallMatch![1].trim();

    // It must NOT be the literal `false`
    expect(refetchIntervalValue).not.toBe("false");
  });

  it("uses a conditional expression or function for refetchInterval", () => {
    // The refetchInterval passed to useRun should be status-dependent.
    // Acceptable patterns:
    //   - A ternary: status === "running" ? 2000 : false
    //   - A function reference: getRefetchInterval or an inline arrow
    //   - A variable that is computed based on status
    // Unacceptable: a hardcoded value (false, 2000, or any literal)

    const useRunCallMatch = RUN_DETAIL_SOURCE.match(
      /useRun\s*\(\s*[^,]+,\s*\{[^}]*refetchInterval\s*:\s*([^,}\n]+)/
    );
    expect(useRunCallMatch).not.toBeNull();

    const value = useRunCallMatch![1].trim();

    // Must be dynamic: a variable, function call, ternary, or function reference
    const isDynamic =
      // ternary expression
      value.includes("?") ||
      // function reference or call
      value.includes("(") ||
      // variable reference (not a literal)
      /^[a-zA-Z_]/.test(value) && value !== "false" && value !== "undefined";

    expect(isDynamic).toBe(true);
  });

  it("references run status when determining refetchInterval", () => {
    // The component must check the run's status to decide whether to poll.
    // This could be via run.status, run?.status, data?.status, or similar.
    // The status check must influence the refetchInterval value.

    // Look for status-based polling logic near the useRun call
    const hasStatusBasedPolling =
      // Direct status check for polling
      /(?:status|run\.status|run\?\.status|data\.status|data\?\.status)/.test(RUN_DETAIL_SOURCE) &&
      // And a conditional refetchInterval (not hardcoded false)
      /refetchInterval\s*:\s*(?!false)[^\n]+(?:status|running|pending)/.test(RUN_DETAIL_SOURCE);

    // Alternative: a helper function that takes status and returns interval
    const hasPollingHelper =
      /(?:refetchInterval|getRefetchInterval|pollingInterval).*(?:running|pending)/.test(RUN_DETAIL_SOURCE) ||
      /(?:running|pending).*(?:refetchInterval|2000|\d{3,4})/.test(RUN_DETAIL_SOURCE);

    expect(hasStatusBasedPolling || hasPollingHelper).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. RunDetail must display total_tokens in the rendered output
// ---------------------------------------------------------------------------

describe("RunDetail displays total_tokens (RUN-144)", () => {
  it("RunResponseSchema includes total_tokens as a required number field", () => {
    const shape = RunResponseSchema.shape;
    expect(shape).toHaveProperty("total_tokens");
  });

  it("RunResponseSchema parses a response with total_tokens", () => {
    const result = RunResponseSchema.safeParse({
      id: "run-1",
      workflow_id: "wf-1",
      workflow_name: "Test",
      status: "completed",
      started_at: null,
      completed_at: null,
      duration_seconds: null,
      total_cost_usd: 0.042,
      total_tokens: 1500,
      created_at: Date.now() / 1000,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.total_tokens).toBe(1500);
    }
  });

  it("RunDetail component renders total_tokens in its JSX output", () => {
    // RunDetail currently renders total_cost_usd in a badge but does NOT
    // render total_tokens anywhere. This test should FAIL until fixed.
    //
    // We look for total_tokens being referenced in a rendering context —
    // i.e., accessed from the run object and used in JSX, not just as a type.

    const rendersTokens =
      // Direct property access in JSX context: {run.total_tokens} or similar
      RUN_DETAIL_SOURCE.includes("run.total_tokens") ||
      RUN_DETAIL_SOURCE.includes("run?.total_tokens") ||
      // Destructured and rendered
      /\btotal_tokens\b/.test(RUN_DETAIL_SOURCE) &&
        // Must appear in JSX (after return statement), not just in imports/types
        /return\s*\([\s\S]*total_tokens/.test(RUN_DETAIL_SOURCE);

    expect(rendersTokens).toBe(true);
  });

  it("total_tokens is displayed near total_cost_usd in the header area", () => {
    // Both cost and tokens should be visible in the run header for at-a-glance review.
    // Look for total_tokens rendering near the existing total_cost_usd badge.

    const costBadgeIndex = RUN_DETAIL_SOURCE.indexOf("total_cost_usd");
    expect(costBadgeIndex).toBeGreaterThan(-1);

    // total_tokens should appear in the rendered output (anywhere in the component)
    // Ideally near the cost badge, but at minimum it must be rendered.
    const tokenRenderIndex = RUN_DETAIL_SOURCE.indexOf("total_tokens");

    // If total_tokens only appears in type imports or comments, this fails.
    // It must appear in the component body where JSX is returned.
    const returnIndex = RUN_DETAIL_SOURCE.lastIndexOf("return (");
    expect(tokenRenderIndex).toBeGreaterThan(returnIndex);
  });
});

// ---------------------------------------------------------------------------
// 4. Edge case: run completes between polls (transition scenario)
// ---------------------------------------------------------------------------

describe("Run completes between polls — transition edge case (RUN-144)", () => {
  it("useRun hook signature supports function-based refetchInterval for query-aware polling", () => {
    // The useRun hook in queries/runs.ts must accept a function for refetchInterval.
    // This is what enables the "completed between polls" pattern:
    // the function receives the latest query result and can check status to stop.
    //
    // We verify the hook's TypeScript type by reading the source.
    const hooksSource = readFileSync(
      resolve(__dirname, "../../../queries/runs.ts"),
      "utf-8"
    );

    // useRun must accept a function signature for refetchInterval
    const acceptsFunctionInterval =
      hooksSource.includes("(query") ||
      hooksSource.includes("=> number | false") ||
      hooksSource.includes("Function") ||
      // The actual react-query pattern: (query: ...) => number | false | undefined
      /refetchInterval\s*\??\s*:\s*[\s\S]*?\(/.test(hooksSource);

    expect(acceptsFunctionInterval).toBe(true);
  });

  it("the expected polling pattern correctly handles running -> completed transition", () => {
    // This tests the behavioral contract: the refetchInterval function pattern
    // that RunDetail SHOULD use. It must return a polling interval for active
    // statuses and false for terminal ones.

    // This is the expected pattern the Green team should implement:
    const refetchInterval = (query: { state: { data?: { status: string } } }) => {
      const status = query?.state?.data?.status;
      if (status === "running" || status === "pending") return 2000;
      return false;
    };

    // Simulate the transition: running -> running -> completed -> completed
    expect(refetchInterval({ state: { data: { status: "running" } } })).toBe(2000);
    expect(refetchInterval({ state: { data: { status: "running" } } })).toBe(2000);
    // Status changes between polls:
    expect(refetchInterval({ state: { data: { status: "completed" } } })).toBe(false);
    // Stays stopped:
    expect(refetchInterval({ state: { data: { status: "completed" } } })).toBe(false);
  });

  it("the polling pattern handles undefined data (before first response)", () => {
    const refetchInterval = (query: { state: { data?: { status: string } } }) => {
      const status = query?.state?.data?.status;
      if (status === "running" || status === "pending") return 2000;
      return false;
    };

    // Before first response, data is undefined — should not crash
    const result = refetchInterval({ state: { data: undefined } });
    expect(result).toBe(false);
  });

  it("the polling pattern stops on ALL terminal statuses", () => {
    const refetchInterval = (query: { state: { data?: { status: string } } }) => {
      const status = query?.state?.data?.status;
      if (status === "running" || status === "pending") return 2000;
      return false;
    };

    for (const terminal of ["completed", "failed", "cancelled", "error", "success"]) {
      expect(
        refetchInterval({ state: { data: { status: terminal } } })
      ).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// 5. Integration: useRun is called with conditional refetchInterval
// ---------------------------------------------------------------------------

describe("Integration: useRun conditional refetchInterval (RUN-144)", () => {
  it("RunDetail passes refetchInterval that depends on run status — not a static value", () => {
    // This is the core DoD requirement: RunDetail must call useRun with a
    // refetchInterval that is conditional on the run's status.
    //
    // We combine source analysis to verify the integration point:
    // 1. useRun is called (already true — component imports and uses it)
    // 2. refetchInterval is not hardcoded false
    // 3. The interval value references status

    // Verify useRun is imported and called
    expect(RUN_DETAIL_SOURCE).toMatch(/import\s*\{[^}]*useRun[^}]*\}\s*from/);
    expect(RUN_DETAIL_SOURCE).toMatch(/useRun\s*\(/);

    // Extract the full useRun call with its options
    const useRunCall = RUN_DETAIL_SOURCE.match(
      /useRun\s*\([^)]*\{[^}]*\}[^)]*\)/s
    );
    expect(useRunCall).not.toBeNull();

    const callText = useRunCall![0];

    // refetchInterval must not be literal false
    expect(callText).not.toMatch(/refetchInterval\s*:\s*false\b/);

    // refetchInterval should reference something dynamic
    const refetchMatch = callText.match(/refetchInterval\s*:\s*(.+?)(?:[,}])/s);
    expect(refetchMatch).not.toBeNull();

    const intervalExpr = refetchMatch![1].trim();
    // Must not be a boolean or numeric literal — must be a variable, function, or expression
    expect(intervalExpr).not.toMatch(/^(false|true|\d+)$/);
  });
});
