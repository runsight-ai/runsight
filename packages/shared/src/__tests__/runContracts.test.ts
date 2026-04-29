import { describe, expect, it } from "vitest";
import {
  RunCreateSchema,
  RunListResponseSchema,
  RunNodeResponseSchema,
  RunResponseSchema,
} from "../zod";

describe("shared run contracts", () => {
  it("RunCreateSchema accepts explicit branch and source for dirty simulation runs", () => {
    const result = RunCreateSchema.safeParse({
      workflow_id: "wf_1",
      branch: "sim/wf_1/20260330/abc12",
      source: "simulation",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.branch).toBe("sim/wf_1/20260330/abc12");
      expect(result.data.source).toBe("simulation");
    }
  });

  it("RunCreateSchema rejects missing branch", () => {
    const result = RunCreateSchema.safeParse({
      workflow_id: "wf_1",
      source: "simulation",
    });

    expect(result.success).toBe(false);
  });

  it("RunResponseSchema preserves branch, source, and commit_sha", () => {
    const result = RunResponseSchema.safeParse({
      id: "run_1",
      workflow_id: "wf_1",
      workflow_name: "Test Flow",
      status: "pending",
      started_at: null,
      completed_at: null,
      duration_seconds: null,
      total_cost_usd: 0,
      total_tokens: 0,
      created_at: 123,
      branch: "sim/wf_1/20260330/abc12",
      source: "simulation",
      commit_sha: "1234567890abcdef1234567890abcdef12345678",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.branch).toBe("sim/wf_1/20260330/abc12");
      expect(result.data.source).toBe("simulation");
      expect(result.data.commit_sha).toBe("1234567890abcdef1234567890abcdef12345678");
    }
  });

  it("RunResponseSchema rejects missing branch", () => {
    const result = RunResponseSchema.safeParse({
      id: "run_1",
      workflow_id: "wf_1",
      workflow_name: "Test Flow",
      status: "pending",
      started_at: null,
      completed_at: null,
      duration_seconds: null,
      total_cost_usd: 0,
      total_tokens: 0,
      created_at: 123,
      source: "simulation",
      commit_sha: "1234567890abcdef1234567890abcdef12345678",
    });

    expect(result.success).toBe(false);
  });

  it("RunListResponseSchema exposes branch, source, and commit_sha on list items", () => {
    const result = RunListResponseSchema.safeParse({
      items: [
        {
          id: "run_1",
          workflow_id: "wf_1",
          workflow_name: "Test Flow",
          status: "completed",
          started_at: 100,
          completed_at: 101,
          duration_seconds: 1,
          total_cost_usd: 0.01,
          total_tokens: 42,
          created_at: 99,
          branch: "sim/wf_1/20260330/abc12",
          source: "simulation",
          commit_sha: "1234567890abcdef1234567890abcdef12345678",
        },
      ],
      total: 1,
      offset: 0,
      limit: 20,
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.items[0]?.branch).toBe("sim/wf_1/20260330/abc12");
      expect(result.data.items[0]?.source).toBe("simulation");
      expect(result.data.items[0]?.commit_sha).toBe(
        "1234567890abcdef1234567890abcdef12345678",
      );
    }
  });

  it("RunListResponseSchema rejects list items missing branch", () => {
    const result = RunListResponseSchema.safeParse({
      items: [
        {
          id: "run_1",
          workflow_id: "wf_1",
          workflow_name: "Test Flow",
          status: "completed",
          started_at: 100,
          completed_at: 101,
          duration_seconds: 1,
          total_cost_usd: 0.01,
          total_tokens: 42,
          created_at: 99,
          source: "simulation",
          commit_sha: "1234567890abcdef1234567890abcdef12345678",
        },
      ],
      total: 1,
      offset: 0,
      limit: 20,
    });

    expect(result.success).toBe(false);
  });

  it("RunResponseSchema preserves parent/child lineage fields", () => {
    const result = RunResponseSchema.safeParse({
      id: "run_child",
      workflow_id: "wf_1",
      workflow_name: "Child Flow",
      status: "completed",
      started_at: 100,
      completed_at: 120,
      duration_seconds: 20,
      total_cost_usd: 0.5,
      total_tokens: 500,
      created_at: 99,
      branch: "main",
      source: "manual",
      commit_sha: null,
      run_number: 2,
      eval_pass_pct: null,
      regression_count: null,
      node_summary: null,
      parent_run_id: "run_parent",
      root_run_id: "run_root",
      depth: 1,
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.parent_run_id).toBe("run_parent");
      expect(result.data.root_run_id).toBe("run_root");
      expect(result.data.depth).toBe(1);
    }
  });

  it("RunNodeResponseSchema preserves child run and exit-handle fields", () => {
    const result = RunNodeResponseSchema.safeParse({
      id: "run_parent:workflow_call",
      run_id: "run_parent",
      node_id: "workflow_call",
      block_type: "workflow",
      status: "completed",
      started_at: 100,
      completed_at: 110,
      duration_seconds: 10,
      cost_usd: 0.05,
      tokens: { prompt: 100, completion: 50, total: 150 },
      error: null,
      child_run_id: "run_child",
      exit_handle: "success",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.child_run_id).toBe("run_child");
      expect(result.data.exit_handle).toBe("success");
    }
  });
});
