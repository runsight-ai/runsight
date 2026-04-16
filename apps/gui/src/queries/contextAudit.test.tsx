// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ContextAuditEventV1, ContextAuditListResponse } from "@runsight/shared/zod";
import React, { type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { runsApi } from "../api/runs";
import { queryKeys } from "./keys";

const harness = vi.hoisted(() => ({
  getRunContextAudit: vi.fn(),
}));

vi.mock("../api/runs", () => ({
  runsApi: {
    getRunContextAudit: harness.getRunContextAudit,
  },
}));

type ContextAuditStoreModule = {
  useContextAuditStore: {
    getState: () => {
      replaceRunEvents: (runId: string, events: ContextAuditEventV1[]) => void;
      appendEvents: (runId: string, events: ContextAuditEventV1[]) => void;
      clearRun: (runId: string) => void;
    };
  };
  selectRunEvents: (runId: string) => (state: unknown) => ContextAuditEventV1[];
};

type RunsQueryModule = {
  useRunContextAudit: (runId: string, params?: { page_size?: number }) => {
    fetchNextPage: () => Promise<unknown>;
    hasNextPage?: boolean;
  };
  useRunContextAuditStream: (runId: string | null | undefined) => void;
};

type EventSourceListener = (event: MessageEvent) => void;

const eventSources: MockEventSource[] = [];

class MockEventSource {
  readonly url: string;
  readonly listeners = new Map<string, EventSourceListener[]>();
  closed = false;

  constructor(url: string) {
    this.url = url;
    eventSources.push(this);
  }

  addEventListener(type: string, listener: EventSourceListener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, payload: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(payload) }));
    }
  }

  emitRaw(type: string, data: string) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data }));
    }
  }

  close() {
    this.closed = true;
  }
}

function event(runId: string, nodeId: string, sequence: number): ContextAuditEventV1 {
  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: runId,
    workflow_name: "wf",
    node_id: nodeId,
    block_type: "linear",
    access: "declared",
    mode: "strict",
    sequence,
    records: [
      {
        input_name: "summary",
        from_ref: "draft.summary",
        namespace: "results",
        source: "draft",
        field_path: "summary",
        status: "resolved",
        severity: "allow",
        value_type: "str",
        preview: "bounded",
        reason: null,
        internal: false,
      },
    ],
    resolved_count: 1,
    denied_count: 0,
    warning_count: 0,
    emitted_at: `2026-04-17T00:00:0${sequence}.000Z`,
  };
}

function page(
  items: ContextAuditEventV1[],
  endCursor: string | null,
  hasNextPage: boolean,
): ContextAuditListResponse {
  return {
    items,
    page_size: items.length,
    end_cursor: endCursor,
    has_next_page: hasNextPage,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return React.createElement(QueryClientProvider, { client }, children);
}

async function loadRunsModule(): Promise<RunsQueryModule> {
  return import("./runs") as Promise<RunsQueryModule>;
}

async function loadStoreModule(): Promise<ContextAuditStoreModule> {
  const storeModulePath = "../store/contextAudit";
  return import(/* @vite-ignore */ storeModulePath) as Promise<ContextAuditStoreModule>;
}

describe("RUN-915 context audit query layer", () => {
  beforeEach(async () => {
    harness.getRunContextAudit.mockReset();
    eventSources.length = 0;
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds queryKeys.runs.contextAudit", () => {
    expect(queryKeys.runs.contextAudit("run_915")).toEqual([
      "runs",
      "run_915",
      "contextAudit",
    ]);
  });

  it("useRunContextAudit fetches paginated history and merges pages in execution order", async () => {
    const { useRunContextAudit } = await loadRunsModule();
    const store = await loadStoreModule();
    store.useContextAuditStore.getState().clearRun("run_915");
    harness.getRunContextAudit
      .mockResolvedValueOnce(page([event("run_915", "draft", 1)], "cursor-1", true))
      .mockResolvedValueOnce(page([event("run_915", "review", 2)], null, false));

    const { result } = renderHook(() => useRunContextAudit("run_915", { page_size: 1 }), {
      wrapper,
    });

    await waitFor(() => {
      expect(runsApi.getRunContextAudit).toHaveBeenCalledWith("run_915", {
        page_size: 1,
      });
    });

    await act(async () => {
      await result.current.fetchNextPage();
    });

    const events = store.selectRunEvents("run_915")(store.useContextAuditStore.getState());
    expect(events.map((item) => `${item.node_id}:${item.sequence}`)).toEqual([
      "draft:1",
      "review:2",
    ]);
    expect(runsApi.getRunContextAudit).toHaveBeenLastCalledWith("run_915", {
      cursor: "cursor-1",
      page_size: 1,
    });
  });

  it("useRunContextAuditStream appends valid context_resolution events and dedupes history", async () => {
    const { useRunContextAuditStream } = await loadRunsModule();
    const store = await loadStoreModule();
    store.useContextAuditStore.getState().clearRun("run_915");
    store.useContextAuditStore.getState().clearRun("other_run");
    store.useContextAuditStore
      .getState()
      .replaceRunEvents("run_915", [event("run_915", "draft", 1)]);

    renderHook(() => useRunContextAuditStream("run_915"), { wrapper });

    expect(eventSources[0].url).toBe("/api/runs/run_915/stream");
    act(() => {
      eventSources[0].emit("context_resolution", event("run_915", "draft", 1));
      eventSources[0].emit("context_resolution", event("run_915", "review", 2));
      eventSources[0].emit("context_resolution", event("other_run", "leak", 3));
      eventSources[0].emit("replay", event("run_915", "ignored_replay", 4));
    });

    const events = store.selectRunEvents("run_915")(store.useContextAuditStore.getState());
    expect(events.map((item) => `${item.node_id}:${item.sequence}`)).toEqual([
      "draft:1",
      "review:2",
    ]);
  });

  it("useRunContextAuditStream ignores malformed payloads and stays open until terminal events", async () => {
    const { useRunContextAuditStream } = await loadRunsModule();
    const store = await loadStoreModule();
    store.useContextAuditStore.getState().clearRun("run_915");

    renderHook(() => useRunContextAuditStream("run_915"), { wrapper });

    act(() => {
      eventSources[0].emitRaw("context_resolution", "{not-json");
      eventSources[0].emit("node_completed", { node_id: "draft" });
      eventSources[0].emit("context_resolution", event("run_915", "draft", 1));
    });

    expect(eventSources[0].closed).toBe(false);
    expect(store.selectRunEvents("run_915")(store.useContextAuditStore.getState())).toHaveLength(
      1,
    );

    act(() => {
      eventSources[0].emit("run_completed", { run_id: "run_915" });
    });

    expect(eventSources[0].closed).toBe(true);
  });
});
