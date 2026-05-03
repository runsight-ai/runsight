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

function extractComponentFieldNames(source: string, componentName: string): string[] {
  const pattern = new RegExp(`/\\*\\* ${componentName} \\*/\\s*${componentName}: \\{([\\s\\S]*?)\\n\\s+\\};`);
  const match = source.match(pattern);

  expect(match, `Expected generated api.ts to declare ${componentName}`).not.toBeNull();

  return (match?.[1] ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const fieldMatch = line.match(/^([A-Za-z0-9_]+)\??:/);
      return fieldMatch?.[1] ?? null;
    })
    .filter((field): field is string => field !== null);
}

function extractComponentBlock(
  source: string,
  componentName: string,
  nextComponentName: string,
): string {
  const startMarker = `/** ${componentName} */`;
  const endMarker = `/** ${nextComponentName} */`;
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start);

  expect(start, `Expected generated api.ts to declare ${componentName}`).toBeGreaterThanOrEqual(0);
  expect(end, `Expected generated api.ts to declare ${nextComponentName}`).toBeGreaterThan(start);

  return source.slice(start, end);
}

describe("shared workflow input contract smoke", () => {
  it("RunCreateSchema accepts branch when provided and defaults omitted inputs to an empty object", () => {
    const schema = getSchema("RunCreateSchema");

    const parsed = schema.parse({
      workflow_id: "wf_input_contract",
      branch: "main",
    }) as { workflow_id: string; branch?: string | null; inputs?: Record<string, unknown> };

    expect(parsed).toEqual(
      expect.objectContaining({
        workflow_id: "wf_input_contract",
        branch: "main",
        inputs: {},
      }),
    );

    const omittedBranch = schema.parse({ workflow_id: "wf_input_contract_without_branch" }) as {
      workflow_id: string;
      branch?: string | null;
      inputs?: Record<string, unknown>;
    };
    expect(omittedBranch).toEqual(
      expect.objectContaining({
        workflow_id: "wf_input_contract_without_branch",
        inputs: {},
      }),
    );
  });

  it("WorkflowResponseSchema preserves identity, list metadata, and input schema metadata", () => {
    const schema = getSchema("WorkflowResponseSchema");

    expect(schema.shape).toEqual(
      expect.objectContaining({
        id: expect.anything(),
        kind: expect.anything(),
        block_count: expect.anything(),
        modified_at: expect.anything(),
        enabled: expect.anything(),
        commit_sha: expect.anything(),
        health: expect.anything(),
        input_schema: expect.anything(),
      }),
    );

    const parsed = schema.parse({
      id: "research-review",
      kind: "workflow",
      name: "Research Review",
      yaml: "blocks: {}",
      valid: true,
      block_count: 3,
      modified_at: 1711900000,
      enabled: true,
      commit_sha: "1234567890abcdef1234567890abcdef12345678",
      health: {
        run_count: 2,
        eval_pass_pct: 95,
        eval_health: "success",
        total_cost_usd: 0.3,
        regression_count: 0,
      },
      input_schema: {
        query: {
          type: "string",
          default: "search",
          description: "Search query",
          sensitive: false,
        },
      },
    }) as {
      block_count?: number;
      input_schema?: Record<string, { type: string; sensitive?: boolean | null }>;
    };

    expect(parsed.block_count).toBe(3);
    expect(parsed.input_schema?.query).toEqual(
      expect.objectContaining({
        type: "string",
        sensitive: false,
      }),
    );
  });

  it("RunResponseSchema preserves workflow input snapshots and sensitive redaction boundaries", () => {
    const schema = getSchema("RunResponseSchema");

    const parsed = schema.parse({
      id: "run_input_contract",
      workflow_id: "wf_input_contract",
      workflow_name: "Input Contract Workflow",
      branch: "main",
      status: "completed",
      started_at: 1711900000,
      completed_at: 1711900010,
      duration_seconds: 10,
      total_cost_usd: 0,
      total_tokens: 0,
      created_at: 1711900011,
      workflow_inputs: {
        query: {
          type: "string",
          sensitive: false,
          source: "provided",
          value: "audit runs",
        },
        api_key: {
          type: "string",
          sensitive: true,
          source: "provided",
        },
      },
      workflow_input_schema: {
        query: {
          type: "string",
          required: true,
          default: null,
          description: "Search query",
          sensitive: false,
        },
      },
    }) as {
      workflow_inputs?: Record<string, { value?: string; redacted?: string; sensitive?: boolean }>;
    };

    expect(parsed.workflow_inputs?.query?.value).toBe("audit runs");
    expect(parsed.workflow_inputs?.api_key).toEqual(
      expect.objectContaining({
        sensitive: true,
        source: "provided",
      }),
    );
    expect(parsed.workflow_inputs?.api_key).not.toHaveProperty("value");
    expect(parsed.workflow_inputs?.api_key).not.toHaveProperty("redacted");
  });

  it("parses structured workflow input validation errors", () => {
    const schema = getSchema("WorkflowInputValidationErrorResponseSchema");

    const parsed = schema.parse({
      error: "Workflow input validation failed",
      error_code: "WORKFLOW_INPUT_VALIDATION_ERROR",
      status_code: 422,
      details: {
        kind: "workflow_input_validation",
        fields: [
          {
            field: "query",
            code: "required",
            message: "Input 'query' is required.",
            input_path: ["inputs", "query"],
            expected_type: "string",
            actual_type: null,
          },
        ],
      },
    }) as {
      error_code: string;
      status_code: number;
      details: { kind: string; fields: Array<{ field: string }> };
    };

    expect(parsed.error_code).toBe("WORKFLOW_INPUT_VALIDATION_ERROR");
    expect(parsed.status_code).toBe(422);
    expect(parsed.details.kind).toBe("workflow_input_validation");
    expect(parsed.details.fields[0]?.field).toBe("query");
    expect(() =>
      schema.parse({
        error: "Workflow input validation failed",
        error_code: "VALIDATION_ERROR",
        status_code: 422,
        details: { kind: "workflow_input_validation", fields: [] },
      }),
    ).toThrow();
  });

  it("generated OpenAPI TS exposes workflow input fields on the run and workflow components", () => {
    const runCreateFields = extractComponentFieldNames(apiSource, "RunCreate");
    const runResponseFields = extractComponentFieldNames(apiSource, "RunResponse");
    const workflowResponseFields = extractComponentFieldNames(apiSource, "WorkflowResponse");

    expect(runCreateFields).toEqual(expect.arrayContaining(["workflow_id", "inputs"]));
    expect(runResponseFields).toEqual(
      expect.arrayContaining(["workflow_inputs", "workflow_input_schema"]),
    );
    expect(workflowResponseFields).toEqual(expect.arrayContaining(["input_schema"]));
  });

  it("generated OpenAPI TS keeps defaulted and nullable RunCreate fields optional for callers", () => {
    const runCreateBlock = extractComponentBlock(apiSource, "RunCreate", "RunEvalResponse");

    expect(runCreateBlock).toMatch(/\binputs\?:/);
    expect(runCreateBlock).toMatch(/\bsource\?:/);
    expect(runCreateBlock).toMatch(/\bbranch\?: string \| null;/);
  });
});
