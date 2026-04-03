import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  useQuery: vi.fn((options: Record<string, unknown>) => options),
  useMutation: vi.fn((options: Record<string, unknown>) => options),
  invalidateQueries: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: {
    get: mocks.apiGet,
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: mocks.useQuery,
  useMutation: mocks.useMutation,
  useQueryClient: () => ({ invalidateQueries: mocks.invalidateQueries }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

beforeEach(() => {
  vi.resetModules();
  mocks.apiGet.mockReset();
  mocks.useQuery.mockClear();
  mocks.useMutation.mockClear();
  mocks.invalidateQueries.mockReset();
  mocks.toastSuccess.mockReset();
  mocks.toastError.mockReset();
});

describe("soul data API helpers (RUN-444)", () => {
  it("adds soulsApi.getSoulUsages and calls /souls/:id/usages", async () => {
    mocks.apiGet.mockResolvedValue({
      soul_id: "researcher",
      usages: [{ workflow_id: "wf_1", workflow_name: "Research Flow" }],
      total: 1,
    });

    const { soulsApi } = await import("../../api/souls");
    const getSoulUsages = (soulsApi as Record<string, unknown>).getSoulUsages;

    expect(getSoulUsages).toBeTypeOf("function");

    const result = await (
      getSoulUsages as (id: string) => Promise<{
        soul_id: string;
        usages: Array<{ workflow_id: string; workflow_name: string }>;
        total: number;
      }>
    )("researcher");

    expect(mocks.apiGet).toHaveBeenCalledWith("/souls/researcher/usages");
    expect(result).toEqual({
      soul_id: "researcher",
      usages: [{ workflow_id: "wf_1", workflow_name: "Research Flow" }],
      total: 1,
    });
  });

  it("preserves empty usages as { soul_id, usages: [], total: 0 }", async () => {
    mocks.apiGet.mockResolvedValue({
      soul_id: "researcher",
      usages: [],
      total: 0,
    });

    const { soulsApi } = await import("../../api/souls");
    const getSoulUsages = (soulsApi as Record<string, unknown>).getSoulUsages;

    expect(getSoulUsages).toBeTypeOf("function");

    await expect(
      (getSoulUsages as (id: string) => Promise<unknown>)("researcher"),
    ).resolves.toEqual({
      soul_id: "researcher",
      usages: [],
      total: 0,
    });
  });

  it("surfaces API failures from soulsApi.getSoulUsages", async () => {
    const notFound = new Error("Soul not found");
    mocks.apiGet.mockRejectedValue(notFound);

    const { soulsApi } = await import("../../api/souls");
    const getSoulUsages = (soulsApi as Record<string, unknown>).getSoulUsages;

    expect(getSoulUsages).toBeTypeOf("function");

    await expect(
      (getSoulUsages as (id: string) => Promise<unknown>)("missing"),
    ).rejects.toBe(notFound);
    expect(mocks.apiGet).toHaveBeenCalledWith("/souls/missing/usages");
  });

  it("adds soulsApi.listAvailableTools and calls /tools", async () => {
    mocks.apiGet.mockResolvedValue([
      {
        id: "http",
        name: "HTTP Requests",
        description: "Fetch external APIs.",
        origin: "builtin",
        executor: "native",
      },
      {
        id: "report_lookup",
        name: "Report Lookup",
        description: "Look up saved reports.",
        origin: "custom",
        executor: "request",
      },
    ]);

    const { soulsApi } = await import("../../api/souls");
    const listAvailableTools = (soulsApi as Record<string, unknown>).listAvailableTools;

    expect(listAvailableTools).toBeTypeOf("function");

    const result = await (listAvailableTools as () => Promise<unknown[]>)();

    expect(mocks.apiGet).toHaveBeenCalledWith("/tools");
    expect(result).toEqual([
      expect.objectContaining({ id: "http", origin: "builtin", executor: "native" }),
      expect.objectContaining({
        id: "report_lookup",
        origin: "custom",
        executor: "request",
      }),
    ]);
  });

  it("adds settingsApi.listModelProviders and calls /models/providers", async () => {
    mocks.apiGet.mockResolvedValue([
      { id: "openai", name: "OpenAI", model_count: 12, is_configured: true },
      { id: "anthropic", name: "Anthropic", model_count: 5, is_configured: false },
    ]);

    const { settingsApi } = await import("../../api/settings");
    const listModelProviders = (settingsApi as Record<string, unknown>).listModelProviders;

    expect(listModelProviders).toBeTypeOf("function");

    const result = await (
      listModelProviders as () => Promise<
        Array<{ id: string; name: string; model_count: number; is_configured: boolean }>
      >
    )();

    expect(mocks.apiGet).toHaveBeenCalledWith("/models/providers");
    expect(result).toEqual([
      { id: "openai", name: "OpenAI", model_count: 12, is_configured: true },
      { id: "anthropic", name: "Anthropic", model_count: 5, is_configured: false },
    ]);
  });

  it("adds settingsApi.listModelsForProvider and calls /models?provider=...", async () => {
    mocks.apiGet.mockResolvedValue([
      {
        provider: "openai",
        provider_name: "OpenAI",
        model_id: "gpt-4o",
        mode: "chat",
        max_tokens: 128000,
        input_cost_per_token: 0.000005,
        output_cost_per_token: 0.000015,
        supports_vision: true,
        supports_function_calling: true,
      },
    ]);

    const { settingsApi } = await import("../../api/settings");
    const listModelsForProvider = (settingsApi as Record<string, unknown>).listModelsForProvider;

    expect(listModelsForProvider).toBeTypeOf("function");

    const result = await (
      listModelsForProvider as (provider: string) => Promise<unknown[]>
    )("openai");

    expect(mocks.apiGet).toHaveBeenCalledWith("/models?provider=openai");
    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual([
      expect.objectContaining({
        provider: "openai",
        model_id: "gpt-4o",
      }),
    ]);
  });
});

describe("soul data query keys (RUN-444)", () => {
  it("adds queryKeys.souls.usages(id)", async () => {
    const { queryKeys } = await import("../keys");
    const usagesKey = (queryKeys.souls as Record<string, unknown>).usages;

    expect(usagesKey).toBeTypeOf("function");

    const key = (usagesKey as (id: string) => readonly string[])("researcher");

    expect(key).toEqual(expect.arrayContaining(["souls", "researcher", "usages"]));
  });

  it("adds queryKeys.souls.tools for the shared tool catalog", async () => {
    const { queryKeys } = await import("../keys");

    expect((queryKeys.souls as Record<string, unknown>).tools).toEqual(
      expect.arrayContaining(["souls", "tools"]),
    );
  });

  it("adds queryKeys.models.providers and queryKeys.models.byProvider(provider)", async () => {
    const { queryKeys } = await import("../keys");
    const models = (queryKeys as Record<string, unknown>).models as Record<string, unknown>;

    expect(models).toBeTypeOf("object");
    expect(models.providers).toEqual(expect.arrayContaining(["models", "providers"]));
    expect(models.byProvider).toBeTypeOf("function");
    expect((models.byProvider as (provider: string) => readonly string[])("openai")).toEqual(
      expect.arrayContaining(["models", "openai"]),
    );
  });
});

describe("soul data query hooks (RUN-444)", () => {
  it("adds useSoulUsages and wires useQuery to soulsApi.getSoulUsages", async () => {
    const { useSoulUsages } = await import("../souls");
    const { queryKeys } = await import("../keys");

    expect(useSoulUsages).toBeTypeOf("function");

    const query = (
      useSoulUsages as unknown as (id: string | undefined) => {
        queryKey: readonly string[];
        queryFn: () => Promise<unknown>;
        enabled: boolean;
      }
    )("researcher");

    expect(mocks.useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: queryKeys.souls.usages("researcher"),
        enabled: true,
      }),
    );

    mocks.apiGet.mockResolvedValue({
      soul_id: "researcher",
      usages: [],
      total: 0,
    });

    await query.queryFn();
    expect(mocks.apiGet).toHaveBeenCalledWith("/souls/researcher/usages");
  });

  it("adds useAvailableTools and wires useQuery to /tools", async () => {
    const { useAvailableTools } = await import("../souls");
    const { queryKeys } = await import("../keys");

    expect(useAvailableTools).toBeTypeOf("function");

    const query = (
      useAvailableTools as unknown as () => {
        queryKey: readonly string[];
        queryFn: () => Promise<unknown>;
      }
    )();

    expect(mocks.useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: queryKeys.souls.tools,
      }),
    );

    mocks.apiGet.mockResolvedValue([]);

    await query.queryFn();
    expect(mocks.apiGet).toHaveBeenCalledWith("/tools");
  });

  it("adds useModelProviders and wires useQuery to /models/providers", async () => {
    const { useModelProviders } = await import("../settings");
    const { queryKeys } = await import("../keys");

    expect(useModelProviders).toBeTypeOf("function");

    const query = (
      useModelProviders as unknown as () => {
        queryKey: readonly string[];
        queryFn: () => Promise<unknown>;
      }
    )();

    expect(mocks.useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: queryKeys.models.providers,
      }),
    );

    mocks.apiGet.mockResolvedValue([]);

    await query.queryFn();
    expect(mocks.apiGet).toHaveBeenCalledWith("/models/providers");
  });

  it("adds useModelsForProvider and disables the query when provider is null", async () => {
    const { useModelsForProvider } = await import("../settings");

    expect(useModelsForProvider).toBeTypeOf("function");

    const disabledQuery = (
      useModelsForProvider as unknown as (provider: string | null) => {
        queryKey: readonly unknown[];
        enabled: boolean;
      }
    )(null);

    expect(mocks.useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        enabled: false,
      }),
    );
    expect(disabledQuery.queryKey).toEqual(expect.arrayContaining(["models"]));
    expect(disabledQuery.enabled).toBe(false);
  });

  it("uses the provider value in the query key and request path when enabled", async () => {
    const { useModelsForProvider } = await import("../settings");
    const { queryKeys } = await import("../keys");

    expect(useModelsForProvider).toBeTypeOf("function");

    const query = (
      useModelsForProvider as unknown as (provider: string | null) => {
        queryKey: readonly string[];
        queryFn: () => Promise<unknown>;
        enabled: boolean;
      }
    )("openai");

    expect(mocks.useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: queryKeys.models.byProvider("openai"),
        enabled: true,
      }),
    );

    mocks.apiGet.mockResolvedValue([]);

    await query.queryFn();
    expect(mocks.apiGet).toHaveBeenCalledWith("/models?provider=openai");
  });
});
