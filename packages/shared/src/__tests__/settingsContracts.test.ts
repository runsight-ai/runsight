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

describe("canonical settings transport contracts", () => {
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
      is_active: true,
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

  it("exports canonical fallback item and list schemas on @runsight/shared/zod", () => {
    const fallbackSample = {
      id: "openai",
      provider_id: "openai",
      provider_name: "OpenAI",
      fallback_provider_id: "anthropic",
      fallback_model_id: "claude-sonnet-4",
    };

    const fallbackItemSchema = getCanonicalSchema("SettingsFallbackResponseSchema");
    const fallbackListSchema = getCanonicalSchema("SettingsFallbackListResponseSchema");
    const fallbackUpdateSchema = getCanonicalSchema("FallbackUpdateSchema");

    expect(fallbackItemSchema.parse(fallbackSample)).toEqual(
      expect.objectContaining(fallbackSample),
    );
    expect(fallbackListSchema.parse({ items: [fallbackSample], total: 1 })).toEqual(
      expect.objectContaining({
        items: [expect.objectContaining(fallbackSample)],
        total: 1,
      }),
    );
    expect(
      fallbackUpdateSchema.parse({
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

  it("exports the canonical app-settings schema on @runsight/shared/zod", () => {
    const appSettingsSample = {
      base_path: "/workspace",
      auto_save: true,
      onboarding_completed: true,
      fallback_enabled: false,
    };

    const appSettingsSchema = getCanonicalSchema("AppSettingsOutSchema");

    const parsed = appSettingsSchema.parse(appSettingsSample);

    expect(parsed).toEqual(
      expect.objectContaining(appSettingsSample),
    );
    expect(parsed).not.toHaveProperty("auto_save");
  });

  it("keeps generated OpenAPI and shared contract artifacts on fallback-only settings fields", () => {
    const settingsFallbackProps = getSchemaProperties("SettingsFallbackResponse");
    const fallbackUpdateProps = getSchemaProperties("FallbackUpdate");
    const appSettingsProps = getSchemaProperties("AppSettingsOut");

    expect(settingsFallbackProps).toHaveProperty("fallback_provider_id");
    expect(settingsFallbackProps).toHaveProperty("fallback_model_id");
    expect(settingsFallbackProps).not.toHaveProperty("model_name");

    expect(fallbackUpdateProps).toHaveProperty("fallback_provider_id");
    expect(fallbackUpdateProps).toHaveProperty("fallback_model_id");

    expect(appSettingsProps).toHaveProperty("fallback_enabled");
    expect(appSettingsProps).not.toHaveProperty("default_provider");
    expect(appSettingsProps).not.toHaveProperty("fallback_chain_enabled");
    expect(appSettingsProps).not.toHaveProperty("auto_save");

    expect(GENERATED_API_SOURCE).toContain("/api/settings/fallbacks");
    expect(GENERATED_API_SOURCE).toContain("SettingsFallbackResponse");
    expect(GENERATED_API_SOURCE).toContain("fallback_enabled");
    expect(GENERATED_API_SOURCE).not.toContain("auto_save");
    expect(GENERATED_API_SOURCE).not.toContain("/api/settings/models");
    expect(GENERATED_API_SOURCE).not.toContain("/api/settings/models/{model_id}");
    expect(GENERATED_API_SOURCE).not.toContain("SettingsModelDefaultResponse");
    expect(GENERATED_API_SOURCE).not.toContain("SettingsModelDefaultListResponse");
    expect(GENERATED_API_SOURCE).not.toContain("list_model_defaults_api_settings_models_get");
    expect(GENERATED_API_SOURCE).not.toContain(
      "update_model_default_api_settings_models__model_id__put",
    );
    expect(GENERATED_API_SOURCE).not.toContain("default_provider");

    expect(GENERATED_ZOD_SOURCE).toContain("SettingsFallbackResponseSchema");
    expect(GENERATED_ZOD_SOURCE).toContain("FallbackUpdateSchema");
    expect(GENERATED_ZOD_SOURCE).toContain("fallback_enabled");
    expect(GENERATED_ZOD_SOURCE).not.toContain("auto_save");
    expect(GENERATED_ZOD_SOURCE).not.toContain("SettingsModelDefaultResponseSchema");
    expect(GENERATED_ZOD_SOURCE).not.toContain("default_provider");
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
