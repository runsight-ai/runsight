import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const settingsSourcePath = resolve(__dirname, "..", "settings.ts");
const sharedParseSpies = vi.hoisted(
  () => new Map<string, ReturnType<typeof vi.fn<[unknown], unknown>>>(),
);
const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
}));

vi.mock("../client", () => ({
  api: {
    get: mocks.apiGet,
    post: mocks.apiPost,
    put: mocks.apiPut,
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
  mocks.apiPost.mockReset();
  mocks.apiPut.mockReset();
  sharedParseSpies.forEach((spy) => spy.mockClear());
});

type SharedContractCase = {
  title: string;
  schemaPattern: RegExp;
  arrange: (payload: unknown) => void;
  invoke: (settingsApi: typeof import("../settings").settingsApi) => Promise<unknown>;
  assertResult: (result: unknown) => void;
  failureMessage: string;
};

const providerItemPayload = {
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

const modelDefaultItemPayload = {
  id: "openai",
  provider_id: "openai",
  provider_name: "OpenAI",
  model_name: "gpt-4.1",
  is_default: true,
  fallback_chain: ["gpt-4o-mini", "claude-3-5-sonnet"],
};

const budgetItemPayload = {
  id: "team",
  name: "Team Budget",
  limit_usd: 100,
  spent_usd: 42.5,
  period: "monthly",
  reset_at: "2026-04-30T00:00:00Z",
};

const appSettingsPayload = {
  base_path: "/workspace",
  default_provider: "openai",
  auto_save: true,
  onboarding_completed: true,
  fallback_chain_enabled: false,
};

describe("RUN-512 settings API shared contract normalization", () => {
  const contractCases: SharedContractCase[] = [
    {
      title: "parses provider lists through shared contracts and keeps API response fields that the transport exposes",
      schemaPattern: /Provider/i,
      arrange: (payload) => {
        mocks.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.listProviders(),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            items: [
              expect.objectContaining({
                api_key_preview: providerItemPayload.api_key_preview,
                created_at: providerItemPayload.created_at,
                updated_at: providerItemPayload.updated_at,
              }),
            ],
            total: 1,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.listProviders() to parse via @runsight/shared/zod provider contracts",
    },
    {
      title: "parses getProvider responses through shared contracts and preserves provider transport fields",
      schemaPattern: /Provider/i,
      arrange: (payload) => {
        mocks.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.getProvider("openai"),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            api_key_preview: providerItemPayload.api_key_preview,
            created_at: providerItemPayload.created_at,
            updated_at: providerItemPayload.updated_at,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.getProvider() to parse via @runsight/shared/zod provider contracts",
    },
    {
      title: "parses createProvider responses through shared contracts and preserves provider transport fields",
      schemaPattern: /Provider/i,
      arrange: (payload) => {
        mocks.apiPost.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.createProvider({
          name: "OpenAI",
          api_key_env: "OPENAI_API_KEY",
          base_url: "https://api.openai.com/v1",
        }),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            api_key_preview: providerItemPayload.api_key_preview,
            created_at: providerItemPayload.created_at,
            updated_at: providerItemPayload.updated_at,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.createProvider() to parse via @runsight/shared/zod provider contracts",
    },
    {
      title: "parses updateProvider responses through shared contracts and preserves provider transport fields",
      schemaPattern: /Provider/i,
      arrange: (payload) => {
        mocks.apiPut.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.updateProvider("openai", {
          name: "OpenAI",
          api_key_env: "OPENAI_API_KEY",
          base_url: "https://api.openai.com/v1",
        }),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            api_key_preview: providerItemPayload.api_key_preview,
            created_at: providerItemPayload.created_at,
            updated_at: providerItemPayload.updated_at,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.updateProvider() to parse via @runsight/shared/zod provider contracts",
    },
    {
      title: "parses model defaults through shared contracts instead of GUI-local schemas",
      schemaPattern: /ModelDefault/i,
      arrange: (payload) => {
        mocks.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.listModelDefaults(),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            items: [
              expect.objectContaining({
                provider_id: modelDefaultItemPayload.provider_id,
                provider_name: modelDefaultItemPayload.provider_name,
                fallback_chain: modelDefaultItemPayload.fallback_chain,
              }),
            ],
            total: 1,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.listModelDefaults() to parse via @runsight/shared/zod model-default contracts",
    },
    {
      title: "parses updateModelDefault responses through shared contracts",
      schemaPattern: /ModelDefault/i,
      arrange: (payload) => {
        mocks.apiPut.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.updateModelDefault("openai", {
          model_name: "gpt-4.1",
          is_default: true,
          fallback_chain: modelDefaultItemPayload.fallback_chain,
        }),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            provider_id: modelDefaultItemPayload.provider_id,
            provider_name: modelDefaultItemPayload.provider_name,
            fallback_chain: modelDefaultItemPayload.fallback_chain,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.updateModelDefault() to parse via @runsight/shared/zod model-default contracts",
    },
    {
      title: "parses budgets through shared contracts and preserves spent/reset transport fields",
      schemaPattern: /Budget/i,
      arrange: (payload) => {
        mocks.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.getBudgets(),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            items: [
              expect.objectContaining({
                spent_usd: budgetItemPayload.spent_usd,
                reset_at: budgetItemPayload.reset_at,
              }),
            ],
            total: 1,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.getBudgets() to parse via @runsight/shared/zod budget contracts",
    },
    {
      title: "parses createBudget responses through shared contracts and preserves spent/reset transport fields",
      schemaPattern: /Budget/i,
      arrange: (payload) => {
        mocks.apiPost.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.createBudget({
          name: "Team Budget",
          limit_usd: 100,
          period: "monthly",
        }),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            spent_usd: budgetItemPayload.spent_usd,
            reset_at: budgetItemPayload.reset_at,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.createBudget() to parse via @runsight/shared/zod budget contracts",
    },
    {
      title: "parses updateBudget responses through shared contracts and preserves spent/reset transport fields",
      schemaPattern: /Budget/i,
      arrange: (payload) => {
        mocks.apiPut.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.updateBudget("team", {
          name: "Team Budget",
          limit_usd: 100,
          period: "monthly",
        }),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            spent_usd: budgetItemPayload.spent_usd,
            reset_at: budgetItemPayload.reset_at,
          }),
        );
      },
      failureMessage:
        "Expected settingsApi.updateBudget() to parse via @runsight/shared/zod budget contracts",
    },
    {
      title: "routes app settings parsing through the shared contract path",
      schemaPattern: /AppSettings/i,
      arrange: (payload) => {
        mocks.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.getAppSettings(),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(appSettingsPayload));
      },
      failureMessage:
        "Expected settingsApi.getAppSettings() to parse via @runsight/shared/zod app-settings contracts",
    },
    {
      title: "routes updateAppSettings parsing through the shared contract path",
      schemaPattern: /AppSettings/i,
      arrange: (payload) => {
        mocks.apiPut.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.updateAppSettings({
          onboarding_completed: true,
          fallback_chain_enabled: false,
        }),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(appSettingsPayload));
      },
      failureMessage:
        "Expected settingsApi.updateAppSettings() to parse via @runsight/shared/zod app-settings contracts",
    },
  ];

  it.each(contractCases)("$title", async ({
    arrange,
    assertResult,
    failureMessage,
    invoke,
    schemaPattern,
    title,
  }) => {
    const payload =
      title.includes("provider lists")
        ? { items: [providerItemPayload], total: 1 }
        : title.includes("model defaults")
          ? { items: [modelDefaultItemPayload], total: 1 }
          : title.includes("budgets through")
            ? { items: [budgetItemPayload], total: 1 }
            : title.includes("app settings")
              ? appSettingsPayload
              : schemaPattern.test("Provider")
                ? providerItemPayload
                : schemaPattern.test("ModelDefault")
                  ? modelDefaultItemPayload
                  : schemaPattern.test("Budget")
                    ? budgetItemPayload
                    : appSettingsPayload;

    arrange(payload);

    const { settingsApi } = await import("../settings");
    const result = await invoke(settingsApi);

    assertResult(result);
    expect(calledSharedSchemas(schemaPattern), failureMessage).not.toHaveLength(0);
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
