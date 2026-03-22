import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { runsApi } from "../api/runs";
import { queryKeys } from "./keys";

export function useRuns(
  params?: Record<string, string>,
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
