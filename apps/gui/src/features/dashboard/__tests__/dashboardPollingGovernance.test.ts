import { beforeEach, describe, expect, it, vi } from "vitest";

const queryMock = vi.hoisted(() => ({
  useQuery: vi.fn(),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: queryMock.useQuery,
}));

beforeEach(() => {
  vi.resetModules();
  queryMock.useQuery.mockReset();
  queryMock.useQuery.mockReturnValue({ data: undefined });
});

describe("dashboard polling smoke", () => {
  it("keeps KPI refresh in React Query with background polling disabled", async () => {
    const { useDashboardKPIs } = await import("@/queries/dashboard");

    useDashboardKPIs();

    expect(queryMock.useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        refetchInterval: 30_000,
        refetchIntervalInBackground: false,
      }),
    );
  });
});
