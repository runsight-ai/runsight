import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo } from "react";
import { ContextAuditEventV1Schema, type ContextAuditEventV1 } from "@runsight/shared/zod";
import { toast } from "sonner";
import { runsApi, type RunContextAuditParams, type RunQueryParams } from "../api/runs";
import { useContextAuditStore } from "../store/contextAudit";
import { queryKeys } from "./keys";

const PRODUCTION_RUN_SOURCES = new Set(["manual", "webhook", "schedule"]);

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

export function useRunContextAudit(runId: string, params?: Pick<RunContextAuditParams, "page_size" | "node_id">) {
  const replaceRunEvents = useContextAuditStore((state) => state.replaceRunEvents);
  const query = useInfiniteQuery({
    queryKey: [...queryKeys.runs.contextAudit(runId), params],
    queryFn: ({ pageParam }) =>
      runsApi.getRunContextAudit(runId, {
        ...params,
        ...(pageParam ? { cursor: pageParam } : {}),
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.end_cursor ?? undefined,
    enabled: !!runId,
  });

  useEffect(() => {
    if (!runId || !query.data) {
      return;
    }
    const existingEvents = useContextAuditStore.getState().eventsByRun[runId] ?? [];
    replaceRunEvents(
      runId,
      [...query.data.pages.flatMap((page) => page.items), ...existingEvents],
    );
  }, [query.data, replaceRunEvents, runId]);

  return query;
}

export function useRunContextAuditStream(
  runId: string | null | undefined,
  options?: { enabled?: boolean },
): void {
  const appendEvents = useContextAuditStore((state) => state.appendEvents);

  useEffect(() => {
    if (!runId || options?.enabled === false) {
      return;
    }
    const source = new EventSource(`/api/runs/${runId}/stream`);

    source.addEventListener("context_resolution", (event) => {
      const auditEvent = parseContextAuditEvent((event as MessageEvent).data);
      if (auditEvent?.run_id === runId) {
        appendEvents(runId, [auditEvent]);
      }
    });

    source.addEventListener("run_completed", () => source.close());
    source.addEventListener("run_failed", () => source.close());

    return () => source.close();
  }, [appendEvents, options?.enabled, runId]);
}

export function useRunRegressions(runId: string) {
  return useQuery({
    queryKey: queryKeys.runs.regressions(runId),
    queryFn: () => runsApi.getRunRegressions(runId),
    enabled: !!runId,
  });
}

export function useChildRuns(runId: string) {
  return useQuery({
    queryKey: queryKeys.runs.children(runId),
    queryFn: () => runsApi.getChildRuns(runId),
    enabled: !!runId,
  });
}

export function useActiveRuns() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: [
      ...queryKeys.runs.all,
      {
        status: ["running", "pending"],
        source: ["manual", "webhook", "schedule"],
        branch: "main",
      },
    ],
    queryFn: () => {
      const params = new URLSearchParams();
      params.append("status", "running");
      params.append("status", "pending");
      params.append("source", "manual");
      params.append("source", "webhook");
      params.append("source", "schedule");
      params.append("branch", "main");
      return runsApi.listRuns(params);
    },
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const activeRuns = useMemo(
    () =>
      [...(query.data?.items ?? [])]
        .filter((run) => run.branch === "main" && PRODUCTION_RUN_SOURCES.has(run.source))
        .sort((left, right) => {
          const leftPriority = left.status === "running" ? 0 : 1;
          const rightPriority = right.status === "running" ? 0 : 1;

          if (leftPriority !== rightPriority) {
            return leftPriority - rightPriority;
          }

          return right.created_at - left.created_at;
        }),
    [query.data?.items],
  );

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

function parseContextAuditEvent(data: string): ContextAuditEventV1 | null {
  try {
    return ContextAuditEventV1Schema.parse(JSON.parse(data));
  } catch {
    return null;
  }
}
