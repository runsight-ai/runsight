import { useEffect, useMemo, useState } from "react";

import { type RunLogResponse } from "@/api/runs";
import { useRunLogs } from "@/queries/runs";
import { useCanvasStore } from "@/store/canvas";

import { mapSSEEventToStoreAction } from "./useRunStream";

export interface SurfaceBottomPanelLogEntry {
  timestamp: string;
  level: string;
  message: string;
}

type UseSurfaceBottomPanelLogsParams = {
  runId: string | undefined;
};

type StreamEventType =
  | "log_entry"
  | "node_started"
  | "node_completed"
  | "node_failed"
  | "run_completed"
  | "run_failed";

const STREAM_EVENT_TYPES: StreamEventType[] = [
  "log_entry",
  "node_started",
  "node_completed",
  "node_failed",
  "run_completed",
  "run_failed",
];

export function useSurfaceBottomPanelLogs({ runId }: UseSurfaceBottomPanelLogsParams) {
  const [liveEntries, setLiveEntries] = useState<SurfaceBottomPanelLogEntry[]>([]);
  const setNodeStatus = useCanvasStore((state) => state.setNodeStatus);
  const setActiveRunId = useCanvasStore((state) => state.setActiveRunId);
  const setRunCost = useCanvasStore((state) => state.setRunCost);
  const { data: logData } = useRunLogs(runId ?? "", undefined, {
    refetchInterval: undefined,
  });

  useEffect(() => {
    setLiveEntries([]);
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      return;
    }

    let disposed = false;
    const source = new EventSource(`/api/runs/${runId}/stream`);

    const appendEntry = (entry: SurfaceBottomPanelLogEntry) => {
      if (disposed) {
        return;
      }
      setLiveEntries((previous) => appendUniqueEntry(previous, entry));
    };

    for (const eventType of STREAM_EVENT_TYPES) {
      source.addEventListener(eventType, (event) => {
        if (disposed) {
          return;
        }

        const data = JSON.parse((event as MessageEvent).data) as Record<string, unknown>;

        if (eventType === "log_entry") {
          const normalizedEntry = normalizeLogEntry(data as RunLogResponse);
          appendEntry(normalizedEntry);
          return;
        }

        const storeAction = mapSSEEventToStoreAction(eventType, data);
        if (storeAction) {
          switch (storeAction.action) {
            case "setNodeStatus":
              setNodeStatus(storeAction.nodeId, storeAction.status);
              break;
            case "runCompleted":
              setRunCost(storeAction.totalCost);
              setActiveRunId(null);
              break;
            case "runFailed":
              setActiveRunId(null);
              break;
          }
        }

        const logEntry = sseEventToLogEntry(eventType, data);
        if (logEntry) {
          appendEntry(logEntry);
        }

        if (eventType === "run_completed" || eventType === "run_failed") {
          source.close();
        }
      });
    }

    return () => {
      disposed = true;
      source.close();
    };
  }, [runId, setActiveRunId, setNodeStatus, setRunCost]);

  const entries = useMemo(
    () => mergeLogEntries(logData?.items ?? [], liveEntries),
    [liveEntries, logData?.items],
  );

  return {
    entries,
  };
}

function sseEventToLogEntry(
  eventType: StreamEventType,
  data: Record<string, unknown>,
): SurfaceBottomPanelLogEntry | null {
  const timestamp = new Date().toISOString();

  switch (eventType) {
    case "node_started":
      return {
        timestamp,
        level: "info",
        message: `Node ${data.node_id as string} started`,
      };
    case "node_completed":
      return {
        timestamp,
        level: "info",
        message: `Node ${data.node_id as string} completed${data.cost_usd != null ? ` ($${(data.cost_usd as number).toFixed(4)})` : ""}`,
      };
    case "node_failed":
      return {
        timestamp,
        level: "error",
        message: `Node ${data.node_id as string} failed: ${(data.error as string) ?? "unknown error"}`,
      };
    case "run_completed":
      return {
        timestamp,
        level: "info",
        message: `Run completed. Total cost: $${((data.total_cost_usd as number) ?? 0).toFixed(4)}`,
      };
    case "run_failed":
      return {
        timestamp,
        level: "error",
        message: `Run failed: ${(data.error as string) ?? "unknown error"}`,
      };
    default:
      return null;
  }
}

function mergeLogEntries(
  replayedEntries: RunLogResponse[],
  liveEntries: SurfaceBottomPanelLogEntry[],
): SurfaceBottomPanelLogEntry[] {
  const merged: SurfaceBottomPanelLogEntry[] = [];
  const seenKeys = new Set<string>();

  for (const entry of [...replayedEntries, ...liveEntries]) {
    const normalizedEntry = normalizeLogEntry(entry);
    const key = logEntryKey(normalizedEntry);
    if (seenKeys.has(key)) {
      continue;
    }
    seenKeys.add(key);
    merged.push(normalizedEntry);
  }

  return merged;
}

function appendUniqueEntry(
  previousEntries: SurfaceBottomPanelLogEntry[],
  nextEntry: SurfaceBottomPanelLogEntry,
) {
  const nextKey = logEntryKey(nextEntry);
  if (previousEntries.some((entry) => logEntryKey(entry) === nextKey)) {
    return previousEntries;
  }
  return [...previousEntries, nextEntry];
}

function normalizeLogEntry(
  entry: Pick<RunLogResponse, "timestamp" | "level" | "message">,
): SurfaceBottomPanelLogEntry {
  return {
    timestamp:
      typeof entry.timestamp === "string"
        ? entry.timestamp
        : new Date(entry.timestamp).toISOString(),
    level: entry.level,
    message: entry.message,
  };
}

function logEntryKey(entry: SurfaceBottomPanelLogEntry) {
  return `${entry.timestamp}|${entry.level}|${entry.message}`;
}
