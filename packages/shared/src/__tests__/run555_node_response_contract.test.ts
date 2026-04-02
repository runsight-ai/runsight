/**
 * RUN-555: RunNodeResponseSchema enrichment contract tests.
 *
 * Red-team tests — these MUST fail until RunNodeResponseSchema in zod.ts
 * is updated with: output, soul_id, model_name, eval_score, eval_passed,
 * eval_results.
 */

import { describe, it, expect } from "vitest";
import { RunNodeResponseSchema } from "../zod";

// ---------------------------------------------------------------------------
// 1. Schema shape declares the 6 enrichment fields
// ---------------------------------------------------------------------------

describe("RUN-555: RunNodeResponseSchema has enrichment fields", () => {
  it("schema shape includes output field", () => {
    expect(RunNodeResponseSchema.shape).toHaveProperty("output");
  });

  it("schema shape includes soul_id field", () => {
    expect(RunNodeResponseSchema.shape).toHaveProperty("soul_id");
  });

  it("schema shape includes model_name field", () => {
    expect(RunNodeResponseSchema.shape).toHaveProperty("model_name");
  });

  it("schema shape includes eval_score field", () => {
    expect(RunNodeResponseSchema.shape).toHaveProperty("eval_score");
  });

  it("schema shape includes eval_passed field", () => {
    expect(RunNodeResponseSchema.shape).toHaveProperty("eval_passed");
  });

  it("schema shape includes eval_results field", () => {
    expect(RunNodeResponseSchema.shape).toHaveProperty("eval_results");
  });
});

// ---------------------------------------------------------------------------
// 2. Parsing preserves the 6 enrichment fields in parsed output
// ---------------------------------------------------------------------------

describe("RUN-555: RunNodeResponseSchema parses enriched payloads", () => {
  const baseNode = {
    id: "run_1:step_1",
    run_id: "run_1",
    node_id: "step_1",
    block_type: "llm",
    status: "completed",
    started_at: 1000,
    completed_at: 2000,
    duration_seconds: 1.0,
    cost_usd: 0.05,
    tokens: { prompt: 100, completion: 50, total: 150 },
    error: null,
  };

  it("parsed output preserves output field value", () => {
    const enriched = { ...baseNode, output: "The capital of France is Paris." };
    const result = RunNodeResponseSchema.parse(enriched);
    expect(result).toHaveProperty("output", "The capital of France is Paris.");
  });

  it("parsed output preserves soul_id field value", () => {
    const enriched = { ...baseNode, soul_id: "soul_analyst" };
    const result = RunNodeResponseSchema.parse(enriched);
    expect(result).toHaveProperty("soul_id", "soul_analyst");
  });

  it("parsed output preserves model_name field value", () => {
    const enriched = { ...baseNode, model_name: "gpt-4.1" };
    const result = RunNodeResponseSchema.parse(enriched);
    expect(result).toHaveProperty("model_name", "gpt-4.1");
  });

  it("parsed output preserves eval_score field value", () => {
    const enriched = { ...baseNode, eval_score: 0.95 };
    const result = RunNodeResponseSchema.parse(enriched);
    expect(result).toHaveProperty("eval_score", 0.95);
  });

  it("parsed output preserves eval_passed field value", () => {
    const enriched = { ...baseNode, eval_passed: true };
    const result = RunNodeResponseSchema.parse(enriched);
    expect(result).toHaveProperty("eval_passed", true);
  });

  it("parsed output preserves eval_results dict value", () => {
    const evalResults = {
      coherence: { score: 0.9, passed: true },
      factuality: { score: 0.7, passed: false },
    };
    const enriched = { ...baseNode, eval_results: evalResults };
    const result = RunNodeResponseSchema.parse(enriched);
    expect(result).toHaveProperty("eval_results");
    expect(result.eval_results).toEqual(evalResults);
  });

  it("parsed output preserves null values for all 6 enrichment fields", () => {
    const nulled = {
      ...baseNode,
      output: null,
      soul_id: null,
      model_name: null,
      eval_score: null,
      eval_passed: null,
      eval_results: null,
    };
    const result = RunNodeResponseSchema.parse(nulled);
    expect(result).toHaveProperty("output", null);
    expect(result).toHaveProperty("soul_id", null);
    expect(result).toHaveProperty("model_name", null);
    expect(result).toHaveProperty("eval_score", null);
    expect(result).toHaveProperty("eval_passed", null);
    expect(result).toHaveProperty("eval_results", null);
  });
});

// ---------------------------------------------------------------------------
// 3. Exported TypeScript type includes the 6 fields (compile-time contract)
//    At runtime we verify by checking parsed keys.
// ---------------------------------------------------------------------------

describe("RUN-555: RunNodeResponseSchema all 6 fields round-trip", () => {
  it("a fully enriched node round-trips all 6 fields through parse", () => {
    const input = {
      id: "run_1:step_1",
      run_id: "run_1",
      node_id: "step_1",
      block_type: "llm",
      status: "completed",
      started_at: 1000,
      completed_at: 2000,
      duration_seconds: 1.0,
      cost_usd: 0.05,
      tokens: { prompt: 100, completion: 50, total: 150 },
      error: null,
      output: "Full LLM response",
      soul_id: "soul_planner",
      model_name: "claude-3-5-sonnet",
      eval_score: 0.88,
      eval_passed: true,
      eval_results: { check_1: { passed: true, score: 1.0 } },
    };

    const parsed = RunNodeResponseSchema.parse(input);
    const keys = Object.keys(parsed);
    expect(keys).toContain("output");
    expect(keys).toContain("soul_id");
    expect(keys).toContain("model_name");
    expect(keys).toContain("eval_score");
    expect(keys).toContain("eval_passed");
    expect(keys).toContain("eval_results");
  });
});
