import { readFileSync } from "node:fs";
import * as sharedZod from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

type ParseableSchema = {
  parse: (input: unknown) => unknown;
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

const OPENAPI_DOCUMENT = JSON.parse(
  readFileSync(new URL("../../../../openapi.json", import.meta.url), "utf8"),
) as {
  components?: {
    schemas?: Record<string, { properties?: Record<string, unknown> }>;
  };
};
const GENERATED_API_SOURCE = readFileSync(new URL("../api.ts", import.meta.url), "utf8");
const GENERATED_ZOD_SOURCE = readFileSync(new URL("../zod.ts", import.meta.url), "utf8");

function getSchemaProperties(name: string) {
  return OPENAPI_DOCUMENT.components?.schemas?.[name]?.properties ?? {};
}

describe("RUN-512 canonical settings transport contracts", () => {
  it("exports canonical provider item and list schemas on @runsight/shared/zod", () => {
    const providerSample = {
      id: "openai",
      name: "OpenAI",
      type: "openai",
      status: "connected",
      api_key_env: "OPENAI_API_KEY",
      api_key_preview: "sk-proj...abcd",
      base_url: "https://api.openai.com/v1",
      models: ["gpt-4.1"],
      model_count: 1,
      is_configured: true,
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-02T00:00:00Z",
    };

    const providerItemSchema = getCanonicalSchema("SettingsProviderResponseSchema");
    const providerListSchema = getCanonicalSchema("SettingsProviderListResponseSchema");

    expect(providerItemSchema.parse(providerSample)).toEqual(
      expect.objectContaining({
        api_key_preview: providerSample.api_key_preview,
        created_at: providerSample.created_at,
        updated_at: providerSample.updated_at,
      }),
    );
    expect(providerListSchema.parse({ items: [providerSample], total: 1 })).toEqual(
      expect.objectContaining({
        items: [
          expect.objectContaining({
            api_key_preview: providerSample.api_key_preview,
            created_at: providerSample.created_at,
            updated_at: providerSample.updated_at,
          }),
        ],
        total: 1,
      }),
    );
  });

  it("exports canonical model-default item and list schemas on @runsight/shared/zod", () => {
    const modelDefaultSample = {
      id: "openai",
      provider_id: "openai",
      provider_name: "OpenAI",
      model_name: "gpt-4.1",
      is_default: true,
      fallback_provider_id: "anthropic",
      fallback_model_id: "claude-sonnet-4",
    };

    const modelDefaultItemSchema = getCanonicalSchema("SettingsModelDefaultResponseSchema");
    const modelDefaultListSchema = getCanonicalSchema("SettingsModelDefaultListResponseSchema");

    expect(modelDefaultItemSchema.parse(modelDefaultSample)).toEqual(
      expect.objectContaining({
        provider_id: modelDefaultSample.provider_id,
        provider_name: modelDefaultSample.provider_name,
        fallback_provider_id: modelDefaultSample.fallback_provider_id,
        fallback_model_id: modelDefaultSample.fallback_model_id,
      }),
    );
    expect(modelDefaultListSchema.parse({ items: [modelDefaultSample], total: 1 })).toEqual(
      expect.objectContaining({
        items: [
          expect.objectContaining({
            provider_id: modelDefaultSample.provider_id,
            provider_name: modelDefaultSample.provider_name,
            fallback_provider_id: modelDefaultSample.fallback_provider_id,
            fallback_model_id: modelDefaultSample.fallback_model_id,
          }),
        ],
        total: 1,
      }),
    );
  });

  it("parses renamed fallback fields as strings, nulls, or omitted in canonical zod schemas", () => {
    const modelDefaultSchema = getCanonicalSchema("SettingsModelDefaultResponseSchema");
    const modelDefaultUpdateSchema = getCanonicalSchema("ModelDefaultUpdateSchema");

    expect(
      modelDefaultSchema.parse({
        id: "openai",
        provider_id: "openai",
        provider_name: "OpenAI",
        model_name: "gpt-4.1",
        is_default: true,
        fallback_provider_id: "anthropic",
        fallback_model_id: "claude-sonnet-4",
      }),
    ).toEqual(
      expect.objectContaining({
        fallback_provider_id: "anthropic",
        fallback_model_id: "claude-sonnet-4",
      }),
    );
    expect(
      modelDefaultSchema.parse({
        id: "openai",
        provider_id: "openai",
        provider_name: "OpenAI",
        model_name: "gpt-4.1",
        is_default: true,
        fallback_provider_id: null,
        fallback_model_id: null,
      }),
    ).toEqual(
      expect.objectContaining({
        fallback_provider_id: null,
        fallback_model_id: null,
      }),
    );
    expect(
      modelDefaultSchema.parse({
        id: "openai",
        provider_id: "openai",
        provider_name: "OpenAI",
        model_name: "gpt-4.1",
        is_default: true,
      }),
    ).toEqual(
      expect.objectContaining({
        id: "openai",
        provider_id: "openai",
      }),
    );

    expect(
      modelDefaultUpdateSchema.parse({
        fallback_provider_id: "anthropic",
        fallback_model_id: "claude-sonnet-4",
      }),
    ).toEqual(
      expect.objectContaining({
        fallback_provider_id: "anthropic",
        fallback_model_id: "claude-sonnet-4",
      }),
    );
    expect(
      modelDefaultUpdateSchema.parse({
        fallback_provider_id: null,
        fallback_model_id: null,
      }),
    ).toEqual(
      expect.objectContaining({
        fallback_provider_id: null,
        fallback_model_id: null,
      }),
    );
    expect(modelDefaultUpdateSchema.parse({ model_name: "gpt-4.1" })).toEqual(
      expect.objectContaining({
        model_name: "gpt-4.1",
      }),
    );
  });

  it("exports canonical budget item and list schemas on @runsight/shared/zod", () => {
    const budgetSample = {
      id: "team",
      name: "Team Budget",
      limit_usd: 100,
      spent_usd: 42.5,
      period: "monthly",
      reset_at: "2026-04-30T00:00:00Z",
    };

    const budgetItemSchema = getCanonicalSchema("SettingsBudgetResponseSchema");
    const budgetListSchema = getCanonicalSchema("SettingsBudgetListResponseSchema");

    expect(budgetItemSchema.parse(budgetSample)).toEqual(
      expect.objectContaining({
        spent_usd: budgetSample.spent_usd,
        reset_at: budgetSample.reset_at,
      }),
    );
    expect(budgetListSchema.parse({ items: [budgetSample], total: 1 })).toEqual(
      expect.objectContaining({
        items: [
          expect.objectContaining({
            spent_usd: budgetSample.spent_usd,
            reset_at: budgetSample.reset_at,
          }),
        ],
        total: 1,
      }),
    );
  });

  it("exports the canonical app-settings schema on @runsight/shared/zod", () => {
    const appSettingsSample = {
      base_path: "/workspace",
      default_provider: "openai",
      auto_save: true,
      onboarding_completed: true,
      fallback_enabled: false,
    };

    const appSettingsSchema = getCanonicalSchema("AppSettingsOutSchema");

    expect(appSettingsSchema.parse(appSettingsSample)).toEqual(
      expect.objectContaining(appSettingsSample),
    );
  });

  it("keeps generated OpenAPI and shared contract artifacts on the renamed fallback fields only", () => {
    const settingsModelDefaultProps = getSchemaProperties("SettingsModelDefaultResponse");
    const modelDefaultUpdateProps = getSchemaProperties("ModelDefaultUpdate");
    const appSettingsProps = getSchemaProperties("AppSettingsOut");

    expect(settingsModelDefaultProps).toHaveProperty("fallback_provider_id");
    expect(settingsModelDefaultProps).toHaveProperty("fallback_model_id");
    expect(settingsModelDefaultProps).not.toHaveProperty("fallback_chain");

    expect(modelDefaultUpdateProps).toHaveProperty("fallback_provider_id");
    expect(modelDefaultUpdateProps).toHaveProperty("fallback_model_id");
    expect(modelDefaultUpdateProps).not.toHaveProperty("fallback_chain");

    expect(appSettingsProps).toHaveProperty("fallback_enabled");
    expect(appSettingsProps).not.toHaveProperty("fallback_chain_enabled");

    expect(GENERATED_API_SOURCE).toContain("fallback_provider_id");
    expect(GENERATED_API_SOURCE).toContain("fallback_model_id");
    expect(GENERATED_API_SOURCE).toContain("fallback_enabled");
    expect(GENERATED_API_SOURCE).not.toContain("fallback_chain");
    expect(GENERATED_API_SOURCE).not.toContain("fallback_chain_enabled");

    expect(GENERATED_ZOD_SOURCE).toContain("fallback_provider_id");
    expect(GENERATED_ZOD_SOURCE).toContain("fallback_model_id");
    expect(GENERATED_ZOD_SOURCE).toContain("fallback_enabled");
    expect(GENERATED_ZOD_SOURCE).not.toContain("fallback_chain");
    expect(GENERATED_ZOD_SOURCE).not.toContain("fallback_chain_enabled");
  });

  it("exports the canonical provider-test response schema on @runsight/shared/zod", () => {
    const providerTestSample = {
      success: true,
      message: "Connection successful",
      models: ["gpt-4.1", "gpt-4o-mini"],
      model_count: 2,
      latency_ms: 123.4,
    };

    const providerTestSchema = getCanonicalSchema("ProviderTestOutSchema");

    expect(providerTestSchema.parse(providerTestSample)).toEqual(
      expect.objectContaining(providerTestSample),
    );
  });
});
