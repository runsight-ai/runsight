import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "./keys";
import { api } from "../api/client";
import type { DashboardKPIsResponse } from "../types/generated/zod";
import type { RunResponse } from "../types/generated/zod";
import { DashboardKPIsResponseSchema } from "../types/generated/zod";

export function useDashboardKPIs() {
  return useQuery({
    queryKey: queryKeys.dashboard.kpis,
    queryFn: async (): Promise<DashboardKPIsResponse> => {
      const res = await api.get("/dashboard");
      return DashboardKPIsResponseSchema.parse(res);
    },
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
