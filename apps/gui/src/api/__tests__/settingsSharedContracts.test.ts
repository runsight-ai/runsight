import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const settingsSourcePath = resolve(__dirname, "..", "settings.ts");
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

beforeEach(() => {
  vi.resetModules();
  mocks.apiGet.mockReset();
  mocks.apiPost.mockReset();
  mocks.apiPut.mockReset();
});

type SharedContractCase = {
  title: string;
  payload: unknown;
  arrange: (payload: unknown) => void;
  invoke: (settingsApi: typeof import("../settings").settingsApi) => Promise<unknown>;
  assertResult: (result: unknown) => void;
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
      payload: { items: [providerItemPayload], total: 1 },
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
    },
    {
      title: "parses getProvider responses through shared contracts and preserves provider transport fields",
      payload: providerItemPayload,
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
    },
    {
      title: "parses createProvider responses through shared contracts and preserves provider transport fields",
      payload: providerItemPayload,
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
    },
    {
      title: "parses updateProvider responses through shared contracts and preserves provider transport fields",
      payload: providerItemPayload,
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
    },
    {
      title: "parses model defaults through shared contracts instead of GUI-local schemas",
      payload: { items: [modelDefaultItemPayload], total: 1 },
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
    },
    {
      title: "parses updateModelDefault responses through shared contracts",
      payload: modelDefaultItemPayload,
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
    },
    {
      title: "parses budgets through shared contracts and preserves spent/reset transport fields",
      payload: { items: [budgetItemPayload], total: 1 },
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
    },
    {
      title: "parses createBudget responses through shared contracts and preserves spent/reset transport fields",
      payload: budgetItemPayload,
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
    },
    {
      title: "parses updateBudget responses through shared contracts and preserves spent/reset transport fields",
      payload: budgetItemPayload,
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
    },
    {
      title: "keeps the full app settings surface when reading settings",
      payload: appSettingsPayload,
      arrange: (payload) => {
        mocks.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.getAppSettings(),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(appSettingsPayload));
      },
    },
    {
      title: "keeps the full app settings surface when updating settings",
      payload: appSettingsPayload,
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
    },
  ];

  it.each(contractCases)("$title", async ({ arrange, assertResult, invoke, payload }) => {
    arrange(payload);

    const { settingsApi } = await import("../settings");
    const result = await invoke(settingsApi);

    assertResult(result);
  });
});

describe("RUN-512 settings adapter drift guard", () => {
  it("blocks direct GUI-local settings transport schema definitions while allowing shared-schema composition", () => {
    const source = readFileSync(settingsSourcePath, "utf-8");

    expect(source).not.toMatch(/const\s+ProviderSchema\s*=\s*z\.object\(/);
    expect(source).not.toMatch(/const\s+ModelDefaultSchema\s*=\s*z\.object\(/);
    expect(source).not.toMatch(/const\s+BudgetSchema\s*=\s*z\.object\(/);
    expect(source).not.toMatch(/const\s+AppSettingsSchema\s*=\s*z\.object\(/);
  });
});
