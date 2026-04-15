import { readFileSync } from "node:fs";
import type { settingsApi as SettingsApi } from "../settings";
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
  invoke: (settingsApi: typeof SettingsApi) => Promise<unknown>;
  assertResult: (result: unknown) => void;
};

type CanonicalImportBindings = {
  named: Map<string, string[]>;
  namespaces: string[];
};

type LocalSchemaConstruction = {
  binding: string;
  body: string;
  statement: string;
};

function escapeForRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function collectCanonicalImportBindings(source: string, modulePath: string): CanonicalImportBindings {
  const modulePattern = escapeForRegExp(modulePath);
  const namedImportPattern = new RegExp(
    `import\\s*{([^;]*?)}\\s*from\\s*["']${modulePattern}["'];`,
    "g",
  );
  const namespaceImportPattern = new RegExp(
    `import\\s*\\*\\s*as\\s*(\\w+)\\s*from\\s*["']${modulePattern}["'];`,
    "g",
  );
  const named = new Map<string, string[]>();
  const namespaces = [...source.matchAll(namespaceImportPattern)].map((match) => match[1] ?? "");

  for (const match of source.matchAll(namedImportPattern)) {
    for (const specifier of match[1]
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)) {
      const [importedName, localName = importedName] = specifier.split(/\s+as\s+/).map((entry) => entry.trim());
      const existing = named.get(importedName) ?? [];

      existing.push(localName);
      named.set(importedName, existing);
    }
  }

  return { named, namespaces };
}

function getCanonicalSchemaReferences(
  importBindings: CanonicalImportBindings,
  exportedSchemaName: string,
) {
  return [
    ...(importBindings.named.get(exportedSchemaName) ?? []),
    ...importBindings.namespaces.map((namespaceImport) => `${namespaceImport}.${exportedSchemaName}`),
  ];
}

function extractParseTarget(source: string, methodName: string) {
  const parsePattern = new RegExp(
    `${methodName}:\\s*async[\\s\\S]*?return\\s+([^;]+?)\\.parse\\(res\\);`,
    "m",
  );
  const match = source.match(parsePattern);

  return match?.[1]?.trim() ?? null;
}

function collectLocalZObjectConstructions(source: string): LocalSchemaConstruction[] {
  const constructions: LocalSchemaConstruction[] = [];
  const constructionPattern = /^const\s+(\w+)\s*=\s*(?:\w+)\.object\s*\(\s*\{/gm;

  for (const match of source.matchAll(constructionPattern)) {
    const [matchedText, binding] = match;
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

    const statementEnd = source.indexOf(";", bodyEnd);
    const statement = source.slice(startIndex, statementEnd === -1 ? source.length : statementEnd + 1);

    constructions.push({
      binding,
      body: source.slice(bodyStart + 1, bodyEnd),
      statement,
    });
  }

  return constructions;
}

function matchesAllPatterns(body: string, patterns: RegExp[]) {
  return patterns.every((pattern) => pattern.test(body));
}

function collectLocalConcernBindings(source: string) {
  const constructions = collectLocalZObjectConstructions(source);
  const concernDefinitions = [
    {
      concern: "provider",
      fieldPatterns: [/api_key_env\s*:/, /api_key_preview\s*:/, /model_count\s*:/, /is_configured\s*:/],
    },
    {
      concern: "fallback",
      fieldPatterns: [/provider_id\s*:/, /provider_name\s*:/, /fallback_provider_id\s*:/, /fallback_model_id\s*:/],
    },
    {
      concern: "app-settings",
      fieldPatterns: [/onboarding_completed\s*:/, /fallback_enabled\s*:/],
    },
  ];

  return concernDefinitions.flatMap(({ concern, fieldPatterns }) => {
    const itemBindings = constructions
      .filter((construction) => matchesAllPatterns(construction.body, fieldPatterns))
      .map((construction) => construction.binding);
    const listBindings = constructions
      .filter(
        (construction) =>
          /items\s*:/.test(construction.body) &&
          /total\s*:/.test(construction.body) &&
          itemBindings.some((binding) =>
            new RegExp(`\\bz\\.array\\(\\s*${escapeForRegExp(binding)}\\s*\\)`).test(construction.statement),
          ),
      )
      .map((construction) => construction.binding);

    return [...itemBindings, ...listBindings].map((binding) => ({ binding, concern }));
  });
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
  kind: "provider",
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
  fallback_provider_id: "anthropic",
  fallback_model_id: "claude-sonnet-4",
};

const appSettingsPayload = {
  base_path: "/workspace",
  onboarding_completed: true,
  fallback_enabled: false,
};

const providerTestPayload = {
  success: true,
  message: "Connection successful",
  models: ["gpt-4.1", "gpt-4o-mini"],
  model_count: 2,
  latency_ms: 123.4,
};

describe("RUN-512 settings API canonical shared contracts", () => {
  it("sources settings-surface parse calls from the canonical @runsight/shared/zod path", () => {
    const importBindings = collectCanonicalImportBindings(settingsSource, "@runsight/shared/zod");
    const parseExpectations = [
      { methodName: "listProviders", exportedSchemaName: "SettingsProviderListResponseSchema" },
      { methodName: "getProvider", exportedSchemaName: "SettingsProviderResponseSchema" },
      { methodName: "createProvider", exportedSchemaName: "SettingsProviderResponseSchema" },
      { methodName: "updateProvider", exportedSchemaName: "SettingsProviderResponseSchema" },
      { methodName: "listFallbackTargets", exportedSchemaName: "SettingsFallbackListResponseSchema" },
      { methodName: "updateFallbackTarget", exportedSchemaName: "SettingsFallbackResponseSchema" },
      { methodName: "getAppSettings", exportedSchemaName: "AppSettingsOutSchema" },
      { methodName: "updateAppSettings", exportedSchemaName: "AppSettingsOutSchema" },
      { methodName: "testProviderConnection", exportedSchemaName: "ProviderTestOutSchema" },
      { methodName: "testProviderCredentials", exportedSchemaName: "ProviderTestOutSchema" },
    ];

    expect(
      importBindings.named.size > 0 || importBindings.namespaces.length > 0,
      "Expected apps/gui/src/api/settings.ts to value-import settings schemas from @runsight/shared/zod",
    ).toBe(true);

    for (const { methodName, exportedSchemaName } of parseExpectations) {
      const canonicalReferences = getCanonicalSchemaReferences(importBindings, exportedSchemaName);
      const parseTarget = extractParseTarget(settingsSource, methodName);

      expect(
        canonicalReferences.length,
        `Expected ${exportedSchemaName} to be sourced from @runsight/shared/zod using a named, aliased, or namespace import in apps/gui/src/api/settings.ts`,
      ).toBeGreaterThan(0);
      expect(
        parseTarget,
        `Expected ${methodName} to parse through a schema sourced from @runsight/shared/zod`,
      ).toBeTruthy();
      expect(
        canonicalReferences,
        `Expected ${methodName} to parse with a symbol originating from @runsight/shared/zod`,
      ).toContain(parseTarget);
    }
  });

  it("does not locally construct or parse settings-surface transport schemas in settings.ts", () => {
    const localConcernBindings = collectLocalConcernBindings(settingsSource);
    const parseTargetsByMethod = [
      "listProviders",
      "getProvider",
      "createProvider",
      "updateProvider",
      "listFallbackTargets",
      "updateFallbackTarget",
      "getAppSettings",
      "updateAppSettings",
      "testProviderConnection",
      "testProviderCredentials",
    ].map((methodName) => ({
      methodName,
      parseTarget: extractParseTarget(settingsSource, methodName),
    }));

    expect(
      localConcernBindings,
      [
        "Expected apps/gui/src/api/settings.ts to stop locally constructing provider/model-default/app-settings transport schemas.",
        "Expected apps/gui/src/api/settings.ts to stop locally constructing provider/fallback/app-settings transport schemas.",
        `Found local constructions: ${localConcernBindings.map(({ binding, concern }) => `${binding} (${concern})`).join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);

    for (const { methodName, parseTarget } of parseTargetsByMethod) {
      expect(
        localConcernBindings.map(({ binding }) => binding),
        `Expected ${methodName} to avoid parsing through a locally constructed settings transport schema`,
      ).not.toContain(parseTarget);
    }
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
          id: "openai",
          kind: "provider",
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
          id: "openai",
          kind: "provider",
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
      title: "preserves fallback transport fields for listFallbackTargets",
      payload: { items: [modelDefaultItemPayload], total: 1 },
      arrange: (payload) => {
        testState.apiGet.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.listFallbackTargets(),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            items: [
              expect.objectContaining({
                provider_id: modelDefaultItemPayload.provider_id,
                provider_name: modelDefaultItemPayload.provider_name,
                fallback_provider_id: modelDefaultItemPayload.fallback_provider_id,
                fallback_model_id: modelDefaultItemPayload.fallback_model_id,
              }),
            ],
            total: 1,
          }),
        );
      },
    },
    {
      title: "preserves fallback transport fields for updateFallbackTarget",
      payload: modelDefaultItemPayload,
      arrange: (payload) => {
        testState.apiPut.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.updateFallbackTarget("openai", {
          fallback_provider_id: modelDefaultItemPayload.fallback_provider_id,
          fallback_model_id: modelDefaultItemPayload.fallback_model_id,
        }),
      assertResult: (result) => {
        expect(result).toEqual(
          expect.objectContaining({
            provider_id: modelDefaultItemPayload.provider_id,
            provider_name: modelDefaultItemPayload.provider_name,
            fallback_provider_id: modelDefaultItemPayload.fallback_provider_id,
            fallback_model_id: modelDefaultItemPayload.fallback_model_id,
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
        expect(result).not.toHaveProperty("auto_save");
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
          fallback_enabled: false,
        }),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(appSettingsPayload));
        expect(result).not.toHaveProperty("auto_save");
      },
    },
    {
      title: "parses provider-test connection responses through the canonical shared contract",
      payload: providerTestPayload,
      arrange: (payload) => {
        testState.apiPost.mockResolvedValue(payload);
      },
      invoke: (settingsApi) => settingsApi.testProviderConnection("openai"),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(providerTestPayload));
      },
    },
    {
      title: "parses provider-test credential responses through the canonical shared contract",
      payload: providerTestPayload,
      arrange: (payload) => {
        testState.apiPost.mockResolvedValue(payload);
      },
      invoke: (settingsApi) =>
        settingsApi.testProviderCredentials({
          provider_type: "openai",
          name: "OpenAI",
          api_key_env: "OPENAI_API_KEY",
          base_url: "https://api.openai.com/v1",
        }),
      assertResult: (result) => {
        expect(result).toEqual(expect.objectContaining(providerTestPayload));
      },
    },
  ];

  it.each(contractCases)("$title", async ({ arrange, assertResult, invoke, payload }) => {
    arrange(payload);

    const { settingsApi } = await import("../settings");
    const result = await invoke(settingsApi);

    assertResult(result);
  });

  it("sends provider write requests with embedded identity fields", async () => {
    testState.apiPost.mockResolvedValue(providerItemPayload);
    testState.apiPut.mockResolvedValue(providerItemPayload);

    const { settingsApi } = await import("../settings");
    await settingsApi.createProvider({
      id: "openai",
      kind: "provider",
      name: "OpenAI",
      api_key_env: "OPENAI_API_KEY",
      base_url: "https://api.openai.com/v1",
    });
    await settingsApi.updateProvider("openai", {
      id: "openai",
      kind: "provider",
      is_active: false,
    });

    expect(testState.apiPost).toHaveBeenCalledWith("/settings/providers", {
      id: "openai",
      kind: "provider",
      name: "OpenAI",
      api_key_env: "OPENAI_API_KEY",
      base_url: "https://api.openai.com/v1",
    });
    expect(testState.apiPut).toHaveBeenCalledWith("/settings/providers/openai", {
      id: "openai",
      kind: "provider",
      is_active: false,
    });
  });

  it("sends only fallback_provider_id and fallback_model_id in updateFallbackTarget requests", async () => {
    testState.apiPut.mockResolvedValue(modelDefaultItemPayload);

    const { settingsApi } = await import("../settings");
    await settingsApi.updateFallbackTarget("openai", {
      fallback_provider_id: "anthropic",
      fallback_model_id: "claude-sonnet-4",
    });

    expect(testState.apiPut).toHaveBeenCalledWith("/settings/fallbacks/openai", {
      fallback_provider_id: "anthropic",
      fallback_model_id: "claude-sonnet-4",
    });

    const [, payload] = testState.apiPut.mock.calls.at(-1) ?? [];
    expect(payload).toEqual(
      expect.objectContaining({
        fallback_provider_id: "anthropic",
        fallback_model_id: "claude-sonnet-4",
      }),
    );
    expect(payload).not.toHaveProperty("fallback_chain");
  });

  it("sends only fallback_enabled in updateAppSettings requests", async () => {
    testState.apiPut.mockResolvedValue(appSettingsPayload);

    const { settingsApi } = await import("../settings");
    await settingsApi.updateAppSettings({
      onboarding_completed: true,
      fallback_enabled: false,
    });

    expect(testState.apiPut).toHaveBeenCalledWith("/settings/app", {
      onboarding_completed: true,
      fallback_enabled: false,
    });

    const [, payload] = testState.apiPut.mock.calls.at(-1) ?? [];
    expect(payload).toEqual(
      expect.objectContaining({
        onboarding_completed: true,
        fallback_enabled: false,
      }),
    );
    expect(payload).not.toHaveProperty("fallback_chain_enabled");
  });
});
