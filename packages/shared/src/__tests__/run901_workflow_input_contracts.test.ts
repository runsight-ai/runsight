import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as sharedZod from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

const SHARED_SRC = resolve(__dirname, "..");
const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..");
const apiSource = readFileSync(resolve(SHARED_SRC, "api.ts"), "utf8");
const openapi = JSON.parse(readFileSync(resolve(REPO_ROOT, "openapi.json"), "utf8"));

type ParseableSchema = {
  parse: (input: unknown) => unknown;
  shape: Record<string, unknown>;
};

type OpenApiSchema = {
  properties?: Record<string, unknown>;
  anyOf?: unknown[];
  allOf?: unknown[];
  oneOf?: unknown[];
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
  const pattern = new RegExp(`\\/\\*\\* ${componentName} \\*\\/\\s*${componentName}: \\{([\\s\\S]*?)\\n\\s+\\};`);
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

function findSchemaWithProperties(
  schemas: Record<string, OpenApiSchema>,
  requiredProperties: string[],
): [string, OpenApiSchema] | undefined {
  return Object.entries(schemas).find(([, schema]) => {
    const properties = schema.properties ?? {};
    return requiredProperties.every((property) => property in properties);
  });
}

describe("RUN-901 shared workflow input contracts", () => {
  it("RunCreateSchema defaults omitted inputs to an empty object", () => {
    const schema = getSchema("RunCreateSchema");

    const parsed = schema.parse({
      workflow_id: "wf_901",
    }) as { workflow_id: string; inputs?: Record<string, unknown> };

    expect(parsed.workflow_id).toBe("wf_901");
    expect(parsed.inputs).toEqual({});
  });

  it("WorkflowResponseSchema preserves input_schema field metadata", () => {
    const schema = getSchema("WorkflowResponseSchema");

    const parsed = schema.parse({
      kind: "workflow",
      id: "wf_901",
      input_schema: {
        query: {
          type: "string",
          default: "search",
          description: "Search query",
          sensitive: false,
        },
      },
    }) as {
      input_schema?: Record<
        string,
        {
          type: string;
          default: string;
          description: string;
          sensitive: boolean;
        }
      >;
    };

    expect(parsed).toHaveProperty("input_schema");
    expect(parsed.input_schema).toEqual({
      query: {
        type: "string",
        default: "search",
        description: "Search query",
        sensitive: false,
      },
    });
  });

  it("RunResponseSchema preserves workflow input snapshots and sensitive redaction boundaries", () => {
    const schema = getSchema("RunResponseSchema");

    const parsed = schema.parse({
      id: "run_901",
      workflow_id: "wf_901",
      workflow_name: "Workflow 901",
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
        api_key: {
          type: "string",
          required: true,
          default: null,
          description: "Private token",
          sensitive: true,
        },
      },
    }) as {
      workflow_inputs?: Record<
        string,
        {
          type: string;
          sensitive: boolean;
          source: string;
          value?: string;
          redacted?: string;
        }
      >;
      workflow_input_schema?: Record<
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

    expect(parsed.workflow_inputs?.query).toEqual({
      type: "string",
      sensitive: false,
      source: "provided",
      value: "audit runs",
    });
    expect(parsed.workflow_inputs?.api_key).toEqual({
      type: "string",
      sensitive: true,
      source: "provided",
    });
    expect(parsed.workflow_inputs?.api_key).not.toHaveProperty("value");
    expect(parsed.workflow_inputs?.api_key).not.toHaveProperty("redacted");
    expect(parsed.workflow_input_schema).toEqual({
      query: {
        type: "string",
        required: true,
        default: null,
        description: "Search query",
        sensitive: false,
      },
      api_key: {
        type: "string",
        required: true,
        default: null,
        description: "Private token",
        sensitive: true,
      },
    });
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

  it("committed OpenAPI includes a workflow input validation error schema with structured fields", () => {
    const schemas = (openapi.components?.schemas ?? {}) as Record<string, OpenApiSchema>;
    const match = findSchemaWithProperties(schemas, [
      "error",
      "error_code",
      "status_code",
      "details",
    ]);

    expect(match, "Expected a schema with workflow input validation error fields").toBeDefined();
    const [schemaName, schema] = match ?? [];

    expect(schemaName).toBeTruthy();
    expect(schema.properties).toBeDefined();
    expect(schema.properties).toEqual(
      expect.objectContaining({
        error: expect.any(Object),
        error_code: expect.any(Object),
        status_code: expect.any(Object),
        details: expect.any(Object),
      }),
    );
  });
});
