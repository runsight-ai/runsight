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
      fallback_chain: ["gpt-4o-mini", "claude-3-5-sonnet"],
    };

    const modelDefaultItemSchema = getCanonicalSchema("SettingsModelDefaultResponseSchema");
    const modelDefaultListSchema = getCanonicalSchema("SettingsModelDefaultListResponseSchema");

    expect(modelDefaultItemSchema.parse(modelDefaultSample)).toEqual(
      expect.objectContaining({
        provider_id: modelDefaultSample.provider_id,
        provider_name: modelDefaultSample.provider_name,
        fallback_chain: modelDefaultSample.fallback_chain,
      }),
    );
    expect(modelDefaultListSchema.parse({ items: [modelDefaultSample], total: 1 })).toEqual(
      expect.objectContaining({
        items: [
          expect.objectContaining({
            provider_id: modelDefaultSample.provider_id,
            provider_name: modelDefaultSample.provider_name,
            fallback_chain: modelDefaultSample.fallback_chain,
          }),
        ],
        total: 1,
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
      fallback_chain_enabled: false,
    };

    const appSettingsSchema = getCanonicalSchema("AppSettingsOutSchema");

    expect(appSettingsSchema.parse(appSettingsSample)).toEqual(
      expect.objectContaining(appSettingsSample),
    );
  });
});
