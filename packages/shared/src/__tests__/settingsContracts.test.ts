import * as sharedZod from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

type ParseableSchema = {
  parse: (input: unknown) => unknown;
  shape: Record<string, unknown>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getCanonicalSchema(name: string): ParseableSchema {
  const schema = (sharedZod as Record<string, unknown>)[name];

  expect(
    isRecord(schema) && typeof schema.parse === "function",
    `Expected ${name} to be exported from @runsight/shared/zod`,
  ).toBe(true);

  return schema as ParseableSchema;
}

describe("canonical settings transport contract smoke", () => {
  it("parses provider, fallback, app-settings, and provider-test responses", () => {
    const providerSample = {
      id: "fixture-primary",
      kind: "provider",
      name: "Fixture Primary",
      type: "fixture-primary",
      status: "connected",
      api_key_env: "FIXTURE_PROVIDER_CREDENTIAL",
      api_key_preview: "test-key...abcd",
      base_url: "http://localhost/v1",
      models: ["fixture-chat-model"],
      model_count: 1,
      is_active: true,
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-02T00:00:00Z",
    };
    const fallbackSample = {
      id: "fixture-primary",
      provider_id: "fixture-primary",
      provider_name: "Fixture Primary",
      fallback_provider_id: "fixture-backup",
      fallback_model_id: "fixture-backup-model",
    };

    expect(
      getCanonicalSchema("SettingsProviderListResponseSchema").parse({
        items: [providerSample],
        total: 1,
      }),
    ).toEqual(
      expect.objectContaining({
        items: [expect.objectContaining({ id: "fixture-primary", kind: "provider" })],
        total: 1,
      }),
    );
    expect(
      getCanonicalSchema("SettingsFallbackListResponseSchema").parse({
        items: [fallbackSample],
        total: 1,
      }),
    ).toEqual(expect.objectContaining({ items: [expect.objectContaining(fallbackSample)] }));
    expect(
      getCanonicalSchema("AppSettingsOutSchema").parse({
        base_path: "/workspace",
        onboarding_completed: true,
        fallback_enabled: false,
      }),
    ).toEqual(expect.objectContaining({ fallback_enabled: false }));
    expect(
      getCanonicalSchema("ProviderTestOutSchema").parse({
        success: true,
        message: "Connection successful",
        models: ["fixture-chat-model"],
        model_count: 1,
        latency_ms: 123.4,
      }),
    ).toEqual(expect.objectContaining({ success: true, model_count: 1 }));
  });

  it("keeps embedded identity request contracts strict for provider and soul YAML", () => {
    const providerCreateSchema = getCanonicalSchema("ProviderCreateSchema");
    const soulCreateSchema = getCanonicalSchema("SoulCreateSchema");

    expect(providerCreateSchema.shape).toEqual(
      expect.objectContaining({
        id: expect.anything(),
        kind: expect.anything(),
        name: expect.anything(),
      }),
    );
    expect(
      providerCreateSchema.parse({
        id: "fixture-provider",
        kind: "provider",
        name: "Fixture Provider",
        api_key_env: "DUMMY_PROVIDER_KEY",
        base_url: "http://localhost/fixture-provider/v1",
      }),
    ).toEqual(expect.objectContaining({ id: "fixture-provider", kind: "provider" }));
    expect(() =>
      providerCreateSchema.parse({
        id: "fixture-provider",
        kind: "provider",
        name: "Fixture Provider",
        custom_notes: "unsupported",
      }),
    ).toThrow();

    expect(
      soulCreateSchema.parse({
        id: "researcher",
        kind: "soul",
        name: "Researcher",
        role: "Research File Writer",
        system_prompt: "Write a research brief.",
      }),
    ).toEqual(expect.objectContaining({ id: "researcher", kind: "soul" }));
    expect(() =>
      soulCreateSchema.parse({
        id: "researcher",
        kind: "soul",
        name: "Researcher",
        role: "Researcher",
        system_prompt: "Research carefully.",
        assertions: [{ type: "contains", value: "hello" }],
      }),
    ).toThrow();
  });

  it("keeps tool and fallback update schemas on canonical field names", () => {
    const toolListItemSchema = getCanonicalSchema("ToolListItemResponseSchema");
    const fallbackUpdateSchema = getCanonicalSchema("FallbackUpdateSchema");

    expect(
      toolListItemSchema.parse({
        id: "report_lookup",
        name: "Report Lookup",
        description: "Look up saved reports.",
        origin: "custom",
        executor: "python",
      }),
    ).toEqual(expect.objectContaining({ id: "report_lookup", origin: "custom" }));
    expect(() =>
      toolListItemSchema.parse({
        slug: "http",
        name: "HTTP Requests",
        description: "Fetch external APIs.",
        type: "builtin",
      }),
    ).toThrow();
    expect(
      fallbackUpdateSchema.parse({
        fallback_provider_id: null,
        fallback_model_id: null,
      }),
    ).toEqual(
      expect.objectContaining({
        fallback_provider_id: null,
        fallback_model_id: null,
      }),
    );
  });

  it("rejects null app-settings update values while allowing omitted fields", () => {
    const appSettingsUpdateSchema = getCanonicalSchema("AppSettingsUpdateSchema");

    expect(appSettingsUpdateSchema.parse({})).toEqual({});
    expect(() =>
      appSettingsUpdateSchema.parse({
        onboarding_completed: null,
      }),
    ).toThrow();
    expect(() =>
      appSettingsUpdateSchema.parse({
        fallback_enabled: null,
      }),
    ).toThrow();
  });
});
