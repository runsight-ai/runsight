import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "./keys";
import { api } from "../api/client";
import { dashboardApi } from "../api/dashboard";
import type { DashboardKPIsResponse } from "@runsight/shared/zod";
import type { RunResponse } from "@runsight/shared/zod";
import {
  DashboardKPIsResponseSchema,
} from "@runsight/shared/zod";
import type { AttentionItemsResponse } from "@runsight/shared/zod";

export function useDashboardKPIs() {
  return useQuery({
    queryKey: queryKeys.dashboard.kpis,
    queryFn: async (): Promise<DashboardKPIsResponse> => {
      const res = await api.get("/dashboard");
      return DashboardKPIsResponseSchema.parse(res);
    },
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useRecentRuns(limit: number = 10) {
  return useQuery({
    queryKey: [...queryKeys.dashboard.recentRuns, limit],
    queryFn: async (): Promise<{ items: RunResponse[]; total: number }> => {
      const res = await api.get<{ items: RunResponse[]; total: number }>(
        `/runs?limit=${limit}&offset=0`,
      );
      return res;
    },
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
