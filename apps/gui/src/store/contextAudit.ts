import { create } from "zustand";
import type { ContextAuditEventV1 } from "@runsight/shared/zod";

export type ContextAuditTableRow = {
  id: string;
  runId: string;
  nodeId: string;
  inputName: string | null;
  fromRef: string | null;
  status: string;
  severity: string;
  internal: boolean;
};

export type ContextAuditEdgeInput = {
  id: string;
  runId: string;
  source: string;
  target: string;
  inputName: string | null;
  namespace: string | null;
};

type ContextAuditState = {
  activeRunId: string | null;
  eventsByRun: Record<string, ContextAuditEventV1[]>;
  replaceRunEvents: (runId: string, events: ContextAuditEventV1[]) => void;
  appendEvents: (runId: string, events: ContextAuditEventV1[]) => void;
  clearRun: (runId: string) => void;
};

export const useContextAuditStore = create<ContextAuditState>((set, get) => ({
  activeRunId: null,
  eventsByRun: {},

  replaceRunEvents: (runId, events) => {
    set({
      activeRunId: runId,
      eventsByRun: {
        [runId]: normalizeEvents(runId, events),
      },
    });
  },

  appendEvents: (runId, events) => {
    const state = get();
    if (state.activeRunId !== null && state.activeRunId !== runId) {
      return;
    }
    const current = state.eventsByRun[runId] ?? [];
    set({
      activeRunId: runId,
      eventsByRun: {
        ...state.eventsByRun,
        [runId]: normalizeEvents(runId, [...current, ...events]),
      },
    });
  },

  clearRun: (runId) => {
    const { [runId]: _removed, ...remaining } = get().eventsByRun;
    set({
      activeRunId: get().activeRunId === runId ? null : get().activeRunId,
      eventsByRun: remaining,
    });
  },
}));

export const selectRunEvents =
  (runId: string) =>
  (state: ContextAuditState): ContextAuditEventV1[] =>
    state.eventsByRun[runId] ?? [];

export const selectNodeEvents =
  (runId: string, nodeId: string) =>
  (state: ContextAuditState): ContextAuditEventV1[] =>
    selectRunEvents(runId)(state).filter((event) => event.node_id === nodeId);

export const selectRunSummary = (runId: string) => (state: ContextAuditState) => {
  const events = selectRunEvents(runId)(state);
  return {
    totalEvents: events.length,
    resolvedCount: events.reduce((total, event) => total + (event.resolved_count ?? 0), 0),
    deniedCount: events.reduce((total, event) => total + (event.denied_count ?? 0), 0),
    warningCount: events.reduce((total, event) => total + (event.warning_count ?? 0), 0),
  };
};

export const selectNodeSummary =
  (runId: string, nodeId: string) => (state: ContextAuditState) => {
    const events = selectNodeEvents(runId, nodeId)(state);
    return {
      totalEvents: events.length,
      inputCount: events.reduce((total, event) => total + (event.records?.length ?? 0), 0),
      warningCount: events.reduce((total, event) => total + (event.warning_count ?? 0), 0),
    };
  };

export const selectContextAuditRows =
  (runId: string) =>
  (state: ContextAuditState): ContextAuditTableRow[] =>
    selectRunEvents(runId)(state).flatMap((event) =>
      (event.records ?? []).map((record, index) => ({
        id: `${eventKey(event)}:${index}`,
        runId: event.run_id,
        nodeId: event.node_id,
        inputName: record.input_name ?? null,
        fromRef: record.from_ref ?? null,
        status: record.status,
        severity: record.severity,
        internal: record.internal ?? false,
      })),
    );

export const selectContextAuditEdges =
  (runId: string) =>
  (state: ContextAuditState): ContextAuditEdgeInput[] =>
    selectRunEvents(runId)(state).flatMap((event) =>
      (event.records ?? [])
        .filter((record) => typeof record.source === "string" && record.source.length > 0)
        .map((record, index) => ({
          id: `${eventKey(event)}:${index}:edge`,
          runId: event.run_id,
          source: record.source as string,
          target: event.node_id,
          inputName: record.input_name ?? null,
          namespace: record.namespace ?? null,
        })),
    );

function normalizeEvents(runId: string, events: ContextAuditEventV1[]): ContextAuditEventV1[] {
  const byKey = new Map<string, ContextAuditEventV1>();
  for (const event of events) {
    if (event.run_id !== runId) {
      continue;
    }
    byKey.set(eventKey(event), event);
  }
  return [...byKey.values()].sort(compareEvents);
}

function eventKey(event: ContextAuditEventV1): string {
  if (event.sequence !== null && event.sequence !== undefined) {
    return `${event.run_id}:${event.sequence}`;
  }
  return [
    event.run_id,
    event.node_id,
    event.block_type,
    event.access,
    event.mode,
    event.emitted_at,
    JSON.stringify(event.records ?? []),
  ].join(":");
}

function compareEvents(left: ContextAuditEventV1, right: ContextAuditEventV1): number {
  if (left.sequence !== null && left.sequence !== undefined) {
    if (right.sequence !== null && right.sequence !== undefined) {
      return left.sequence - right.sequence;
    }
    return -1;
  }
  if (right.sequence !== null && right.sequence !== undefined) {
    return 1;
  }
  return left.emitted_at.localeCompare(right.emitted_at);
}
