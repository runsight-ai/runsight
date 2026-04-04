/**
 * RED-TEAM tests for RUN-612: child run drill-down.
 *
 * Problem: The run detail page needs to surface child runs spawned by
 * workflow-call blocks, and the per-workflow run history needs to surface
 * child-run relationships. Currently the frontend has no concept of child
 * runs — no hook, no API method, and the Zod schemas are missing the
 * parent/child linkage fields.
 *
 * AC:
 * 1. Current run view surfaces child runs for that run.
 * 2. Per-workflow run history surfaces child-run relationships.
 * 3. Header remains root-run totals only.
 * 4. No UI fallback that reconstructs relationships heuristically.
 *
 * Changes required:
 * - RunResponseSchema gains parent_run_id, root_run_id, depth.
 * - RunNodeResponseSchema gains child_run_id, exit_handle.
 * - New useChildRuns hook in queries/runs.ts.
 * - New getChildRuns method in api/runs.ts.
 * - Query key for children in queries/keys.ts.
 */

import { describe, it, expect } from "vitest";
import { RunResponseSchema, RunNodeResponseSchema } from "@runsight/shared/zod";

// ---------------------------------------------------------------------------
// 1. RunResponseSchema includes parent linkage fields
// ---------------------------------------------------------------------------

describe("RunResponseSchema child linkage fields (RUN-612)", () => {
  it("accepts parent_run_id as a nullable string", () => {
    const valid = RunResponseSchema.safeParse({
      id: "run_612",
      workflow_id: "wf_1",
      workflow_name: "Test Workflow",
      status: "completed",
      started_at: 100.0,
      completed_at: 120.0,
      duration_seconds: 20.0,
      total_cost_usd: 0.5,
      total_tokens: 500,
      created_at: 100.0,
      branch: "main",
      source: "manual",
      commit_sha: null,
      run_number: 1,
      eval_pass_pct: null,
      regression_count: null,
      node_summary: null,
      parent_run_id: "run_parent_1",
      root_run_id: "run_root_1",
      depth: 1,
    });

    expect(valid.success).toBe(true);
    if (valid.success) {
      expect(valid.data.parent_run_id).toBe("run_parent_1");
    }
  });

  it("accepts root_run_id as a nullable string", () => {
    const valid = RunResponseSchema.safeParse({
      id: "run_612",
      workflow_id: "wf_1",
      workflow_name: "Test Workflow",
      status: "completed",
      started_at: 100.0,
      completed_at: 120.0,
      duration_seconds: 20.0,
      total_cost_usd: 0.5,
      total_tokens: 500,
      created_at: 100.0,
      parent_run_id: null,
      root_run_id: "run_root_1",
      depth: 0,
    });

    expect(valid.success).toBe(true);
    if (valid.success) {
      expect(valid.data.root_run_id).toBe("run_root_1");
    }
  });

  it("accepts depth as a number", () => {
    const valid = RunResponseSchema.safeParse({
      id: "run_612",
      workflow_id: "wf_1",
      workflow_name: "Test Workflow",
      status: "completed",
      started_at: 100.0,
      completed_at: 120.0,
      duration_seconds: 20.0,
      total_cost_usd: 0.5,
      total_tokens: 500,
      created_at: 100.0,
      parent_run_id: null,
      root_run_id: null,
      depth: 2,
    });

    expect(valid.success).toBe(true);
    if (valid.success) {
      expect(valid.data.depth).toBe(2);
    }
  });

  it("exposes parent_run_id, root_run_id, depth in the inferred TypeScript type", () => {
    // This is a compile-time check: if RunResponse doesn't have these fields,
    // the test file itself won't compile. At runtime we verify the schema
    // shape includes the keys.
    const shape = RunResponseSchema.shape;
    expect(shape).toHaveProperty(
      "parent_run_id",
    );
    expect(shape).toHaveProperty(
      "root_run_id",
    );
    expect(shape).toHaveProperty(
      "depth",
    );
  });
});

// ---------------------------------------------------------------------------
// 2. RunNodeResponseSchema includes child linkage fields
// ---------------------------------------------------------------------------

describe("RunNodeResponseSchema child linkage fields (RUN-612)", () => {
  it("accepts child_run_id as a nullable string", () => {
    const valid = RunNodeResponseSchema.safeParse({
      id: "run_612:step_wf",
      run_id: "run_612",
      node_id: "step_wf",
      block_type: "workflow",
      status: "completed",
      started_at: 100.0,
      completed_at: 110.0,
      duration_seconds: 10.0,
      cost_usd: 0.05,
      tokens: { prompt: 100, completion: 50, total: 150 },
      error: null,
      child_run_id: "run_612_child",
      exit_handle: "success",
    });

    expect(valid.success).toBe(true);
    if (valid.success) {
      expect(valid.data.child_run_id).toBe("run_612_child");
    }
  });

  it("accepts exit_handle as a nullable string", () => {
    const valid = RunNodeResponseSchema.safeParse({
      id: "run_612:step_wf",
      run_id: "run_612",
      node_id: "step_wf",
      block_type: "workflow",
      status: "completed",
      started_at: 100.0,
      completed_at: 110.0,
      duration_seconds: 10.0,
      cost_usd: 0.05,
      tokens: { prompt: 100, completion: 50, total: 150 },
      error: null,
      child_run_id: null,
      exit_handle: "success",
    });

    expect(valid.success).toBe(true);
    if (valid.success) {
      expect(valid.data.exit_handle).toBe("success");
    }
  });

  it("exposes child_run_id and exit_handle in the schema shape", () => {
    const shape = RunNodeResponseSchema.shape;
    expect(shape).toHaveProperty(
      "child_run_id",
    );
    expect(shape).toHaveProperty(
      "exit_handle",
    );
  });
});

// ---------------------------------------------------------------------------
// 3. useChildRuns hook exists in queries module
// ---------------------------------------------------------------------------

describe("useChildRuns hook (RUN-612)", () => {
  it("exports useChildRuns from queries/runs", async () => {
    // Dynamic import to check existence at runtime
    const queriesModule = await import("../../../queries/runs");
    expect(queriesModule).toHaveProperty("useChildRuns");
    expect(typeof queriesModule.useChildRuns).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// 4. getChildRuns API method exists
// ---------------------------------------------------------------------------

describe("runsApi.getChildRuns (RUN-612)", () => {
  it("exports getChildRuns from api/runs", async () => {
    const apiModule = await import("../../../api/runs");
    expect(apiModule.runsApi).toHaveProperty("getChildRuns");
    expect(typeof apiModule.runsApi.getChildRuns).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// 5. Query key for children exists
// ---------------------------------------------------------------------------

describe("query key for children (RUN-612)", () => {
  it("queryKeys.runs has a children key factory", async () => {
    const { queryKeys } = await import("../../../queries/keys");
    expect(queryKeys.runs).toHaveProperty("children");
    expect(typeof queryKeys.runs.children).toBe("function");

    const key = (queryKeys.runs.children as (id: string) => readonly string[])("run_1");
    expect(key).toContain("runs");
    expect(key).toContain("run_1");
  });
});
