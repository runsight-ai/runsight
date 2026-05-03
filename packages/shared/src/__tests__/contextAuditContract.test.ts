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

describe("context audit shared/client contract smoke", () => {
  it("exports and parses the context audit list response schema", () => {
    const schema = getSchema("ContextAuditListResponseSchema");

    expect(schema.shape).toEqual(
      expect.objectContaining({
        items: expect.anything(),
        page_size: expect.anything(),
        has_next_page: expect.anything(),
        end_cursor: expect.anything(),
      }),
    );

    const parsed = schema.parse({
      items: [
        {
          schema_version: "context_audit.v1",
          event: "context_resolution",
          run_id: "run_context_contract",
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
    }) as { items: unknown[]; page_size: number; has_next_page: boolean };

    expect(parsed.items).toHaveLength(1);
    expect(parsed.page_size).toBe(100);
    expect(parsed.has_next_page).toBe(false);
  });

  it("keeps context access and status values on the declared governance contract", () => {
    const contextAccessSchema = getSchema("ContextAccessSchema");
    const contextAuditStatusSchema = getSchema("ContextAuditStatusSchema");

    expect(contextAccessSchema.parse("declared")).toBe("declared");
    expect(() => contextAccessSchema.parse("all")).toThrow();
    expect(contextAuditStatusSchema.parse("resolved")).toBe("resolved");
    expect(() => contextAuditStatusSchema.parse("all_access")).toThrow();
  });
});
