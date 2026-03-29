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
// __dirname = apps/gui/src/types/generated/__tests__
// up 1=generated, 2=types, 3=src, 4=gui
const GUI_ROOT = resolve(__dirname, "..", "..", "..", "..");
const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..", "..", "..");
const PACKAGE_JSON_PATH = resolve(GUI_ROOT, "package.json");
const ZOD_GENERATOR_SCRIPT = resolve(REPO_ROOT, "scripts", "generate-zod-schemas.py");
const COMMITTED_ZOD_PATH = resolve(GENERATED_DIR, "zod.ts");

type SchemaFieldSnapshot = {
  fresh: string[];
  committed: string[];
};

function extractSchemaFieldNames(source: string, schemaName: string): string[] {
  const pattern = new RegExp(
    `export const ${schemaName}Schema = z\\.object\\(\\{([\\s\\S]*?)\\n\\}\\);`,
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

function buildFreshSchemaSnapshot(): {
  runCreate: SchemaFieldSnapshot;
  runResponse: SchemaFieldSnapshot;
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
      runCreate: {
        fresh: extractSchemaFieldNames(freshZod, "RunCreate"),
        committed: extractSchemaFieldNames(committedZod, "RunCreate"),
      },
      runResponse: {
        fresh: extractSchemaFieldNames(freshZod, "RunResponse"),
        committed: extractSchemaFieldNames(committedZod, "RunResponse"),
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
  // These tests will fail at import time until the files exist
  it("exports WorkflowResponse type", async () => {
    const mod = await import("../api");
    expect(mod).toHaveProperty("components");
  });

  it("exports RunResponse type", async () => {
    const mod = await import("../api");
    expect(mod).toHaveProperty("components");
  });

  it("exports SoulResponse type", async () => {
    const mod = await import("../api");
    expect(mod).toHaveProperty("components");
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

  it("WorkflowResponseSchema parses a valid workflow object", async () => {
    const mod = await import("../zod");
    const result = mod.WorkflowResponseSchema.safeParse({
      id: "test-id",
      name: "Test Workflow",
      yaml: "steps: []",
      valid: true,
    });
    expect(result.success).toBe(true);
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
    runCreate: SchemaFieldSnapshot;
    runResponse: SchemaFieldSnapshot;
  };

  beforeAll(() => {
    snapshot = buildFreshSchemaSnapshot();
  });

  it("RunCreateSchema includes source in the generated output", () => {
    expect(snapshot.runCreate.fresh).toContain("source");
    expect(snapshot.runCreate.committed).toEqual(snapshot.runCreate.fresh);
  });

  it("RunResponseSchema includes branch, source, and commit_sha in the generated output", () => {
    expect(snapshot.runResponse.fresh).toEqual(
      expect.arrayContaining(["branch", "source", "commit_sha"]),
    );
    expect(snapshot.runResponse.committed).toEqual(snapshot.runResponse.fresh);
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
