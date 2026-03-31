import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { toast } from "sonner";
import { runsApi, type RunQueryParams } from "../api/runs";
import { queryKeys } from "./keys";

export function useRuns(
  params?: RunQueryParams,
  options?: { refetchInterval?: number | false }
) {
  return useQuery({
    queryKey: [...queryKeys.runs.all, params],
    queryFn: () => runsApi.listRuns(params),
    refetchInterval: options?.refetchInterval,
  });
}

export function useRun(
  id: string,
  options?: {
    refetchInterval?:
      | number
      | false
      | ((query: { state: { dataUpdatedAt: number } }) => number | false | undefined);
  }
) {
  return useQuery({
    queryKey: queryKeys.runs.detail(id),
    queryFn: () => runsApi.getRun(id),
    enabled: !!id,
    refetchInterval: options?.refetchInterval,
  });
}

export function useCreateRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: runsApi.createRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
      toast.success("Run started");
    },
    onError: (error: Error) => {
      toast.error("Failed to start run", { description: error.message });
    },
  });
}

export function useCancelRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: runsApi.cancelRun,
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
      toast.success("Run cancelled");
    },
    onError: (error: Error) => {
      toast.error("Failed to cancel run", { description: error.message });
    },
  });
}

export function useDeleteRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: runsApi.deleteRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
      toast.success("Run deleted");
    },
    onError: (error: Error) => {
      toast.error("Failed to delete run", { description: error.message });
    },
  });
}

export function useRunNodes(id: string) {
  return useQuery({
    // Using a derived query key for nodes
    queryKey: [...queryKeys.runs.detail(id), "nodes"],
    queryFn: () => runsApi.getRunNodes(id),
    enabled: !!id,
  });
}

export function useRunLogs(id: string, params?: Record<string, string>, options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: [...queryKeys.runs.logs(id), params],
    queryFn: () => runsApi.getRunLogs(id, params),
    enabled: !!id,
    refetchInterval: options?.refetchInterval,
  });
}

export function useActiveRuns() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: [...queryKeys.runs.all, { status: ["running", "pending"] }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.append("status", "running");
      params.append("status", "pending");
      return runsApi.listRuns(params);
    },
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const activeRuns = useMemo(() => query.data?.items ?? [], [query.data?.items]);

  // SSE: subscribe to each active run's stream for real-time updates
  // Connect EventSource to /api/runs/${run.id}/stream for each active run
  // Handle run_completed and run_failed events to remove run from active list
  // Update cost from SSE node_completed events
  const subscribeToRunStream = useCallback(
    function subscribeToRunStream(runId: string) {
      const url = `/api/runs/${runId}/stream`;
      const eventSource = new EventSource(url);

      eventSource.addEventListener("run_completed", () => {
        queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
      });

      eventSource.addEventListener("run_failed", () => {
        queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
      });

      eventSource.addEventListener("node_completed", (event) => {
        const data = JSON.parse(event.data);
        if (data.cost_usd != null) {
          queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
        }
      });

      return eventSource;
    },
    [queryClient],
  );

  return { ...query, activeRuns, subscribeToRunStream };
}
