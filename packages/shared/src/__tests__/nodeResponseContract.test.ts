/**
 * Run node response enrichment contract smoke.
 *
 * The shared schema must preserve API enrichment fields used by GUI run-detail
 * and evaluation views.
 */

import { describe, expect, it } from "vitest";
import { RunNodeResponseSchema } from "../zod";

const ENRICHMENT_FIELDS = [
  "output",
  "soul_id",
  "model_name",
  "eval_score",
  "eval_passed",
  "eval_results",
] as const;

describe("RunNodeResponseSchema enrichment smoke", () => {
  it("keeps enrichment fields on the public schema shape", () => {
    for (const field of ENRICHMENT_FIELDS) {
      expect(RunNodeResponseSchema.shape).toHaveProperty(field);
    }
  });

  it("parses an enriched node and preserves nullable enrichment values", () => {
    const evalResults = {
      coherence: { score: 0.9, passed: true },
      factuality: { score: 0.7, passed: false },
    };

    const parsed = RunNodeResponseSchema.parse({
      id: "research_run:writer_step",
      run_id: "research_run",
      node_id: "writer_step",
      block_type: "llm",
      status: "completed",
      started_at: 1000,
      completed_at: 2000,
      duration_seconds: 1,
      cost_usd: 0.05,
      tokens: { prompt: 100, completion: 50, total: 150 },
      error: null,
      output: "Full LLM response",
      soul_id: "soul_planner",
      model_name: "fixture-eval-model",
      eval_score: 0.88,
      eval_passed: true,
      eval_results: evalResults,
      child_run_id: null,
      exit_handle: null,
    });

    expect(parsed).toEqual(
      expect.objectContaining({
        output: "Full LLM response",
        soul_id: "soul_planner",
        model_name: "fixture-eval-model",
        eval_score: 0.88,
        eval_passed: true,
        eval_results: evalResults,
        child_run_id: null,
        exit_handle: null,
      }),
    );
  });
});
