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
      workflow_id: "workflow_run_contract",
      branch: "sim/workflow_run_contract/20260330/abc12",
      source: "simulation",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.branch).toBe("sim/workflow_run_contract/20260330/abc12");
      expect(result.data.source).toBe("simulation");
    }
  });

  it("RunCreateSchema rejects missing branch", () => {
    const result = RunCreateSchema.safeParse({
      workflow_id: "workflow_run_contract",
      source: "simulation",
    });

    expect(result.success).toBe(false);
  });

  it("RunResponseSchema preserves branch, source, and commit_sha", () => {
    const result = RunResponseSchema.safeParse({
      id: "run_contract_primary",
      workflow_id: "workflow_run_contract",
      workflow_name: "Run contract workflow",
      status: "pending",
      started_at: null,
      completed_at: null,
      duration_seconds: null,
      total_cost_usd: 0,
      total_tokens: 0,
      created_at: 123,
      branch: "sim/workflow_run_contract/20260330/abc12",
      source: "simulation",
      commit_sha: "1234567890abcdef1234567890abcdef12345678",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.branch).toBe("sim/workflow_run_contract/20260330/abc12");
      expect(result.data.source).toBe("simulation");
      expect(result.data.commit_sha).toBe("1234567890abcdef1234567890abcdef12345678");
    }
  });

  it("RunResponseSchema preserves regression_count values and defaults omitted counts", () => {
    const baseRun = {
      id: "run_regression_primary",
      workflow_id: "workflow_regression_count",
      workflow_name: "Research Flow",
      status: "completed",
      started_at: 100,
      completed_at: 130,
      duration_seconds: 30,
      total_cost_usd: 0.05,
      total_tokens: 500,
      created_at: 100,
      branch: "main",
      source: "manual",
    };

    expect(RunResponseSchema.shape).toHaveProperty("regression_count");
    expect(RunResponseSchema.parse({ ...baseRun, regression_count: 3 })).toHaveProperty(
      "regression_count",
      3,
    );
    expect(RunResponseSchema.parse({ ...baseRun, regression_count: 0 })).toHaveProperty(
      "regression_count",
      0,
    );
    expect(RunResponseSchema.parse({ ...baseRun, regression_count: null })).toHaveProperty(
      "regression_count",
      null,
    );
    expect(RunResponseSchema.parse(baseRun).regression_count).toBe(0);
  });

  it("RunResponseSchema rejects missing branch", () => {
    const result = RunResponseSchema.safeParse({
      id: "run_contract_primary",
      workflow_id: "workflow_run_contract",
      workflow_name: "Run contract workflow",
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
          id: "run_contract_primary",
          workflow_id: "workflow_run_contract",
          workflow_name: "Run contract workflow",
          status: "completed",
          started_at: 100,
          completed_at: 101,
          duration_seconds: 1,
          total_cost_usd: 0.01,
          total_tokens: 42,
          created_at: 99,
          branch: "sim/workflow_run_contract/20260330/abc12",
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
      expect(result.data.items[0]?.branch).toBe(
        "sim/workflow_run_contract/20260330/abc12",
      );
      expect(result.data.items[0]?.source).toBe("simulation");
      expect(result.data.items[0]?.commit_sha).toBe(
        "1234567890abcdef1234567890abcdef12345678",
      );
    }
  });

  it("RunListResponseSchema preserves regression_count on list items", () => {
    const result = RunListResponseSchema.safeParse({
      items: [
        {
          id: "run_regression_primary",
          workflow_id: "workflow_regression_count",
          workflow_name: "Research Flow",
          status: "completed",
          started_at: 100,
          completed_at: 130,
          duration_seconds: 30,
          total_cost_usd: 0.05,
          total_tokens: 500,
          created_at: 100,
          branch: "main",
          source: "manual",
          regression_count: 2,
        },
        {
          id: "run_regression_secondary",
          workflow_id: "workflow_regression_count",
          workflow_name: "Research Flow",
          status: "failed",
          started_at: 200,
          completed_at: 230,
          duration_seconds: 30,
          total_cost_usd: 0.08,
          total_tokens: 800,
          created_at: 200,
          branch: "main",
          source: "manual",
          regression_count: 0,
        },
      ],
      total: 2,
      offset: 0,
      limit: 20,
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.items[0]).toHaveProperty("regression_count", 2);
      expect(result.data.items[1]).toHaveProperty("regression_count", 0);
    }
  });

  it("RunListResponseSchema rejects list items missing branch", () => {
    const result = RunListResponseSchema.safeParse({
      items: [
        {
          id: "run_contract_primary",
          workflow_id: "workflow_run_contract",
          workflow_name: "Run contract workflow",
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
      workflow_id: "workflow_run_contract",
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
