/**
 * RUN-558: RunResponseSchema regression_count contract tests.
 *
 * Red-team tests -- these MUST fail until RunResponseSchema in zod.ts
 * is updated with: regression_count: z.number().nullable().optional()
 *
 * AC2: RunResponseSchema in packages/shared/src/zod.ts updated with regression_count
 */

import { describe, it, expect } from "vitest";
import { RunResponseSchema, RunListResponseSchema } from "../zod";

// ---------------------------------------------------------------------------
// 1. Schema shape declares regression_count
// ---------------------------------------------------------------------------

describe("RUN-558: RunResponseSchema has regression_count field", () => {
  it("schema shape includes regression_count", () => {
    expect(RunResponseSchema.shape).toHaveProperty("regression_count");
  });
});

// ---------------------------------------------------------------------------
// 2. Parsing preserves regression_count in various forms
// ---------------------------------------------------------------------------

describe("RUN-558: RunResponseSchema parses regression_count", () => {
  const baseRun = {
    id: "run_001",
    workflow_id: "wf_1",
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

  it("parsed output preserves a numeric regression_count", () => {
    const input = { ...baseRun, regression_count: 3 };
    const result = RunResponseSchema.parse(input);
    expect(result).toHaveProperty("regression_count", 3);
  });

  it("parsed output preserves regression_count = 0", () => {
    const input = { ...baseRun, regression_count: 0 };
    const result = RunResponseSchema.parse(input);
    expect(result).toHaveProperty("regression_count", 0);
  });

  it("parsed output preserves regression_count = null", () => {
    const input = { ...baseRun, regression_count: null };
    const result = RunResponseSchema.parse(input);
    expect(result).toHaveProperty("regression_count", null);
  });

  it("parsed output defaults regression_count when omitted", () => {
    // Field is optional, so omitting it should not throw
    const result = RunResponseSchema.parse(baseRun);
    // The value should be undefined or null (optional field)
    expect(result).toHaveProperty("regression_count");
  });
});

// ---------------------------------------------------------------------------
// 3. RunListResponseSchema round-trips regression_count in items
// ---------------------------------------------------------------------------

describe("RUN-558: RunListResponseSchema round-trips regression_count", () => {
  it("list items preserve regression_count through parse", () => {
    const payload = {
      items: [
        {
          id: "run_001",
          workflow_id: "wf_1",
          workflow_name: "Research Flow",
          status: "completed",
          started_at: 100,
          completed_at: 130,
          duration_seconds: 30,
          total_cost_usd: 0.05,
          total_tokens: 500,
          created_at: 100,
          regression_count: 2,
        },
        {
          id: "run_002",
          workflow_id: "wf_1",
          workflow_name: "Research Flow",
          status: "failed",
          started_at: 200,
          completed_at: 230,
          duration_seconds: 30,
          total_cost_usd: 0.08,
          total_tokens: 800,
          created_at: 200,
          regression_count: 0,
        },
      ],
      total: 2,
      offset: 0,
      limit: 20,
    };

    const result = RunListResponseSchema.parse(payload);
    expect(result.items[0]).toHaveProperty("regression_count", 2);
    expect(result.items[1]).toHaveProperty("regression_count", 0);
  });
});
