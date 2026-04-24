import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as sharedZod from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

const SHARED_SRC = resolve(__dirname, "..");
const apiSource = readFileSync(resolve(SHARED_SRC, "api.ts"), "utf8");

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

describe("RUN-967 generated regression API contracts", () => {
  it("generated api.ts no longer exposes unknown for the run regressions endpoint", () => {
    const operationBlock = apiSource.match(
      /get_run_regressions_api_runs__run_id__regressions_get:[\s\S]*?(?=\n {4}\w|\n}\nexport)/,
    )?.[0];

    expect(operationBlock).toBeTruthy();
    expect(operationBlock).toContain(
      '"application/json": components["schemas"]["RunRegressionsResponse"]',
    );
    expect(operationBlock).not.toContain('"application/json": unknown');
  });

  it("generated api.ts no longer exposes unknown for the workflow regressions endpoint", () => {
    const operationBlock = apiSource.match(
      /get_workflow_regressions_api_workflows__id__regressions_get:[\s\S]*?(?=\n {4}\w|\n}\nexport)/,
    )?.[0];

    expect(operationBlock).toBeTruthy();
    expect(operationBlock).toContain(
      '"application/json": components["schemas"]["WorkflowRegressionsResponse"]',
    );
    expect(operationBlock).not.toContain('"application/json": unknown');
  });

  it("generated api.ts defines canonical run and workflow regression components", () => {
    expect(apiSource).toContain("RunRegressionIssue: {");
    expect(apiSource).toContain("RunRegressionsResponse: {");
    expect(apiSource).toContain("WorkflowRegressionIssue: {");
    expect(apiSource).toContain("WorkflowRegressionsResponse: {");
  });
});

describe("RUN-967 canonical shared regression Zod exports", () => {
  it("exports a run regressions response schema with the run-level issue shape", () => {
    const issueSchema = getSchema("RunRegressionIssueSchema");
    const responseSchema = getSchema("RunRegressionsResponseSchema");

    expect(Object.keys(issueSchema.shape).sort()).toEqual(["delta", "node_id", "node_name", "type"]);

    const parsed = responseSchema.parse({
      count: 2,
      issues: [
        {
          node_id: "review",
          node_name: "Review",
          type: "assertion_regression",
          delta: { eval_passed: false },
        },
        {
          node_id: "writer",
          node_name: "Writer",
          type: "cost_spike",
          delta: { cost_pct: 42 },
        },
      ],
    }) as { count: number; issues: Array<{ type: string }> };

    expect(parsed.count).toBe(2);
    expect(parsed.issues.map((issue) => issue.type)).toEqual([
      "assertion_regression",
      "cost_spike",
    ]);
  });

  it("exports a workflow regressions response schema with optional run context", () => {
    const issueSchema = getSchema("WorkflowRegressionIssueSchema");
    const responseSchema = getSchema("WorkflowRegressionsResponseSchema");

    expect(Object.keys(issueSchema.shape).sort()).toEqual([
      "delta",
      "node_id",
      "node_name",
      "run_id",
      "run_number",
      "type",
    ]);

    const parsed = responseSchema.parse({
      count: 1,
      issues: [
        {
          node_id: "score",
          node_name: "Score",
          type: "quality_drop",
          delta: { score_delta: -0.22 },
          run_id: "run_967",
          run_number: 7,
        },
      ],
    }) as { issues: Array<{ run_id?: string; run_number?: number | null; type: string }> };

    expect(parsed.issues[0]).toMatchObject({
      type: "quality_drop",
      run_id: "run_967",
      run_number: 7,
    });
  });

  it("restricts regression type values to the backend transport contract", () => {
    const runIssueSchema = getSchema("RunRegressionIssueSchema");
    const workflowIssueSchema = getSchema("WorkflowRegressionIssueSchema");
    const baseIssue = {
      node_id: "node",
      node_name: "Node",
      delta: {},
    };

    expect(runIssueSchema.parse({ ...baseIssue, type: "assertion_regression" })).toBeTruthy();
    expect(runIssueSchema.parse({ ...baseIssue, type: "cost_spike" })).toBeTruthy();
    expect(workflowIssueSchema.parse({ ...baseIssue, type: "quality_drop" })).toBeTruthy();
    expect(() => runIssueSchema.parse({ ...baseIssue, type: "new_baseline" })).toThrow();
  });
});
