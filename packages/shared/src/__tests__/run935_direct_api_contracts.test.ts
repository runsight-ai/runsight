import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as sharedZod from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

const SHARED_SRC = resolve(__dirname, "..");
const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..");
const DIRECT_API_PATH = "/api/workflows/{workflow_id}/runs";
const FORBIDDEN_EXTERNAL_FIELDS = [
  "source",
  "branch",
  "commit_sha",
  "debug",
  "simulation",
  "simulation_id",
  "simulation_branch",
  "trigger_id",
  "delivery_id",
  "idempotency_key",
  "idempotency_token",
  "caller",
  "source_correlation_id",
  "source_metadata",
  "provenance",
];

const apiSource = readFileSync(resolve(SHARED_SRC, "api.ts"), "utf8");
const openapi = JSON.parse(readFileSync(resolve(REPO_ROOT, "openapi.json"), "utf8")) as {
  paths?: Record<string, unknown>;
  components?: { schemas?: Record<string, Record<string, unknown>> };
};

type ParseableSchema = {
  parse: (input: unknown) => unknown;
  safeParse: (input: unknown) => { success: boolean };
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
  const pattern = new RegExp(
    `\\/\\*\\* ${componentName} \\*\\/\\s*${componentName}: \\{([\\s\\S]*?)\\n\\s+\\};`,
  );
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

function extractPathBlock(source: string, path: string): string {
  const startMarker = `    "${path}": {`;
  const start = source.indexOf(startMarker);
  expect(start, `Expected generated api.ts paths to include ${path}`).toBeGreaterThanOrEqual(
    0,
  );

  const nextPath = source.indexOf('\n    "', start + startMarker.length);
  const end = nextPath === -1 ? source.indexOf("\nexport type", start) : nextPath;
  return source.slice(start, end);
}

function extractOperationBlock(source: string, operationName: string): string {
  const pattern = new RegExp(
    `\\n\\s{4}${operationName}: \\{[\\s\\S]*?(?=\\n\\s{4}[A-Za-z0-9_]+: \\{|\\n\\};)`,
  );
  const match = source.match(pattern);

  expect(match, `Expected generated api.ts operations to include ${operationName}`).not.toBeNull();

  return match?.[0] ?? "";
}

function assertOnlyInputs(fields: string[]): void {
  expect(fields.sort()).toEqual(["inputs"]);
  for (const field of FORBIDDEN_EXTERNAL_FIELDS) {
    expect(fields).not.toContain(field);
  }
}

function assertSourceEnumIfModeled(sourceProperty: unknown): void {
  const enumValues = (sourceProperty as { enum?: unknown[] } | undefined)?.enum;
  if (Array.isArray(enumValues)) {
    expect(enumValues).toEqual(expect.arrayContaining(["manual", "simulation", "api"]));
  }
}

describe("RUN-935 generated Direct API shared contracts", () => {
  it("committed OpenAPI snapshot includes the workflow-scoped Direct API route", () => {
    const operation = openapi.paths?.[DIRECT_API_PATH] as {
      post?: {
        requestBody?: { content?: { "application/json"?: { schema?: { $ref?: string } } } };
        responses?: Record<string, unknown>;
      };
    } | undefined;

    expect(
      operation?.post,
      `Expected committed openapi.json to include POST ${DIRECT_API_PATH}`,
    ).toBeDefined();

    const schemaRef = operation?.post?.requestBody?.content?.["application/json"]?.schema?.$ref;
    expect(schemaRef).toBe("#/components/schemas/DirectApiRunCreate");
    expect(operation?.post?.responses).toHaveProperty("200");
    expect(operation?.post?.responses).toHaveProperty("422");
    expect(operation?.post?.responses).toHaveProperty("429");
    expect(operation?.post?.responses).toHaveProperty("503");
  });

  it("committed OpenAPI snapshot keeps the external Direct API body to inputs only", () => {
    const schema = openapi.components?.schemas?.DirectApiRunCreate;
    expect(schema, "Expected committed openapi.json to include DirectApiRunCreate").toBeDefined();

    const properties = (schema?.properties ?? {}) as Record<string, unknown>;
    assertOnlyInputs(Object.keys(properties));
    expect(schema?.additionalProperties).toBe(false);
  });

  it("generated api.ts exposes the Direct API path with a distinct request component", () => {
    const pathBlock = extractPathBlock(apiSource, DIRECT_API_PATH);
    const operationName = pathBlock.match(/post: operations\["([^"]+)"\]/)?.[1];
    expect(
      operationName,
      `Expected generated path ${DIRECT_API_PATH} to expose a post operation`,
    ).toBeDefined();

    const operationBlock = extractOperationBlock(apiSource, operationName ?? "");
    expect(operationBlock).toContain(
      '"application/json": components["schemas"]["DirectApiRunCreate"]',
    );
    expect(operationBlock).toContain('"application/json": components["schemas"]["RunResponse"]');
    expect(operationBlock).not.toContain('"application/json": components["schemas"]["RunCreate"]');
  });

  it("generated api.ts declares DirectApiRunCreate as inputs only and keeps RunCreate distinct", () => {
    const directApiFields = extractComponentFieldNames(apiSource, "DirectApiRunCreate");
    const manualRunFields = extractComponentFieldNames(apiSource, "RunCreate");

    assertOnlyInputs(directApiFields);
    expect(manualRunFields).toEqual(
      expect.arrayContaining(["workflow_id", "inputs", "source", "branch"]),
    );
  });

  it("generated Zod exports validate the external Direct API DTO as inputs only", () => {
    const schema = getSchema("DirectApiRunCreateSchema");

    expect(Object.keys(schema.shape).sort()).toEqual(["inputs"]);
    expect(schema.parse({ inputs: { query: "from api" } })).toEqual({
      inputs: { query: "from api" },
    });

    for (const field of FORBIDDEN_EXTERNAL_FIELDS) {
      expect(
        schema.safeParse({ inputs: { query: "from api" }, [field]: "caller-owned" }).success,
        `DirectApiRunCreateSchema must reject caller-owned field ${field}`,
      ).toBe(false);
    }
  });

  it("generated RunResponse contracts expose sanitized provenance fields", () => {
    const apiFields = extractComponentFieldNames(apiSource, "RunResponse");
    const schema = getSchema("RunResponseSchema");
    const openapiRunResponse = openapi.components?.schemas?.RunResponse;
    const openapiProperties = (openapiRunResponse?.properties ?? {}) as Record<string, unknown>;
    const provenanceFields = [
      "source",
      "commit_sha",
      "source_correlation_id",
      "source_metadata",
    ];

    expect(apiFields).toEqual(expect.arrayContaining(provenanceFields));
    expect(Object.keys(schema.shape)).toEqual(expect.arrayContaining(provenanceFields));
    expect(Object.keys(openapiProperties)).toEqual(expect.arrayContaining(provenanceFields));
    assertSourceEnumIfModeled(openapiProperties.source);

    const parsed = schema.parse({
      id: "run_935",
      workflow_id: "wf_935",
      workflow_name: "Direct API contract",
      status: "pending",
      started_at: null,
      completed_at: null,
      duration_seconds: null,
      total_cost_usd: 0,
      total_tokens: 0,
      created_at: 1711900935,
      branch: "main",
      source: "api",
      commit_sha: "9359359359359359359359359359359359359359",
      source_correlation_id: "request-run-935",
      source_metadata: { entry_path: "direct_api" },
    }) as {
      source: string;
      commit_sha?: string | null;
      source_correlation_id?: string | null;
      source_metadata?: Record<string, unknown>;
    };

    expect(parsed.source).toBe("api");
    expect(parsed.commit_sha).toBe("9359359359359359359359359359359359359359");
    expect(parsed.source_correlation_id).toBe("request-run-935");
    expect(parsed.source_metadata).toEqual({ entry_path: "direct_api" });
  });

  it("does not recreate generated GUI contracts under the product app", () => {
    expect(existsSync(resolve(REPO_ROOT, "apps", "gui", "src", "types", "generated"))).toBe(false);
  });
});
