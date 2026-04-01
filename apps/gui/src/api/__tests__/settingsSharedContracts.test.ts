import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it, vi } from "vitest";

const testState = vi.hoisted(() => ({
  contractMarker: Symbol("runsight.shared-settings-contract-marker"),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
}));

type ParseableSchema = {
  parse: (input: unknown) => unknown;
  transform: (transformer: (parsed: unknown) => unknown) => ParseableSchema;
};

type SharedContractCase = {
  title: string;
  payload: unknown;
  arrange: (payload: unknown) => void;
  invoke: (settingsApi: typeof import("../settings").settingsApi) => Promise<unknown>;
  assertResult: (result: unknown) => void;
};

type SourceSchemaDefinition = {
  name: string;
  body: string;
};

function isRecord(value: unknown): value is Record<PropertyKey, unknown> {
  return typeof value === "object" && value !== null;
}

function isParseableSchema(value: unknown): value is ParseableSchema {
  return (
    isRecord(value) &&
    typeof value.parse === "function" &&
    typeof value.transform === "function"
  );
}

function shouldWrapSharedSchemaExport(name: string, value: unknown): value is ParseableSchema {
  return /(?:Provider|ModelDefault|Budget|AppSettings).*Schema/i.test(name) && isParseableSchema(value);
}

function withSharedContractMarker(value: unknown, schemaName: string) {
  if (!isRecord(value)) {
    return value;
  }

  const target = Object.isExtensible(value)
    ? value
    : Array.isArray(value)
      ? [...value]
      : { ...value };
  const existingMarker = target[testState.contractMarker];
  const markerSet = existingMarker instanceof Set ? new Set(existingMarker) : new Set<string>();

  markerSet.add(schemaName);
  Object.defineProperty(target, testState.contractMarker, {
    configurable: true,
    enumerable: false,
    value: markerSet,
  });

  return target;
}

function wrapSharedSchemaExports<TModule extends Record<string, unknown>>(module: TModule): TModule {
  const wrappedEntries = Object.fromEntries(
    Object.entries(module).map(([name, value]) => [
      name,
      shouldWrapSharedSchemaExport(name, value)
        ? value.transform((parsed) => withSharedContractMarker(parsed, name))
        : value,
    ]),
  );

  return { ...module, ...wrappedEntries };
}

function hasSharedContractMarker(value: unknown): boolean {
  if (!isRecord(value)) {
    return false;
  }

  const marker = value[testState.contractMarker];
  if (marker instanceof Set && marker.size > 0) {
    return true;
  }

  if (Array.isArray(value)) {
    return value.some((item) => hasSharedContractMarker(item));
  }

  return Object.values(value).some((item) => hasSharedContractMarker(item));
}

function expectSharedContractMarker(result: unknown) {
  expect(hasSharedContractMarker(result)).toBe(true);
}

function extractTopLevelZObjectSchemas(source: string): SourceSchemaDefinition[] {
  const definitions: SourceSchemaDefinition[] = [];
  const schemaStartPattern = /^const\s+(\w+)\s*=\s*z\.object\s*\(\s*\{/gm;

  for (const match of source.matchAll(schemaStartPattern)) {
    const [matchedText, name] = match;
    const startIndex = match.index ?? 0;
    const bodyStart = startIndex + matchedText.lastIndexOf("{");
    let depth = 0;
    let bodyEnd = -1;

    for (let index = bodyStart; index < source.length; index += 1) {
      const char = source[index];

      if (char === "{") {
        depth += 1;
        continue;
      }

      if (char === "}") {
        depth -= 1;
        if (depth === 0) {
          bodyEnd = index;
          break;
        }
      }
    }

    if (bodyEnd === -1) {
      continue;
    }

    definitions.push({
      name,
      body: source.slice(bodyStart + 1, bodyEnd),
    });
  }

  return definitions;
}

function matchesDuplicateTransportShape(body: string, fieldPatterns: RegExp[]) {
  return fieldPatterns.every((pattern) => pattern.test(body));
}

vi.mock("../client", () => ({
  api: {
    get: testState.apiGet,
    post: testState.apiPost,
    put: testState.apiPut,
    delete: vi.fn(),
  },
}));

vi.mock("@runsight/shared/zod", async () => {
  const actual = await vi.importActual<typeof import("@runsight/shared/zod")>("@runsight/shared/zod");

  return wrapSharedSchemaExports(actual);
});

vi.mock("@runsight/shared", async () => {
  const actual = await vi.importActual<typeof import("@runsight/shared")>("@runsight/shared");

  return wrapSharedSchemaExports(actual);
});

beforeEach(() => {
  vi.resetModules();
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

describe("RUN-512 settings API shared contract normalization", () => {
  const contractCases: SharedContractCase[] = [
    {
      title: "parses provider lists through shared contracts and preserves provider transport fields",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses getProvider responses through shared contracts and preserves provider transport fields",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses createProvider responses through shared contracts and preserves provider transport fields",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses updateProvider responses through shared contracts and preserves provider transport fields",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses model defaults through shared contracts instead of GUI-local schemas",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses updateModelDefault responses through shared contracts",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses budgets through shared contracts and preserves spent/reset transport fields",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses createBudget responses through shared contracts and preserves spent/reset transport fields",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "parses updateBudget responses through shared contracts and preserves spent/reset transport fields",
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
        expectSharedContractMarker(result);
      },
    },
    {
      title: "keeps the full app settings surface when reading settings through shared contracts",
      payload: appSettingsPayload,
      arrange: (payload) => {
        testState.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.getAppSettings(),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(appSettingsPayload));
        expectSharedContractMarker(result);
      },
    },
    {
      title: "keeps the full app settings surface when updating settings through shared contracts",
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
        expectSharedContractMarker(result);
      },
    },
  ];

  it.each(contractCases)("$title", async ({ arrange, assertResult, invoke, payload }) => {
    arrange(payload);

    const { settingsApi } = await import("../settings");
    const result = await invoke(settingsApi);

    assertResult(result);
  });

  it("does not keep GUI-local top-level z.object transport schemas for shared settings surfaces", () => {
    const settingsSource = readFileSync(new URL("../settings.ts", import.meta.url), "utf8");
    const topLevelSchemas = extractTopLevelZObjectSchemas(settingsSource);
    const duplicateTransportShapes = [
      {
        concern: "provider item settings transport",
        fieldPatterns: [/api_key_env\s*:/, /api_key_preview\s*:/, /model_count\s*:/, /is_configured\s*:/],
      },
      {
        concern: "model-default item settings transport",
        fieldPatterns: [/provider_id\s*:/, /provider_name\s*:/, /model_name\s*:/, /fallback_chain\s*:/],
      },
      {
        concern: "budget item settings transport",
        fieldPatterns: [/\bid\s*:/, /\bname\s*:/, /limit_usd\s*:/, /period\s*:/],
      },
      {
        concern: "app-settings transport",
        fieldPatterns: [/onboarding_completed\s*:/, /fallback_chain_enabled\s*:/],
      },
    ];

    const duplicateSchemas = topLevelSchemas.flatMap((schema) =>
      duplicateTransportShapes
        .filter(({ fieldPatterns }) => matchesDuplicateTransportShape(schema.body, fieldPatterns))
        .map(({ concern }) => `${schema.name} (${concern})`),
    );

    expect(
      duplicateSchemas,
      [
        "Expected apps/gui/src/api/settings.ts to remove dead GUI-local settings transport schemas once shared contracts are in place.",
        `Found duplicate top-level z.object definitions: ${duplicateSchemas.join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);
  });
});
