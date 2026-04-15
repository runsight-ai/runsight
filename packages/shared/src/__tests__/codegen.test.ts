/**
 * RUN-134: Type contract codegen — Pydantic → OpenAPI → TypeScript + Zod
 *
 * Red-team tests: these MUST fail until the codegen pipeline is implemented.
 *
 * Tests validate:
 *   1. Generated type files exist and export expected types
 *   2. Generated Zod schemas exist and are valid
 *   3. Generated types structurally match hand-written schemas (contract test)
 *   4. package.json has the generate:types script
 */

import { describe, it, expect, beforeAll } from "vitest";
import { existsSync, readFileSync, mkdtempSync, rmSync } from "fs";
import { join, resolve } from "path";
import { execFileSync } from "child_process";
import { tmpdir } from "os";

const GENERATED_DIR = resolve(__dirname, "..");
const SHARED_ROOT = resolve(__dirname, "..", "..");
const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..");
const PACKAGE_JSON_PATH = resolve(SHARED_ROOT, "package.json");
const ZOD_GENERATOR_SCRIPT = resolve(REPO_ROOT, "tools", "generate-zod-schemas.py");
const COMMITTED_ZOD_PATH = resolve(GENERATED_DIR, "zod.ts");

type SchemaFieldSnapshot = {
  fresh: string[];
  committed: string[];
};

function extractApiComponentFieldNames(source: string, componentName: string): string[] {
  const pattern = new RegExp(
    `${componentName}: \\{([\\s\\S]*?)\\n\\s+\\};`,
  );
  const match = source.match(pattern);
  if (!match) {
    throw new Error(`Could not find ${componentName} component in generated api.ts output`);
  }

  return match[1]
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const fieldMatch = line.match(/^([A-Za-z0-9_]+)\??:/);
      return fieldMatch?.[1] ?? null;
    })
    .filter((field): field is string => field !== null);
}

function extractSchemaFieldNames(source: string, schemaName: string): string[] {
  const pattern = new RegExp(
    `export const ${schemaName}Schema = z\\.object\\(\\{([\\s\\S]*?)\\n\\}\\)(?:\\.strict\\(\\))?;`,
  );
  const match = source.match(pattern);
  if (!match) {
    throw new Error(`Could not find ${schemaName}Schema in generated output`);
  }

  return match[1]
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const fieldMatch = line.match(/^([A-Za-z0-9_]+):\s/);
      if (!fieldMatch) {
        throw new Error(`Could not parse schema field line: ${line}`);
      }
      return fieldMatch[1];
    });
}

function readCommittedOpenApiSnapshot(): Record<string, unknown> {
  return JSON.parse(readFileSync(resolve(REPO_ROOT, "openapi.json"), "utf8"));
}

function buildFreshSchemaSnapshot(): {
  providerCreate: SchemaFieldSnapshot;
  workflowResponse: SchemaFieldSnapshot;
  runCreate: SchemaFieldSnapshot;
  runResponse: SchemaFieldSnapshot;
  soulCreate: SchemaFieldSnapshot;
  soulResponse: SchemaFieldSnapshot;
  soulUpdate: SchemaFieldSnapshot;
  workflowResponse: SchemaFieldSnapshot;
} {
  const workdir = mkdtempSync(join(tmpdir(), "runsight-zod-"));
  const openapiPath = resolve(workdir, "openapi.json");
  const generatedZodPath = resolve(workdir, "zod.ts");
  const openapiPython = [
    "import json",
    "import sys",
    "from pathlib import Path",
    "from runsight_api.main import app",
    'Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2) + "\\n")',
  ].join("\n");

  try {
    execFileSync(
      "uv",
      ["run", "python", "-c", openapiPython, openapiPath],
      {
        cwd: REPO_ROOT,
        stdio: "pipe",
      },
    );

    execFileSync(
      "uv",
      ["run", "python", ZOD_GENERATOR_SCRIPT, openapiPath, generatedZodPath],
      {
        cwd: REPO_ROOT,
        stdio: "pipe",
      },
    );

    const freshZod = readFileSync(generatedZodPath, "utf8");
    const committedZod = readFileSync(COMMITTED_ZOD_PATH, "utf8");

    return {
      providerCreate: {
        fresh: extractSchemaFieldNames(freshZod, "ProviderCreate"),
        committed: extractSchemaFieldNames(committedZod, "ProviderCreate"),
      },
      workflowResponse: {
        fresh: extractSchemaFieldNames(freshZod, "WorkflowResponse"),
        committed: extractSchemaFieldNames(committedZod, "WorkflowResponse"),
      },
      runCreate: {
        fresh: extractSchemaFieldNames(freshZod, "RunCreate"),
        committed: extractSchemaFieldNames(committedZod, "RunCreate"),
      },
      runResponse: {
        fresh: extractSchemaFieldNames(freshZod, "RunResponse"),
        committed: extractSchemaFieldNames(committedZod, "RunResponse"),
      },
      soulCreate: {
        fresh: extractSchemaFieldNames(freshZod, "SoulCreate"),
        committed: extractSchemaFieldNames(committedZod, "SoulCreate"),
      },
      soulResponse: {
        fresh: extractSchemaFieldNames(freshZod, "SoulResponse"),
        committed: extractSchemaFieldNames(committedZod, "SoulResponse"),
      },
      soulUpdate: {
        fresh: extractSchemaFieldNames(freshZod, "SoulUpdate"),
        committed: extractSchemaFieldNames(committedZod, "SoulUpdate"),
      },
    };
  } finally {
    rmSync(workdir, { recursive: true, force: true });
  }
}

// ---------------------------------------------------------------------------
// 1. Generated files exist
// ---------------------------------------------------------------------------

describe("RUN-134: Generated type files exist", () => {
  it("generated directory contains api.ts (OpenAPI types)", () => {
    const filePath = resolve(GENERATED_DIR, "api.ts");
    expect(
      existsSync(filePath),
      `Expected generated file at ${filePath}`,
    ).toBe(true);
  });

  it("generated directory contains zod.ts (Zod schemas)", () => {
    const candidates = ["zod.ts", "schemas.ts", "api.zod.ts"];
    const found = candidates.some((f) =>
      existsSync(resolve(GENERATED_DIR, f)),
    );
    expect(found, "No generated Zod schema file found").toBe(true);
  });

  it("generated directory contains an index.ts barrel export", () => {
    const filePath = resolve(GENERATED_DIR, "index.ts");
    expect(
      existsSync(filePath),
      `Expected barrel export at ${filePath}`,
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 2. Generated types export expected interfaces
// ---------------------------------------------------------------------------

describe("RUN-134: Generated types export expected interfaces", () => {
  const apiSource = readFileSync(resolve(GENERATED_DIR, "api.ts"), "utf8");

  it("declares WorkflowResponse in the generated API component namespace", () => {
    const fields = extractApiComponentFieldNames(apiSource, "WorkflowResponse");
    expect(fields).toEqual(
      expect.arrayContaining(["id", "kind", "name", "yaml", "valid"]),
    );
  });

  it("declares RunResponse in the generated API component namespace", () => {
    const fields = extractApiComponentFieldNames(apiSource, "RunResponse");
    expect(fields).toEqual(
      expect.arrayContaining(["id", "workflow_id", "status", "created_at"]),
    );
  });

  it("declares SoulResponse in the generated API component namespace", () => {
    const fields = extractApiComponentFieldNames(apiSource, "SoulResponse");
    expect(fields).toEqual(
      expect.arrayContaining(["id", "role", "system_prompt", "workflow_count"]),
    );
  });

  it("declares ToolListItemResponse with canonical tool identity fields", () => {
    const fields = extractApiComponentFieldNames(apiSource, "ToolListItemResponse");
    expect(fields).toEqual(
      expect.arrayContaining(["id", "name", "description", "origin", "executor"]),
    );
    expect(fields).not.toContain("slug");
    expect(fields).not.toContain("type");
  });
});

describe("RUN-840: generated workflow warning contracts stay in sync", () => {
  it("generated WorkflowResponse schemas include warnings in fresh and committed output", () => {
    const snapshot = buildFreshSchemaSnapshot();

    expect(snapshot.workflowResponse.fresh).toEqual(
      expect.arrayContaining(["id", "valid", "warnings"]),
    );
    expect(snapshot.workflowResponse.committed).toEqual(
      expect.arrayContaining(["id", "valid", "warnings"]),
    );
  });

  it("committed Zod source exports WarningItemSchema for workflow warnings", () => {
    const zodSource = readFileSync(COMMITTED_ZOD_PATH, "utf8");

    expect(zodSource).toContain("WarningItemSchema");
    expect(zodSource).toContain("WorkflowResponseSchema");
    expect(zodSource).toContain("warnings");
  });
});

describe("RUN-515: generated API wrapper cleanup stays concrete", () => {
  it("generate-types script does not append a runtime components shim to api.ts", () => {
    const scriptSource = readFileSync(resolve(REPO_ROOT, "tools", "generate-types.sh"), "utf8");
    expect(scriptSource).not.toMatch(/export const components\s*=\s*\{\s*\};/);
  });

  it("committed generated api.ts output does not include a runtime components shim", () => {
    const apiSource = readFileSync(resolve(GENERATED_DIR, "api.ts"), "utf8");
    expect(apiSource).not.toMatch(/\bexport const components\s*=\s*\{\s*\};/);
  });
});

// ---------------------------------------------------------------------------
// 3. Generated Zod schemas are valid and parse-able
// ---------------------------------------------------------------------------

describe("RUN-134: Generated Zod schemas are valid", () => {
  it("exports WorkflowResponseSchema as a Zod schema", async () => {
    // This import will fail until zod.ts is generated
    const mod = await import("../zod");
    expect(mod.WorkflowResponseSchema).toBeDefined();
    expect(typeof mod.WorkflowResponseSchema.parse).toBe("function");
  });

  it("exports RunResponseSchema as a Zod schema", async () => {
    const mod = await import("../zod");
    expect(mod.RunResponseSchema).toBeDefined();
    expect(typeof mod.RunResponseSchema.parse).toBe("function");
  });

  it("exports SoulResponseSchema as a Zod schema", async () => {
    const mod = await import("../zod");
    expect(mod.SoulResponseSchema).toBeDefined();
    expect(typeof mod.SoulResponseSchema.parse).toBe("function");
  });

  it("ToolListItemResponseSchema parses canonical tool identity fields", async () => {
    const mod = await import("../zod");
    const result = mod.ToolListItemResponseSchema.safeParse({
      id: "report_lookup",
      name: "Report Lookup",
      description: "Look up saved reports.",
      origin: "custom",
      executor: "python",
    });
    expect(result.success).toBe(true);
  });

  it("ToolListItemResponseSchema rejects the legacy slug/type taxonomy", async () => {
    const mod = await import("../zod");
    const result = mod.ToolListItemResponseSchema.safeParse({
      slug: "http",
      name: "HTTP Requests",
      description: "Fetch external APIs.",
      type: "builtin",
    });
    expect(result.success).toBe(false);
  });

  it("WorkflowResponseSchema parses a valid workflow object", async () => {
    const mod = await import("../zod");
    const result = mod.WorkflowResponseSchema.safeParse({
      id: "test-id",
      kind: "workflow",
      name: "Test Workflow",
      yaml: "steps: []",
      valid: true,
      block_count: 3,
      modified_at: 1711900000.0,
      enabled: true,
      commit_sha: "deadbeefcafebabe",
      health: {
        run_count: 2,
        eval_pass_pct: 95.0,
        eval_health: "success",
        total_cost_usd: 0.3,
        regression_count: 0,
      },
    });
    expect(result.success).toBe(true);
  });

  it("WorkflowResponseSchema exposes RUN-478 workflow health fields", async () => {
    const mod = await import("../zod");
    const shape = mod.WorkflowResponseSchema.shape;

    expect(shape).toHaveProperty("block_count");
    expect(shape).toHaveProperty("modified_at");
    expect(shape).toHaveProperty("enabled");
    expect(shape).toHaveProperty("commit_sha");
    expect(shape).toHaveProperty("health");
  });

  it("RunResponseSchema parses a valid run object", async () => {
    const mod = await import("../zod");
    const result = mod.RunResponseSchema.safeParse({
      id: "run-1",
      workflow_id: "wf-1",
      workflow_name: "Test",
      status: "completed",
      started_at: 1000,
      completed_at: 2000,
      duration_seconds: 1,
      total_cost_usd: 0.01,
      total_tokens: 100,
      created_at: 1000,
    });
    expect(result.success).toBe(true);
  });
});

describe("RUN-409: generated Zod schemas stay fresh against live OpenAPI", () => {
  let snapshot: {
    providerCreate: SchemaFieldSnapshot;
    workflowResponse: SchemaFieldSnapshot;
    runCreate: SchemaFieldSnapshot;
    runResponse: SchemaFieldSnapshot;
    soulCreate: SchemaFieldSnapshot;
    soulResponse: SchemaFieldSnapshot;
    soulUpdate: SchemaFieldSnapshot;
  };

  beforeAll(() => {
    snapshot = buildFreshSchemaSnapshot();
  });

  it("RunCreateSchema includes source in the generated output", () => {
    expect(snapshot.runCreate.fresh).toContain("source");
    expect(snapshot.runCreate.committed).toEqual(snapshot.runCreate.fresh);
  });

  it("WorkflowResponseSchema includes embedded workflow identity", () => {
    expect(snapshot.workflowResponse.fresh).toEqual(
      expect.arrayContaining(["id", "kind", "name"]),
    );
    expect(snapshot.workflowResponse.committed).toEqual(snapshot.workflowResponse.fresh);
  });

  it("ProviderCreateSchema includes embedded provider identity", () => {
    expect(snapshot.providerCreate.fresh).toEqual(
      expect.arrayContaining(["id", "kind", "name"]),
    );
    expect(snapshot.providerCreate.fresh).not.toContain("type");
    expect(snapshot.providerCreate.committed).toEqual(snapshot.providerCreate.fresh);
  });

  it("RunResponseSchema includes branch, source, commit_sha, and RUN-479 run metrics", () => {
    expect(snapshot.runResponse.fresh).toEqual(
      expect.arrayContaining([
        "branch",
        "source",
        "commit_sha",
        "run_number",
        "eval_pass_pct",
      ]),
    );
    expect(snapshot.runResponse.committed).toEqual(snapshot.runResponse.fresh);
  });

  it("SoulCreateSchema includes embedded soul identity plus role and model_name", () => {
    expect(snapshot.soulCreate.fresh).toEqual(
      expect.arrayContaining(["id", "kind", "name", "role", "system_prompt", "model_name"]),
    );
    expect(snapshot.soulCreate.fresh).not.toContain("models");
    expect(snapshot.soulCreate.committed).toEqual(snapshot.soulCreate.fresh);
  });

  it("SoulCreateSchema includes provider, temperature, and max_tokens but not assertions", () => {
    expect(snapshot.soulCreate.fresh).toEqual(
      expect.arrayContaining(["provider", "temperature", "max_tokens", "avatar_color"]),
    );
    expect(snapshot.soulCreate.fresh).not.toContain("assertions");
    expect(snapshot.soulCreate.committed).toEqual(snapshot.soulCreate.fresh);
  });

  it("SoulResponseSchema includes embedded soul identity, role, model_name, and workflow_count", () => {
    expect(snapshot.soulResponse.fresh).toEqual(
      expect.arrayContaining([
        "id",
        "kind",
        "name",
        "role",
        "system_prompt",
        "model_name",
        "workflow_count",
      ]),
    );
    expect(snapshot.soulResponse.fresh).not.toContain("models");
    expect(snapshot.soulResponse.committed).toEqual(snapshot.soulResponse.fresh);
  });

  it("SoulResponseSchema includes provider, temperature, and max_tokens but not assertions", () => {
    expect(snapshot.soulResponse.fresh).toEqual(
      expect.arrayContaining(["provider", "temperature", "max_tokens", "avatar_color"]),
    );
    expect(snapshot.soulResponse.fresh).not.toContain("assertions");
    expect(snapshot.soulResponse.committed).toEqual(snapshot.soulResponse.fresh);
  });

  it("SoulUpdateSchema includes provider, temperature, and max_tokens but not assertions", () => {
    expect(snapshot.soulUpdate.fresh).toEqual(
      expect.arrayContaining(["provider", "temperature", "max_tokens", "copy_on_edit"]),
    );
    expect(snapshot.soulUpdate.fresh).not.toContain("assertions");
    expect(snapshot.soulUpdate.committed).toEqual(snapshot.soulUpdate.fresh);
  });
});

describe("RUN-477: generated API types stay aligned for soul contracts", () => {
  const apiSource = readFileSync(resolve(GENERATED_DIR, "api.ts"), "utf8");

  it("ProviderCreate component includes embedded provider identity", () => {
    const fields = extractApiComponentFieldNames(apiSource, "ProviderCreate");
    expect(fields).toEqual(expect.arrayContaining(["id", "kind", "name"]));
  });

  it("SoulCreate component includes provider, temperature, and max_tokens but not assertions", () => {
    const fields = extractApiComponentFieldNames(apiSource, "SoulCreate");
    expect(fields).toEqual(
      expect.arrayContaining([
        "id",
        "kind",
        "name",
        "role",
        "system_prompt",
        "provider",
        "temperature",
        "max_tokens",
        "avatar_color",
      ]),
    );
    expect(fields).not.toContain("assertions");
  });

  it("SoulResponse component includes provider, temperature, and max_tokens but not assertions", () => {
    const fields = extractApiComponentFieldNames(apiSource, "SoulResponse");
    expect(fields).toEqual(
      expect.arrayContaining([
        "id",
        "kind",
        "name",
        "role",
        "system_prompt",
        "provider",
        "temperature",
        "max_tokens",
        "avatar_color",
        "workflow_count",
      ]),
    );
    expect(fields).not.toContain("assertions");
  });

  it("SoulUpdate component includes provider, temperature, and max_tokens but not assertions", () => {
    const fields = extractApiComponentFieldNames(apiSource, "SoulUpdate");
    expect(fields).toEqual(
      expect.arrayContaining(["provider", "temperature", "max_tokens", "avatar_color", "copy_on_edit"]),
    );
    expect(fields).not.toContain("assertions");
  });
});

describe("RUN-823: custom YAML request schemas are strict", () => {
  const openapi = JSON.parse(readFileSync(resolve(REPO_ROOT, "openapi.json"), "utf8"));

  it.each([
    "SoulCreate",
    "SoulUpdate",
    "TaskCreate",
    "TaskUpdate",
    "StepCreate",
    "StepUpdate",
    "ProviderCreate",
    "ProviderUpdate",
  ])("%s OpenAPI schema forbids unknown fields", (schemaName) => {
    const schema = openapi.components?.schemas?.[schemaName];
    expect(schema).toBeDefined();
    expect(schema.additionalProperties).toBe(false);
  });

  it("generated request Zod schemas reject unknown fields", async () => {
    const mod = await import("../zod");

    expect(
      mod.SoulCreateSchema.safeParse({
        role: "Reviewer",
        system_prompt: "Review",
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
    expect(
      mod.SoulUpdateSchema.safeParse({
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
    expect(
      mod.TaskCreateSchema.safeParse({
        name: "Task",
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
    expect(
      mod.TaskUpdateSchema.safeParse({
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
    expect(
      mod.StepCreateSchema.safeParse({
        name: "Step",
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
    expect(
      mod.StepUpdateSchema.safeParse({
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
    expect(
      mod.ProviderCreateSchema.safeParse({
        name: "OpenAI",
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
    expect(
      mod.ProviderUpdateSchema.safeParse({
        custom_notes: "unsupported",
      }).success,
    ).toBe(false);
  });

  it("generated Zod strictness uses the public Zod API", () => {
    const source = readFileSync(COMMITTED_ZOD_PATH, "utf8");

    expect(source).not.toContain("_def.unknownKeys");
    expect(source).toContain("ProviderCreateSchema = z.object");
    expect(source).toContain("}).strict();");
  });
});

describe("RUN-842: generated API types stay aligned for run warnings", () => {
  const apiSource = readFileSync(resolve(GENERATED_DIR, "api.ts"), "utf8");

  it("declares WorkflowResponse warnings in the generated API component namespace", () => {
    const fields = extractApiComponentFieldNames(apiSource, "WorkflowResponse");
    expect(fields).toEqual(
      expect.arrayContaining(["id", "valid", "warnings"]),
    );
    expect(fields).not.toContain("code");
  });

  it("declares RunResponse warnings in the generated API component namespace", () => {
    const fields = extractApiComponentFieldNames(apiSource, "RunResponse");
    expect(fields).toEqual(
      expect.arrayContaining(["id", "workflow_id", "status", "warnings"]),
    );
  });

  it("declares WarningItem with the canonical workflow warning fields", () => {
    const fields = extractApiComponentFieldNames(apiSource, "WarningItem");
    expect(fields).toEqual(
      expect.arrayContaining(["message", "source", "context"]),
    );
    expect(fields).toHaveLength(3);
  });

  it("pins the committed openapi.json run warning contract", () => {
    const snapshot = readCommittedOpenApiSnapshot();
    const schemas = snapshot.components as Record<string, unknown> | undefined;
    const schemaMap = (schemas?.schemas ?? {}) as Record<string, Record<string, unknown>>;

    const warningItem = schemaMap.WarningItem;
    expect(warningItem).toBeDefined();
    expect(Object.keys((warningItem?.properties ?? {}) as Record<string, unknown>).sort()).toEqual([
      "context",
      "message",
      "source",
    ]);

    const workflowResponse = schemaMap.WorkflowResponse;
    expect(workflowResponse).toBeDefined();
    const workflowWarnings = (workflowResponse?.properties ?? {}) as Record<string, unknown>;
    expect(workflowWarnings).toHaveProperty("warnings");
    const warningsProperty = workflowWarnings.warnings as Record<string, unknown>;
    expect(warningsProperty?.items).toMatchObject({
      $ref: "#/components/schemas/WarningItem",
    });

    const runResponse = schemaMap.RunResponse;
    expect(runResponse).toBeDefined();
    const runProperties = (runResponse?.properties ?? {}) as Record<string, unknown>;
    const runWarnings = runProperties.warnings as Record<string, unknown> | undefined;
    expect(runWarnings).toBeDefined();
    expect(runWarnings?.items).toMatchObject({
      $ref: "#/components/schemas/WarningItem",
    });
  });

  it("keeps a single canonical WarningItem component (no duplicate warning schemas)", () => {
    const snapshot = readCommittedOpenApiSnapshot();
    const schemas = snapshot.components as Record<string, unknown> | undefined;
    const schemaMap = (schemas?.schemas ?? {}) as Record<string, Record<string, unknown>>;

    const warningLikeNames = Object.keys(schemaMap)
      .filter((name) => name.toLowerCase().includes("warningitem"))
      .sort();
    expect(warningLikeNames).toEqual(["WarningItem"]);

    const runResponse = schemaMap.RunResponse;
    const runProperties = (runResponse?.properties ?? {}) as Record<string, unknown>;
    const runWarnings = runProperties.warnings as Record<string, unknown> | undefined;
    expect(runWarnings?.items).toMatchObject({
      $ref: "#/components/schemas/WarningItem",
    });
  });
});

// ---------------------------------------------------------------------------
// 4. package.json has codegen scripts
// ---------------------------------------------------------------------------

describe("RUN-134: package.json codegen configuration", () => {
  it("has a 'generate:types' script", () => {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf-8"));
    expect(pkg.scripts).toHaveProperty("generate:types");
  });

  it("has openapi-typescript in devDependencies", () => {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf-8"));
    expect(pkg.devDependencies).toHaveProperty("openapi-typescript");
  });

  it("has a 'check:types-fresh' or equivalent CI script", () => {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf-8"));
    const scripts = Object.keys(pkg.scripts || {});
    const hasCheck = scripts.some(
      (s) => s.includes("check:types") || s.includes("codegen:check"),
    );
    expect(
      hasCheck,
      `No type freshness check script found. Scripts: ${scripts.join(", ")}`,
    ).toBe(true);
  });
});
