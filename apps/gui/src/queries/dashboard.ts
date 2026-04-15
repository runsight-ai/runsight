import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "./keys";
import { dashboardApi } from "../api/dashboard";
import { runsApi } from "../api/runs";
import type { DashboardKPIsResponse } from "@runsight/shared/zod";
import type { RunListResponse } from "@runsight/shared/zod";
import type { AttentionItemsResponse } from "@runsight/shared/zod";

export function useDashboardKPIs() {
  return useQuery({
    queryKey: queryKeys.dashboard.kpis,
    queryFn: (): Promise<DashboardKPIsResponse> => dashboardApi.getKPIs(),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useRecentRuns(limit: number = 10) {
  return useQuery({
    queryKey: [...queryKeys.dashboard.recentRuns, limit],
    queryFn: (): Promise<RunListResponse> =>
      runsApi.listRuns({ limit: String(limit), offset: "0" }),
  });
}

export function useAttentionItems(limit?: number) {
  return useQuery({
    queryKey: [...queryKeys.dashboard.attention, limit ?? "default"],
    queryFn: async (): Promise<AttentionItemsResponse> => {
      return dashboardApi.getAttentionItems(limit);
    },
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
