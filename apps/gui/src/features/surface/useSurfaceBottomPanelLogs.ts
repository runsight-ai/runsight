import { useEffect, useMemo, useRef, useState } from "react";

import { type RunLogResponse } from "@/api/runs";
import { useRunLogs } from "@/queries/runs";
import { useCanvasStore } from "@/store/canvas";

import { mapSSEEventToStoreAction } from "./useRunStream";

export interface SurfaceBottomPanelLogEntry {
  timestamp: string;
  level: string;
  message: string;
  dedupeKey?: string;
  origin?: "live" | "replay";
}

type TimestampLike = string | number;

type UseSurfaceBottomPanelLogsParams = {
  runId: string | undefined;
};

type StreamEventType =
  | "log_entry"
  | "replay"
  | "node_started"
  | "node_completed"
  | "node_failed"
  | "run_completed"
  | "run_failed";

const STREAM_EVENT_TYPES: StreamEventType[] = [
  "log_entry",
  "replay",
  "node_started",
  "node_completed",
  "node_failed",
  "run_completed",
  "run_failed",
];

export function useSurfaceBottomPanelLogs({ runId }: UseSurfaceBottomPanelLogsParams) {
  const [liveEntries, setLiveEntries] = useState<SurfaceBottomPanelLogEntry[]>([]);
  const hasFetchedHistoryRef = useRef(false);
  const nextTransientLogKeyRef = useRef(0);
  const setNodeStatus = useCanvasStore((state) => state.setNodeStatus);
  const setActiveRunId = useCanvasStore((state) => state.setActiveRunId);
  const setRunCost = useCanvasStore((state) => state.setRunCost);
  const { data: logData } = useRunLogs(runId ?? "", undefined, {
    refetchInterval: undefined,
  });

  useEffect(() => {
    hasFetchedHistoryRef.current =
      typeof logData?.total === "number" &&
      logData.total > 0 &&
      (logData.items?.length ?? 0) >= logData.total;
  }, [logData?.items, logData?.total]);

  useEffect(() => {
    nextTransientLogKeyRef.current = 0;
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
          const normalizedEntry = withOrigin(normalizeLogEntry(data as RunLogResponse), "live");
          appendEntry(normalizedEntry);
          return;
        }

        if (eventType === "replay") {
          if (hasFetchedHistoryRef.current) {
            return;
          }
          const replayEntry = replayEventToLogEntry(
            data,
            `replay:${runId}:${nextTransientLogKeyRef.current++}`,
          );
          if (replayEntry) {
            appendEntry(replayEntry);
          }
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

        const logEntry = sseEventToLogEntry(
          eventType,
          data,
          `live:${runId}:${nextTransientLogKeyRef.current++}`,
        );
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
  dedupeSeed: string,
): SurfaceBottomPanelLogEntry | null {
  const timestamp = new Date().toISOString();

  switch (eventType) {
    case "node_started":
      return {
        timestamp,
        level: "info",
        message: `Node ${data.node_id as string} started`,
        dedupeKey: `${dedupeSeed}|block_start|${String(data.node_id ?? "")}`,
        origin: "live",
      };
    case "node_completed":
      return {
        timestamp,
        level: "info",
        message: `Node ${data.node_id as string} completed${data.cost_usd != null ? ` ($${(data.cost_usd as number).toFixed(4)})` : ""}`,
        dedupeKey: `${dedupeSeed}|block_complete|${String(data.node_id ?? "")}`,
        origin: "live",
      };
    case "node_failed":
      return {
        timestamp,
        level: "error",
        message: `Node ${data.node_id as string} failed: ${(data.error as string) ?? "unknown error"}`,
        dedupeKey: `${dedupeSeed}|block_error|${String(data.node_id ?? "")}|${String(data.error ?? "")}`,
        origin: "live",
      };
    case "run_completed":
      return {
        timestamp,
        level: "info",
        message: `Run completed. Total cost: $${((data.total_cost_usd as number) ?? 0).toFixed(4)}`,
        dedupeKey: `${dedupeSeed}|workflow_complete`,
        origin: "live",
      };
    case "run_failed":
      return {
        timestamp,
        level: "error",
        message: `Run failed: ${(data.error as string) ?? "unknown error"}`,
        dedupeKey: `${dedupeSeed}|workflow_error|${String(data.error ?? "")}`,
        origin: "live",
      };
    default:
      return null;
  }
}

function replayEventToLogEntry(
  payload: Record<string, unknown>,
  dedupeSeed?: string,
): SurfaceBottomPanelLogEntry | null {
  if (
    isTimestampLike(payload.timestamp) &&
    typeof payload.level === "string" &&
    typeof payload.message === "string"
  ) {
    return withOrigin(
      {
        ...normalizeLogEntry(payload as RunLogResponse),
        dedupeKey:
          logIdDedupeKey(payload.id) ??
          `${normalizeTimestamp(payload.timestamp)}|${payload.level}|${payload.message}`,
      },
      "replay",
    );
  }

  const event = eventTypeFromPayload(payload);
  const timestamp = resolveTimestamp(payload.timestamp);
  if (!event) {
    return null;
  }

  switch (event) {
    case "workflow_start":
      return {
        timestamp,
        level: "info",
        message: `Workflow ${(payload.workflow_name as string) ?? "run"} started`,
        dedupeKey: structuredEventDedupeKey(payload, timestamp) ?? dedupeSeed,
        origin: "replay",
      };
    case "block_start":
      return {
        timestamp,
        level: "info",
        message: `Node ${(payload.block_id as string) ?? "unknown"} started`,
        dedupeKey: structuredEventDedupeKey(payload, timestamp) ?? dedupeSeed,
        origin: "replay",
      };
    case "block_complete":
      return {
        timestamp,
        level: "info",
        message: `Node ${(payload.block_id as string) ?? "unknown"} completed`,
        dedupeKey: structuredEventDedupeKey(payload, timestamp) ?? dedupeSeed,
        origin: "replay",
      };
    case "block_error":
      return {
        timestamp,
        level: "error",
        message: `Node ${(payload.block_id as string) ?? "unknown"} failed: ${(payload.error as string) ?? "unknown error"}`,
        dedupeKey: structuredEventDedupeKey(payload, timestamp) ?? dedupeSeed,
        origin: "replay",
      };
    case "workflow_complete":
      return {
        timestamp,
        level: "info",
        message: "Run completed.",
        dedupeKey: structuredEventDedupeKey(payload, timestamp) ?? dedupeSeed,
        origin: "replay",
      };
    case "workflow_error":
      return {
        timestamp,
        level: "error",
        message: `Run failed: ${(payload.error as string) ?? "unknown error"}`,
        dedupeKey: structuredEventDedupeKey(payload, timestamp) ?? dedupeSeed,
        origin: "replay",
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

type NormalizableLogEntry = {
  id?: number;
  timestamp: TimestampLike;
  level: string;
  message: string;
  dedupeKey?: string;
  origin?: SurfaceBottomPanelLogEntry["origin"];
};

function normalizeLogEntry(
  entry: NormalizableLogEntry,
): SurfaceBottomPanelLogEntry {
  const timestamp = normalizeTimestamp(entry.timestamp);
  const payload = parseStructuredLogPayload(entry.message);
  const existingDedupeKey = entry.dedupeKey;
  const existingOrigin = entry.origin;
  const logIdKey = logIdDedupeKey(entry.id);

  if (payload) {
    if (
      isTimestampLike(payload.timestamp) &&
      typeof payload.level === "string" &&
      typeof payload.message === "string"
    ) {
      return {
        timestamp: normalizeTimestamp(payload.timestamp),
        level: payload.level,
        message: payload.message,
        dedupeKey:
          existingDedupeKey ??
          logIdKey ??
          `${normalizeTimestamp(payload.timestamp)}|${payload.level}|${payload.message}`,
        origin: existingOrigin,
      };
    }

    const structuredReplayEntry = replayEventToLogEntry({ ...payload, timestamp });
    if (structuredReplayEntry) {
      return {
        ...structuredReplayEntry,
        timestamp,
        dedupeKey:
          existingDedupeKey ??
          logIdKey ??
          structuredEventDedupeKey(payload, timestamp) ??
          `${timestamp}|${entry.level}|${entry.message}`,
        origin: existingOrigin ?? structuredReplayEntry.origin,
      };
    }
  }

  return {
    timestamp,
    level: entry.level,
    message: entry.message,
    dedupeKey: existingDedupeKey ?? historyDedupeKey(entry),
    origin: existingOrigin,
  };
}

function withOrigin(
  entry: SurfaceBottomPanelLogEntry,
  origin: SurfaceBottomPanelLogEntry["origin"],
): SurfaceBottomPanelLogEntry {
  return {
    ...entry,
    origin,
  };
}

function logEntryKey(entry: SurfaceBottomPanelLogEntry) {
  return entry.dedupeKey ?? `${entry.timestamp}|${entry.level}|${entry.message}`;
}

function historyDedupeKey(
  entry: Pick<NormalizableLogEntry, "id" | "timestamp" | "level" | "message">,
): string {
  const logIdKey = logIdDedupeKey(entry.id);
  if (logIdKey) {
    return logIdKey;
  }

  const timestamp = normalizeTimestamp(entry.timestamp);
  const payload = parseStructuredLogPayload(entry.message);
  if (payload) {
    const key = structuredEventDedupeKey(payload, timestamp);
    if (key) {
      return key;
    }
  }
  return `${timestamp}|${entry.level}|${entry.message}`;
}

function parseStructuredLogPayload(message: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(message);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function normalizeTimestamp(timestamp: TimestampLike): string {
  return typeof timestamp === "string" ? timestamp : new Date(timestamp).toISOString();
}

function resolveTimestamp(timestamp: unknown): string {
  return isTimestampLike(timestamp) ? normalizeTimestamp(timestamp) : new Date().toISOString();
}

function isTimestampLike(timestamp: unknown): timestamp is TimestampLike {
  return typeof timestamp === "string" || typeof timestamp === "number";
}

function logIdDedupeKey(id: unknown): string | null {
  return typeof id === "number" ? `log:${id}` : null;
}

function eventTypeFromPayload(payload: Record<string, unknown>): string | null {
  return typeof payload.event === "string" ? payload.event : null;
}

function structuredEventDedupeKey(
  payload: Record<string, unknown>,
  fallbackTimestamp?: string,
): string | null {
  const logIdKey = logIdDedupeKey(payload.id);
  if (logIdKey) {
    return logIdKey;
  }

  if (
    isTimestampLike(payload.timestamp) &&
    typeof payload.level === "string" &&
    typeof payload.message === "string"
  ) {
    return `${normalizeTimestamp(payload.timestamp)}|${payload.level}|${payload.message}`;
  }

  const event = eventTypeFromPayload(payload);
  if (!event) {
    return null;
  }
  const timestamp = isTimestampLike(payload.timestamp)
    ? normalizeTimestamp(payload.timestamp)
    : fallbackTimestamp;
  if (!timestamp) {
    return null;
  }

  switch (event) {
    case "workflow_start":
      return `${timestamp}|workflow_start|${String(payload.workflow_name ?? "")}`;
    case "block_start":
      return `${timestamp}|block_start|${String(payload.block_id ?? "")}`;
    case "block_complete":
      return `${timestamp}|block_complete|${String(payload.block_id ?? "")}`;
    case "block_error":
      return `${timestamp}|block_error|${String(payload.block_id ?? "")}|${String(payload.error ?? "")}`;
    case "workflow_complete":
      return `${timestamp}|workflow_complete`;
    case "workflow_error":
      return `${timestamp}|workflow_error|${String(payload.error ?? "")}`;
    default:
      return null;
  }
}
