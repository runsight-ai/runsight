import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as sharedZod from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

const SHARED_SRC = resolve(__dirname, "..");
const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..");
const apiSource = readFileSync(resolve(SHARED_SRC, "api.ts"), "utf8");
const docsSource = readFileSync(
  resolve(
    REPO_ROOT,
    "apps",
    "site",
    "src",
    "content",
    "docs",
    "docs",
    "workflows",
    "context-governance.mdx",
  ),
  "utf8",
);
const openapi = JSON.parse(readFileSync(resolve(REPO_ROOT, "openapi.json"), "utf8"));
const runsApiSource = readFileSync(
  resolve(REPO_ROOT, "apps", "gui", "src", "api", "runs.ts"),
  "utf8",
);

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

describe("RUN-914 context audit shared/client contract", () => {
  it("generated OpenAPI types include the historical context audit path", () => {
    expect(apiSource).toContain("/api/runs/{run_id}/context-audit");
    expect(apiSource).toContain("ContextAuditListResponse");
  });

  it("generated API contracts exclude frontend static and SPA fallback routes", () => {
    expect(openapi.paths).not.toHaveProperty("/runsight.svg");
    expect(openapi.paths).not.toHaveProperty("/{full_path}");
    expect(apiSource).not.toContain('"/runsight.svg"');
    expect(apiSource).not.toContain('"/{full_path}"');
  });

  it("generated Zod exports ContextAuditListResponseSchema", () => {
    const schema = getSchema("ContextAuditListResponseSchema");

    expect(Object.keys(schema.shape).sort()).toEqual([
      "end_cursor",
      "has_next_page",
      "items",
      "page_size",
    ]);

    const parsed = schema.parse({
      items: [
        {
          schema_version: "context_audit.v1",
          event: "context_resolution",
          run_id: "run_914",
          workflow_name: "wf",
          node_id: "summarize",
          block_type: "linear",
          access: "declared",
          mode: "strict",
          sequence: 1,
          records: [],
          resolved_count: 0,
          denied_count: 0,
          warning_count: 0,
          emitted_at: new Date().toISOString(),
        },
      ],
      page_size: 100,
      has_next_page: false,
      end_cursor: null,
    });

    expect(parsed).toMatchObject({
      page_size: 100,
      has_next_page: false,
      end_cursor: null,
    });
  });

  it("runsApi exposes getRunContextAudit using generated schema and query params", () => {
    expect(runsApiSource).toContain("ContextAuditListResponseSchema");
    expect(runsApiSource).toContain("getRunContextAudit");
    expect(runsApiSource).toContain("/runs/${id}/context-audit");
    expect(runsApiSource).toMatch(/node_id/);
    expect(runsApiSource).toMatch(/cursor/);
    expect(runsApiSource).toMatch(/page_size/);

    const methodMatch = runsApiSource.match(
      /getRunContextAudit[\s\S]*?(?=\n {2}\w|\n\};)/,
    );
    expect(methodMatch).not.toBeNull();
    expect(methodMatch?.[0]).toContain("ContextAuditListResponseSchema.parse");
  });

  it("generated contracts and docs do not expose all-access governance", () => {
    const contextAccessSchema = getSchema("ContextAccessSchema");
    const contextAuditStatusSchema = getSchema("ContextAuditStatusSchema");

    expect(contextAccessSchema.parse("declared")).toBe("declared");
    expect(() => contextAccessSchema.parse("all")).toThrow();
    expect(contextAuditStatusSchema.parse("resolved")).toBe("resolved");
    expect(() => contextAuditStatusSchema.parse("all_access")).toThrow();
    expect(apiSource).not.toContain("all_access");
    expect(apiSource).not.toContain('access: all');
    expect(docsSource).not.toContain("access: all");
    expect(docsSource).not.toContain("all_access");
  });
});
