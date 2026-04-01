import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const settingsSourcePath = resolve(__dirname, "..", "settings.ts");
const sharedParseSpies = vi.hoisted(
  () => new Map<string, ReturnType<typeof vi.fn<[unknown], unknown>>>(),
);
const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock("../client", () => ({
  api: {
    get: mocks.apiGet,
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@runsight/shared/zod", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("@runsight/shared/zod");

  sharedParseSpies.clear();

  for (const [name, exportedValue] of Object.entries(actual)) {
    if (
      exportedValue &&
      typeof exportedValue === "object" &&
      "parse" in exportedValue &&
      typeof (exportedValue as { parse?: unknown }).parse === "function"
    ) {
      const schema = exportedValue as { parse: (input: unknown) => unknown };
      const originalParse = schema.parse.bind(schema);
      const spy = vi.fn<[unknown], unknown>((input) => originalParse(input));
      sharedParseSpies.set(name, spy);
      schema.parse = spy;
    }
  }

  return actual;
});

function calledSharedSchemas(pattern: RegExp): string[] {
  return Array.from(sharedParseSpies.entries())
    .filter(([name, spy]) => pattern.test(name) && spy.mock.calls.length > 0)
    .map(([name]) => name);
}

beforeEach(() => {
  vi.resetModules();
  mocks.apiGet.mockReset();
  sharedParseSpies.forEach((spy) => spy.mockClear());
});

describe("RUN-512 settings API shared contract normalization", () => {
  it("parses provider lists through shared contracts and keeps API response fields that the transport exposes", async () => {
    const providerPayload = {
      items: [
        {
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
        },
      ],
      total: 1,
    };

    mocks.apiGet.mockResolvedValue(providerPayload);

    const { settingsApi } = await import("../settings");
    const result = await settingsApi.listProviders();

    expect(result.items[0]).toEqual(
      expect.objectContaining({
        api_key_preview: "sk-proj...abcd",
        created_at: "2026-03-01T00:00:00Z",
        updated_at: "2026-03-02T00:00:00Z",
      }),
    );
    expect(
      calledSharedSchemas(/Provider/i),
      "Expected settingsApi.listProviders() to parse via @runsight/shared/zod provider contracts",
    ).not.toHaveLength(0);
  });

  it("parses model defaults through shared contracts instead of GUI-local schemas", async () => {
    const modelDefaultsPayload = {
      items: [
        {
          id: "openai",
          provider_id: "openai",
          provider_name: "OpenAI",
          model_name: "gpt-4.1",
          is_default: true,
          fallback_chain: ["gpt-4o-mini", "claude-3-5-sonnet"],
        },
      ],
      total: 1,
    };

    mocks.apiGet.mockResolvedValue(modelDefaultsPayload);

    const { settingsApi } = await import("../settings");
    const result = await settingsApi.listModelDefaults();

    expect(result.items[0]).toEqual(
      expect.objectContaining({
        provider_id: "openai",
        provider_name: "OpenAI",
        fallback_chain: ["gpt-4o-mini", "claude-3-5-sonnet"],
      }),
    );
    expect(
      calledSharedSchemas(/ModelDefault/i),
      "Expected settingsApi.listModelDefaults() to parse via @runsight/shared/zod model-default contracts",
    ).not.toHaveLength(0);
  });

  it("parses budgets through shared contracts and preserves spent/reset transport fields", async () => {
    const budgetsPayload = {
      items: [
        {
          id: "team",
          name: "Team Budget",
          limit_usd: 100,
          spent_usd: 42.5,
          period: "monthly",
          reset_at: "2026-04-30T00:00:00Z",
        },
      ],
      total: 1,
    };

    mocks.apiGet.mockResolvedValue(budgetsPayload);

    const { settingsApi } = await import("../settings");
    const result = await settingsApi.getBudgets();

    expect(result.items[0]).toEqual(
      expect.objectContaining({
        spent_usd: 42.5,
        reset_at: "2026-04-30T00:00:00Z",
      }),
    );
    expect(
      calledSharedSchemas(/Budget/i),
      "Expected settingsApi.getBudgets() to parse via @runsight/shared/zod budget contracts",
    ).not.toHaveLength(0);
  });

  it("routes app settings parsing through the shared contract path", async () => {
    const appSettingsPayload = {
      base_path: "/workspace",
      default_provider: "openai",
      auto_save: true,
      onboarding_completed: true,
      fallback_chain_enabled: false,
    };

    mocks.apiGet.mockResolvedValue(appSettingsPayload);

    const { settingsApi } = await import("../settings");
    const result = await settingsApi.getAppSettings();

    expect(result).toEqual(expect.objectContaining(appSettingsPayload));
    expect(
      calledSharedSchemas(/AppSettings/i),
      "Expected settingsApi.getAppSettings() to parse via @runsight/shared/zod app-settings contracts",
    ).not.toHaveLength(0);
  });
});

describe("RUN-512 settings adapter drift guard", () => {
  it("keeps transport validation out of apps/gui/src/api/settings.ts", () => {
    const source = readFileSync(settingsSourcePath, "utf-8");

    expect(source).not.toMatch(/from\s+["']zod["']/);
    expect(source).not.toMatch(/z\.object\(/);
    expect(source).not.toMatch(
      /const\s+(Provider|ProviderList|ModelDefault|ModelDefaultList|Budget|BudgetList|AppSettings)Schema\s*=/,
    );
  });
});
