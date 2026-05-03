import type { settingsApi as SettingsApi } from "../settings";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  id: "fixture-primary",
  name: "Fixture Primary",
  type: "fixture-primary",
  status: "connected",
  api_key_env: "FIXTURE_PROVIDER_CREDENTIAL",
  api_key_preview: "test-key...abcd",
  base_url: "http://localhost/v1",
  models: ["fixture-chat-model"],
  model_count: 1,
  is_configured: true,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-02T00:00:00Z",
};

const modelDefaultItemPayload = {
  id: "fixture-primary",
  provider_id: "fixture-primary",
  provider_name: "Fixture Primary",
  model_name: "fixture-chat-model",
  is_default: true,
  fallback_provider_id: "fixture-backup",
  fallback_model_id: "fixture-backup-model",
};

const appSettingsPayload = {
  base_path: "/workspace",
  onboarding_completed: true,
  fallback_enabled: false,
};

const providerTestPayload = {
  success: true,
  message: "Connection successful",
  models: ["fixture-chat-model", "fixture-small-model"],
  model_count: 2,
  latency_ms: 123.4,
};

describe("settings API transport contracts", () => {
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
      invoke: (settingsApi) => settingsApi.getProvider("fixture-primary"),
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
          id: "fixture-primary",
          kind: "provider",
          name: "Fixture Primary",
          api_key_env: "FIXTURE_PROVIDER_CREDENTIAL",
          base_url: "http://localhost/v1",
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
        settingsApi.updateProvider("fixture-primary", {
          id: "fixture-primary",
          kind: "provider",
          name: "Fixture Primary",
          api_key_env: "FIXTURE_PROVIDER_CREDENTIAL",
          base_url: "http://localhost/v1",
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
        settingsApi.updateFallbackTarget("fixture-primary", {
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
      invoke: (settingsApi) => settingsApi.testProviderConnection("fixture-primary"),
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
          provider_type: "fixture-primary",
          name: "Fixture Primary",
          api_key_env: "FIXTURE_PROVIDER_CREDENTIAL",
          base_url: "http://localhost/v1",
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
      id: "fixture-primary",
      kind: "provider",
      name: "Fixture Primary",
      api_key_env: "FIXTURE_PROVIDER_CREDENTIAL",
      base_url: "http://localhost/v1",
    });
    await settingsApi.updateProvider("fixture-primary", {
      id: "fixture-primary",
      kind: "provider",
      is_active: false,
    });

    expect(testState.apiPost).toHaveBeenCalledWith("/settings/providers", {
      id: "fixture-primary",
      kind: "provider",
      name: "Fixture Primary",
      api_key_env: "FIXTURE_PROVIDER_CREDENTIAL",
      base_url: "http://localhost/v1",
    });
    expect(testState.apiPut).toHaveBeenCalledWith("/settings/providers/fixture-primary", {
      id: "fixture-primary",
      kind: "provider",
      is_active: false,
    });
  });

  it("sends only fallback_provider_id and fallback_model_id in updateFallbackTarget requests", async () => {
    testState.apiPut.mockResolvedValue(modelDefaultItemPayload);

    const { settingsApi } = await import("../settings");
    await settingsApi.updateFallbackTarget("fixture-primary", {
      fallback_provider_id: "fixture-backup",
      fallback_model_id: "fixture-backup-model",
    });

    expect(testState.apiPut).toHaveBeenCalledWith("/settings/fallbacks/fixture-primary", {
      fallback_provider_id: "fixture-backup",
      fallback_model_id: "fixture-backup-model",
    });
    expect(testState.apiPut.mock.calls.at(-1)?.[1]).not.toHaveProperty("fallback_chain");
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
    expect(testState.apiPut.mock.calls.at(-1)?.[1]).not.toHaveProperty(
      "fallback_chain_enabled",
    );
  });
});
