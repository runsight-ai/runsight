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

describe("RUN-840/842 warning contracts", () => {
  const warningPayload = {
    message: "Tool definition warning",
    source: "tool_definitions",
    context: "lookup_profile",
  };

  it("exports WarningItemSchema with canonical warning payload fields", () => {
    const warningSchema = getSchema("WarningItemSchema");

    expect(Object.keys(warningSchema.shape).sort()).toEqual([
      "context",
      "message",
      "source",
    ]);
    expect(warningSchema.parse(warningPayload)).toEqual(
      expect.objectContaining(warningPayload),
    );
    expect(
      warningSchema.safeParse({
        ...warningPayload,
        code: "W001",
        severity: "warning",
      }).success,
    ).toBe(false);
    expect(
      "RunWarningItemSchema" in (sharedZod as Record<string, unknown>),
      "Duplicate warning schema exports are not allowed",
    ).toBe(false);
  });

  it("WorkflowResponseSchema declares warnings and parses warning payloads", () => {
    const workflowSchema = getSchema("WorkflowResponseSchema");

    expect(workflowSchema.shape).toHaveProperty("warnings");

    const parsed = workflowSchema.parse({
      id: "wf_1",
      warnings: [warningPayload],
    });

    expect(parsed).toHaveProperty("warnings");
    expect((parsed as { warnings: unknown[] }).warnings).toHaveLength(1);
    expect((parsed as { warnings: unknown[] }).warnings[0]).toEqual(
      expect.objectContaining(warningPayload),
    );

    const nullContextResult = workflowSchema.safeParse({
      id: "wf_1",
      warnings: [
        {
          message: "Tool definition warning",
          source: "tool_definitions",
          context: null,
        },
      ],
    });

    expect(nullContextResult.success).toBe(true);
    expect(
      workflowSchema.safeParse({
        id: "wf_1",
        warnings: [
          {
            message: "Tool definition warning",
            source: "tool_definitions",
            context: { tool_id: "lookup_profile" },
          },
        ],
      }).success,
    ).toBe(false);
  });

  it("RunResponseSchema declares warnings and parses warning payloads", () => {
    const runSchema = getSchema("RunResponseSchema");

    expect(runSchema.shape).toHaveProperty("warnings");

    const parsed = runSchema.parse({
      id: "run_1",
      workflow_id: "wf_1",
      workflow_name: "Workflow",
      status: "pending",
      started_at: null,
      completed_at: null,
      duration_seconds: null,
      total_cost_usd: 0,
      total_tokens: 0,
      created_at: 123.0,
      warnings: [warningPayload],
    });

    expect(parsed).toHaveProperty("warnings");
    expect((parsed as { warnings: unknown[] }).warnings).toHaveLength(1);
    expect((parsed as { warnings: unknown[] }).warnings[0]).toEqual(
      expect.objectContaining(warningPayload),
    );

    expect(
      runSchema.safeParse({
        id: "run_1",
        workflow_id: "wf_1",
        workflow_name: "Workflow",
        status: "pending",
        started_at: null,
        completed_at: null,
        duration_seconds: null,
        total_cost_usd: 0,
        total_tokens: 0,
        created_at: 123.0,
        warnings: [
          {
            message: "Tool definition warning",
            source: "tool_definitions",
            context: { tool_id: "lookup_profile" },
          },
        ],
      }).success,
    ).toBe(false);
  });
});
