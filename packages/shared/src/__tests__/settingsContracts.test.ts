import { describe, expect, it } from "vitest";

type ParseableSchema = {
  parse: (input: unknown) => unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isParseableSchema(value: unknown): value is ParseableSchema {
  return isRecord(value) && typeof value.parse === "function";
}

async function findSchemaCandidate(
  pattern: RegExp,
  sample: unknown,
  validator: (parsed: unknown) => boolean,
) {
  const zodModule = await import("../zod");
  const matchingEntries = Object.entries(zodModule).filter(([name, value]) =>
    pattern.test(name) && isParseableSchema(value),
  );

  for (const [name, schema] of matchingEntries) {
    try {
      const parsed = schema.parse(sample);
      if (validator(parsed)) {
        return { name, available: matchingEntries.map(([entryName]) => entryName) };
      }
    } catch {
      // Keep searching until a matching contract can parse the full transport shape.
    }
  }

  return { name: null, available: matchingEntries.map(([entryName]) => entryName) };
}

describe("RUN-512 shared settings transport contracts", () => {
  it("exports a provider item schema and list schema that preserve the full settings provider response", async () => {
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

    const itemSchema = await findSchemaCandidate(
      /Provider.*Schema/i,
      providerSample,
      (parsed) =>
        isRecord(parsed) &&
        parsed.api_key_preview === providerSample.api_key_preview &&
        parsed.created_at === providerSample.created_at &&
        parsed.updated_at === providerSample.updated_at,
    );

    const listSchema = await findSchemaCandidate(
      /Provider.*Schema/i,
      { items: [providerSample], total: 1 },
      (parsed) =>
        isRecord(parsed) &&
        Array.isArray(parsed.items) &&
        isRecord(parsed.items[0]) &&
        parsed.items[0].created_at === providerSample.created_at &&
        parsed.items[0].updated_at === providerSample.updated_at &&
        parsed.total === 1,
    );

    expect(
      itemSchema.name,
      `Expected a shared provider response schema. Saw provider-related exports: ${itemSchema.available.join(", ") || "(none)"}`,
    ).not.toBeNull();
    expect(
      listSchema.name,
      `Expected a shared provider list schema. Saw provider-related exports: ${listSchema.available.join(", ") || "(none)"}`,
    ).not.toBeNull();
  });

  it("exports a model-default item schema and list schema for the settings adapter surface", async () => {
    const modelDefaultSample = {
      id: "openai",
      provider_id: "openai",
      provider_name: "OpenAI",
      model_name: "gpt-4.1",
      is_default: true,
      fallback_chain: ["gpt-4o-mini", "claude-3-5-sonnet"],
    };

    const itemSchema = await findSchemaCandidate(
      /ModelDefault.*Schema/i,
      modelDefaultSample,
      (parsed) =>
        isRecord(parsed) &&
        parsed.id === modelDefaultSample.id &&
        parsed.provider_id === modelDefaultSample.provider_id &&
        parsed.provider_name === modelDefaultSample.provider_name &&
        Array.isArray(parsed.fallback_chain),
    );

    const listSchema = await findSchemaCandidate(
      /ModelDefault.*Schema/i,
      { items: [modelDefaultSample], total: 1 },
      (parsed) =>
        isRecord(parsed) &&
        Array.isArray(parsed.items) &&
        isRecord(parsed.items[0]) &&
        parsed.items[0].provider_id === modelDefaultSample.provider_id &&
        parsed.items[0].provider_name === modelDefaultSample.provider_name &&
        parsed.total === 1,
    );

    expect(
      itemSchema.name,
      `Expected a shared model-default response schema. Saw model-default exports: ${itemSchema.available.join(", ") || "(none)"}`,
    ).not.toBeNull();
    expect(
      listSchema.name,
      `Expected a shared model-default list schema. Saw model-default exports: ${listSchema.available.join(", ") || "(none)"}`,
    ).not.toBeNull();
  });

  it("exports a budget item schema and list schema that keep spent and reset fields on the shared settings surface", async () => {
    const budgetSample = {
      id: "team",
      name: "Team Budget",
      limit_usd: 100,
      spent_usd: 42.5,
      period: "monthly",
      reset_at: "2026-04-30T00:00:00Z",
    };

    const itemSchema = await findSchemaCandidate(
      /Budget.*Schema/i,
      budgetSample,
      (parsed) =>
        isRecord(parsed) &&
        parsed.spent_usd === budgetSample.spent_usd &&
        parsed.reset_at === budgetSample.reset_at,
    );

    const listSchema = await findSchemaCandidate(
      /Budget.*Schema/i,
      { items: [budgetSample], total: 1 },
      (parsed) =>
        isRecord(parsed) &&
        Array.isArray(parsed.items) &&
        isRecord(parsed.items[0]) &&
        parsed.items[0].spent_usd === budgetSample.spent_usd &&
        parsed.items[0].reset_at === budgetSample.reset_at &&
        parsed.total === 1,
    );

    expect(
      itemSchema.name,
      `Expected a shared budget response schema. Saw budget-related exports: ${itemSchema.available.join(", ") || "(none)"}`,
    ).not.toBeNull();
    expect(
      listSchema.name,
      `Expected a shared budget list schema. Saw budget-related exports: ${listSchema.available.join(", ") || "(none)"}`,
    ).not.toBeNull();
  });
});
