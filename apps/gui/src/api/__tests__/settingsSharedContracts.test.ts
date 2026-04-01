import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it, vi } from "vitest";

const settingsSource = readFileSync(new URL("../settings.ts", import.meta.url), "utf8");

const testState = vi.hoisted(() => ({
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
}));

type SharedContractCase = {
  title: string;
  payload: unknown;
  arrange: (payload: unknown) => void;
  invoke: (settingsApi: typeof import("../settings").settingsApi) => Promise<unknown>;
  assertResult: (result: unknown) => void;
};

function escapeForRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function collectImportedSpecifiers(source: string, modulePath: string) {
  const modulePattern = escapeForRegExp(modulePath);
  const importPattern = new RegExp(
    `import\\s*{([^;]*?)}\\s*from\\s*[\"']${modulePattern}[\"'];`,
    "g",
  );

  return [...source.matchAll(importPattern)].flatMap((match) =>
    match[1]
      .split(",")
      .map((specifier) => specifier.trim())
      .filter(Boolean)
      .map((specifier) => specifier.split(/\s+as\s+/)[0]?.trim() ?? specifier),
  );
}

function countIdentifierReferences(source: string, identifier: string) {
  return [...source.matchAll(new RegExp(`\\b${escapeForRegExp(identifier)}\\b`, "g"))].length;
}

function collectLocalSettingsSchemaDeclarations(source: string) {
  const localSchemaPattern =
    /^const\s+((?:\w*Provider\w*Schema|\w*ModelDefault\w*Schema|\w*Budget\w*Schema|AppSettings\w*Schema))\s*=/gm;

  return [...source.matchAll(localSchemaPattern)].map((match) => match[1] ?? "");
}

vi.mock("../client", () => ({
  api: {
    delete: testState.apiDelete,
    get: testState.apiGet,
    post: testState.apiPost,
    put: testState.apiPut,
  },
}));

beforeEach(() => {
  vi.resetModules();
  testState.apiDelete.mockReset();
  testState.apiGet.mockReset();
  testState.apiPost.mockReset();
  testState.apiPut.mockReset();
});

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

describe("RUN-512 settings API canonical shared contracts", () => {
  it("imports and references the canonical settings schemas from @runsight/shared/zod", () => {
    const expectedSchemas = [
      "SettingsProviderResponseSchema",
      "SettingsProviderListResponseSchema",
      "SettingsModelDefaultResponseSchema",
      "SettingsModelDefaultListResponseSchema",
      "SettingsBudgetResponseSchema",
      "SettingsBudgetListResponseSchema",
      "AppSettingsOutSchema",
    ];
    const importedSchemas = collectImportedSpecifiers(settingsSource, "@runsight/shared/zod");

    expect(
      importedSchemas,
      `Expected apps/gui/src/api/settings.ts to import the canonical settings transport schemas from @runsight/shared/zod`,
    ).toEqual(expect.arrayContaining(expectedSchemas));

    for (const schemaName of expectedSchemas) {
      expect(
        countIdentifierReferences(settingsSource, schemaName),
        `Expected apps/gui/src/api/settings.ts to reference ${schemaName} after importing it from @runsight/shared/zod`,
      ).toBeGreaterThan(1);
    }
  });

  it("does not keep GUI-local provider, model-default, budget, or app-settings transport schemas", () => {
    const localSchemaDeclarations = collectLocalSettingsSchemaDeclarations(settingsSource);

    expect(
      localSchemaDeclarations,
      [
        "Expected apps/gui/src/api/settings.ts to stop declaring GUI-local settings transport schemas once the canonical shared imports exist.",
        `Found local declarations: ${localSchemaDeclarations.join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
  });

  const contractCases: SharedContractCase[] = [
    {
      title: "preserves provider transport fields for listProviders",
      payload: { items: [providerItemPayload], total: 1 },
      arrange: (payload) => {
        testState.apiGet.mockResolvedValue(payload);
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
      title: "preserves provider transport fields for getProvider",
      payload: providerItemPayload,
      arrange: (payload) => {
        testState.apiGet.mockResolvedValue(payload);
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
      title: "preserves provider transport fields for createProvider",
      payload: providerItemPayload,
      arrange: (payload) => {
        testState.apiPost.mockResolvedValue(payload);
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
      title: "preserves provider transport fields for updateProvider",
      payload: providerItemPayload,
      arrange: (payload) => {
        testState.apiPut.mockResolvedValue(payload);
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
      title: "preserves model-default transport fields for listModelDefaults",
      payload: { items: [modelDefaultItemPayload], total: 1 },
      arrange: (payload) => {
        testState.apiGet.mockResolvedValue(payload);
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
      title: "preserves model-default transport fields for updateModelDefault",
      payload: modelDefaultItemPayload,
      arrange: (payload) => {
        testState.apiPut.mockResolvedValue(payload);
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
      title: "preserves budget transport fields for getBudgets",
      payload: { items: [budgetItemPayload], total: 1 },
      arrange: (payload) => {
        testState.apiGet.mockResolvedValue(payload);
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
      title: "preserves budget transport fields for createBudget",
      payload: budgetItemPayload,
      arrange: (payload) => {
        testState.apiPost.mockResolvedValue(payload);
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
      title: "preserves budget transport fields for updateBudget",
      payload: budgetItemPayload,
      arrange: (payload) => {
        testState.apiPut.mockResolvedValue(payload);
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
      title: "preserves app-settings transport fields for getAppSettings",
      payload: appSettingsPayload,
      arrange: (payload) => {
        testState.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.getAppSettings(),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(appSettingsPayload));
      },
    },
    {
      title: "preserves app-settings transport fields for updateAppSettings",
      payload: appSettingsPayload,
      arrange: (payload) => {
        testState.apiPut.mockResolvedValue(payload);
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
