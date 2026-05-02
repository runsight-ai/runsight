import * as sharedZod from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

type ParseableSchema = {
  parse: (input: unknown) => unknown;
  shape: Record<string, unknown>;
};

function getSchema(name: string): ParseableSchema {
  const schema = (sharedZod as Record<string, unknown>)[name];

  expect(
    schema && typeof (schema as { parse?: unknown }).parse === "function",
    `Expected ${name} to be exported from @runsight/shared/zod`,
  ).toBe(true);

  return schema as ParseableSchema;
}

describe("canonical shared regression contract smoke", () => {
  it("exports and parses run and workflow regression responses", () => {
    const runIssueSchema = getSchema("RunRegressionIssueSchema");
    const runResponseSchema = getSchema("RunRegressionsResponseSchema");
    const workflowIssueSchema = getSchema("WorkflowRegressionIssueSchema");
    const workflowResponseSchema = getSchema("WorkflowRegressionsResponseSchema");

    expect(runIssueSchema.shape).toEqual(
      expect.objectContaining({
        node_id: expect.anything(),
        node_name: expect.anything(),
        type: expect.anything(),
        delta: expect.anything(),
      }),
    );
    expect(workflowIssueSchema.shape).toEqual(
      expect.objectContaining({
        run_id: expect.anything(),
        run_number: expect.anything(),
      }),
    );

    const runParsed = runResponseSchema.parse({
      count: 1,
      issues: [
        {
          node_id: "review",
          node_name: "Review",
          type: "assertion_regression",
          delta: { eval_passed: false },
        },
      ],
    }) as { count: number; issues?: Array<{ type: string }> };

    const workflowParsed = workflowResponseSchema.parse({
      count: 1,
      issues: [
        {
          node_id: "score",
          node_name: "Score",
          type: "quality_drop",
          delta: { score_delta: -0.22 },
          run_id: "run_regression_shared",
          run_number: 7,
        },
      ],
    }) as { issues?: Array<{ run_id?: string | null; run_number?: number | null }> };

    expect(runParsed.count).toBe(1);
    expect(runParsed.issues?.[0]?.type).toBe("assertion_regression");
    expect(workflowParsed.issues?.[0]).toEqual(
      expect.objectContaining({
        run_id: "run_regression_shared",
        run_number: 7,
      }),
    );
  });

  it("restricts regression type values to the transport contract", () => {
    const runIssueSchema = getSchema("RunRegressionIssueSchema");
    const baseIssue = {
      node_id: "node",
      node_name: "Node",
      delta: {},
    };

    expect(runIssueSchema.parse({ ...baseIssue, type: "cost_spike" })).toBeTruthy();
    expect(() => runIssueSchema.parse({ ...baseIssue, type: "new_baseline" })).toThrow();
  });
});
