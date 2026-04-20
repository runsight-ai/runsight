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

describe("RUN-927 shared workflow simulation contracts", () => {
  it("WorkflowSimulationResponseSchema exposes the prepared input_schema alongside branch identity", () => {
    const workflowResponseSchema = getSchema("WorkflowResponseSchema");
    const simulationSchema = getSchema("WorkflowSimulationResponseSchema");

    expect(simulationSchema.shape).toHaveProperty("branch");
    expect(simulationSchema.shape).toHaveProperty("commit_sha");
    expect(simulationSchema.shape).toHaveProperty("input_schema");
    expect(workflowResponseSchema.shape).toHaveProperty("input_schema");

    const parsed = simulationSchema.parse({
      branch: "sim/wf_927_dirty/20260419/abc12",
      commit_sha: "1234567890abcdef1234567890abcdef12345678",
      input_schema: {
        query: {
          type: "string",
          required: true,
          default: null,
          description: "Search query",
          sensitive: false,
        },
      },
    }) as {
      branch: string;
      commit_sha: string;
      input_schema?: Record<
        string,
        {
          type: string;
          required: boolean;
          default: string | null;
          description: string | null;
          sensitive: boolean;
        }
      >;
    };

    expect(parsed.branch).toBe("sim/wf_927_dirty/20260419/abc12");
    expect(parsed.commit_sha).toBe("1234567890abcdef1234567890abcdef12345678");
    expect(parsed).toHaveProperty("input_schema");
    expect(parsed.input_schema).toEqual({
      query: {
        type: "string",
        required: true,
        default: null,
        description: "Search query",
        sensitive: false,
      },
    });
  });
});
