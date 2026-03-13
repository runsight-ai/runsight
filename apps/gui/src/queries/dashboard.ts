import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "./keys";
import { api } from "../api/client";
import type { RunResponse } from "../types/schemas/runs";

export interface DashboardSummary {
  total_runs: number;
  active_runs: number;
  total_cost_usd: number;
  completed_runs: number;
  failed_runs: number;
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: queryKeys.dashboard.summary,
    queryFn: async (): Promise<DashboardSummary> => {
      const res = await api.get<{
        active_runs: number;
        completed_runs: number;
        total_cost_usd: number;
        recent_errors: number;
      }>("/dashboard");
      return {
        total_runs: res.active_runs + res.completed_runs + res.recent_errors,
        active_runs: res.active_runs,
        total_cost_usd: res.total_cost_usd,
        completed_runs: res.completed_runs,
        failed_runs: res.recent_errors,
      };
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
