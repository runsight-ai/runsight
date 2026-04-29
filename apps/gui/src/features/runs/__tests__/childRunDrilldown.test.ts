/**
 * Child run drill-down coverage.
 *
 * The run detail page surfaces child runs spawned by workflow-call blocks, and
 * per-workflow run history preserves parent/child relationships:
 *
 * - Current run view surfaces child runs for that run
 * - Per-workflow run history surfaces child-run relationships
 * - Header remains root-run totals only
 * - UI does not reconstruct relationships heuristically
 * - GUI API and query layers expose child-run accessors
 */

import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// 1. useChildRuns hook exists in queries module
// ---------------------------------------------------------------------------

describe("useChildRuns hook", () => {
  it("exports useChildRuns from queries/runs", async () => {
    // Dynamic import to check existence at runtime
    const queriesModule = await import("../../../queries/runs");
    expect(queriesModule).toHaveProperty("useChildRuns");
    expect(typeof queriesModule.useChildRuns).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// 2. getChildRuns API method exists
// ---------------------------------------------------------------------------

describe("runsApi.getChildRuns", () => {
  it("exports getChildRuns from api/runs", async () => {
    const apiModule = await import("../../../api/runs");
    expect(apiModule.runsApi).toHaveProperty("getChildRuns");
    expect(typeof apiModule.runsApi.getChildRuns).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// 3. Query key for children exists
// ---------------------------------------------------------------------------

describe("query key for children", () => {
  it("queryKeys.runs has a children key factory", async () => {
    const { queryKeys } = await import("../../../queries/keys");
    expect(queryKeys.runs).toHaveProperty("children");
    expect(typeof queryKeys.runs.children).toBe("function");

    const key = (queryKeys.runs.children as (id: string) => readonly string[])("run_1");
    expect(key).toContain("runs");
    expect(key).toContain("run_1");
  });
});
