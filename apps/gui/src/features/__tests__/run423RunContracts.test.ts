import { describe, expect, it } from "vitest";
import {
  RunCreateSchema,
  RunListResponseSchema,
  RunResponseSchema,
} from "@runsight/shared/zod";

describe("RUN-423 shared run contracts", () => {
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
});
