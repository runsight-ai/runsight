import { describe, expect, it } from "vitest";
import { WorkflowResponseSchema } from "../zod";

describe("WorkflowResponse shared contract", () => {
  const phantomFields = [
    "status",
    "updated_at",
    "created_at",
    "last_run_duration",
    "last_run_cost_usd",
    "last_run_completed_at",
    "step_count",
  ] as const;

  const workflowFields = ["block_count", "modified_at", "enabled", "commit_sha", "health"] as const;

  it("does not expose retired workflow dashboard fields", () => {
    for (const field of phantomFields) {
      expect(WorkflowResponseSchema.shape).not.toHaveProperty(field);
    }
  });

  it("exposes the canonical workflow list fields", () => {
    for (const field of workflowFields) {
      expect(WorkflowResponseSchema.shape).toHaveProperty(field);
    }
  });
});
