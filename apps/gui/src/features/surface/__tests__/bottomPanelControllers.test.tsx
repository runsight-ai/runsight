// @vitest-environment jsdom

import React from "react";
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import {
  buildBottomPanelContextResolutionEvent,
  buildBottomPanelRun,
  buildSurfaceLogEntry,
  buildSurfaceReplayEvent,
  eventSourceInstances,
  MockEventSource,
  type SurfaceLogEntry as LogEntry,
  type SurfaceRunRecord as RunRecord,
} from "./helpers/surfaceStreamTestHelpers";

const harness = vi.hoisted(() => ({
  runs: [] as RunRecord[],
  runLogsById: {} as Record<string, LogEntry[]>,
  runLogTotalsById: {} as Record<string, number>,
  runRegressions: { count: 0, issues: [] as Array<Record<string, unknown>> },
  workflowRegressions: { count: 0, issues: [] as Array<Record<string, unknown>> },
  auditCalls: [] as Array<{ runId: string; params?: { page_size?: number; node_id?: string } }>,
  auditStreamCalls: [] as Array<string | null | undefined>,
  canvasStore: {
    activeRunId: null as string | null,
    setNodeStatus: vi.fn(),
    setActiveRunId: vi.fn(),
    setRunCost: vi.fn(),
  },
  contextAuditStore: {
    activeRunId: null as string | null,
    eventsByRun: {} as Record<string, unknown[]>,
    replaceRunEvents: vi.fn((runId: string, events: unknown[]) => {
      harness.contextAuditStore.activeRunId = runId;
      harness.contextAuditStore.eventsByRun = { [runId]: events };
    }),
    appendEvents: vi.fn((runId: string, events: unknown[]) => {
      harness.contextAuditStore.eventsByRun = {
        ...harness.contextAuditStore.eventsByRun,
        [runId]: [...(harness.contextAuditStore.eventsByRun[runId] ?? []), ...events],
      };
    }),
    clearRun: vi.fn(),
  },
}));

vi.mock("@/queries/runs", async () => {
  const { useEffect } = await import("react");

  return {
    useRuns: (filters?: { workflow_id?: string }) => ({
      data: {
        items: filters?.workflow_id
          ? harness.runs.filter((run) => run.workflow_id === filters.workflow_id)
          : harness.runs,
      },
      isLoading: false,
      isError: false,
    }),
    useRunLogs: (runId: string) => ({
      data: {
        items: harness.runLogsById[runId] ?? [],
        total: harness.runLogTotalsById[runId] ?? (harness.runLogsById[runId] ?? []).length,
      },
      isLoading: false,
      isError: false,
    }),
    useRunContextAudit: (
      runId: string,
      params?: { page_size?: number; node_id?: string },
    ) => {
      harness.auditCalls.push({ runId, params });
      return {
        fetchNextPage: vi.fn(),
        hasNextPage: false,
      };
    },
    useRunContextAuditStream: (runId: string | null | undefined) => {
      harness.auditStreamCalls.push(runId);

      useEffect(() => {
        if (!runId) {
          return;
        }

        const source = new EventSource(`/api/runs/${runId}/stream`);

        source.addEventListener("context_resolution", (event) => {
          const payload = JSON.parse((event as MessageEvent).data) as Record<string, unknown>;

          if (payload.run_id === runId) {
            harness.contextAuditStore.appendEvents(runId, [payload]);
          }
        });

        source.addEventListener("run_completed", () => source.close());
        source.addEventListener("run_failed", () => source.close());

        return () => source.close();
      }, [runId]);
    },
    useRunRegressions: () => ({
      data: harness.runRegressions,
      isLoading: false,
      isError: false,
    }),
    useCreateRun: () => ({
      mutate: vi.fn(),
      isPending: false,
    }),
  };
});

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: null,
    isLoading: false,
    isError: false,
  }),
  useWorkflowRegressions: () => ({
    data: harness.workflowRegressions,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: Object.assign(
    (selector?: (state: typeof harness.canvasStore) => unknown) =>
      typeof selector === "function" ? selector(harness.canvasStore) : harness.canvasStore,
    {
      getState: () => harness.canvasStore,
    },
  ),
}));

vi.mock("@/store/contextAudit", () => ({
  useContextAuditStore: Object.assign(
    (selector?: (state: typeof harness.contextAuditStore) => unknown) =>
      typeof selector === "function"
        ? selector(harness.contextAuditStore)
        : harness.contextAuditStore,
    {
      getState: () => harness.contextAuditStore,
    },
  ),
  EMPTY_CONTEXT_AUDIT_EVENTS: [],
  selectRunEvents:
    (runId: string) =>
    (state: typeof harness.contextAuditStore) =>
      state.eventsByRun[runId] ?? [],
  contextAuditRowsFromEvents: (
    events: Array<{
      run_id: string;
      node_id: string;
      block_type: string;
      access: string;
      sequence?: number | null;
      emitted_at: string;
      records?: Array<{
        input_name?: string | null;
        from_ref?: string | null;
        status?: string;
        severity?: string;
        internal?: boolean;
      }>;
    }>,
  ) =>
    events.flatMap((event) =>
      (event.records ?? [
        {
          input_name: "context",
          from_ref: event.access,
          status: "resolved",
          severity: "allow",
          internal: false,
        },
      ]).map((record, index) => ({
        id: `${event.run_id}:${event.sequence ?? event.emitted_at}:${index}`,
        runId: event.run_id,
        nodeId: event.node_id,
        blockType: event.block_type,
        access: event.access,
        sequence: event.sequence,
        emittedAt: event.emitted_at,
        inputName: record.input_name ?? null,
        fromRef: record.from_ref ?? null,
        status: record.status ?? "resolved",
        severity: record.severity ?? "allow",
        internal: record.internal ?? false,
      })),
    ),
}));

function expectSingleStreamForRun(runId: string) {
  const matching = eventSourceInstances.filter(
    (source) => source.url === `/api/runs/${runId}/stream`,
  );

  expect(matching).toHaveLength(1);

  return matching[0];
}

function renderPanel({
  runId = "run_live",
  workflowId = "wf_bottom_panel",
  onAuditNodeSelect,
}: {
  runId?: string;
  workflowId?: string;
  onAuditNodeSelect?: (nodeId: string, runId?: string) => void;
} = {}) {
  return render(
    <MemoryRouter>
      <SurfaceBottomPanel
        runId={runId}
        workflowId={workflowId}
        defaultState="expanded"
        onAuditNodeSelect={onAuditNodeSelect}
      />
    </MemoryRouter>,
  );
}

async function selectRunFromRunsTab(runNumberLabel: string) {
  const user = userEvent.setup();
  await user.click(screen.getByTestId("workflow-runs-tab"));
  await user.click(within(screen.getByTestId("workflow-runs-panel")).getByText(runNumberLabel));
}

beforeEach(() => {
  cleanup();
  harness.runs = [
    buildBottomPanelRun("run_live", { createdAt: 200, runNumber: 1 }),
    buildBottomPanelRun("run_other", { createdAt: 100, runNumber: 2 }),
  ];
  harness.runLogsById = {};
  harness.runLogTotalsById = {};
  harness.runRegressions = { count: 0, issues: [] };
  harness.workflowRegressions = { count: 0, issues: [] };
  harness.auditCalls = [];
  harness.auditStreamCalls = [];
  harness.canvasStore.activeRunId = null;
  harness.canvasStore.setNodeStatus.mockReset();
  harness.canvasStore.setActiveRunId.mockReset();
  harness.canvasStore.setRunCost.mockReset();
  harness.contextAuditStore.activeRunId = null;
  harness.contextAuditStore.eventsByRun = {};
  harness.contextAuditStore.replaceRunEvents.mockClear();
  harness.contextAuditStore.appendEvents.mockClear();
  harness.contextAuditStore.clearRun.mockClear();
  eventSourceInstances.length = 0;
  vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("bottom panel controller boundaries", () => {
  it("keeps audit hydration attached to the selected run from one shared stream even when the Audit tab is closed", async () => {
    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    expect(harness.auditCalls.at(-1)).toMatchObject({
      runId: "run_live",
      params: { page_size: 100 },
    });
    expect(harness.contextAuditStore.replaceRunEvents).toHaveBeenCalledWith("run_live", []);
    expect(screen.getByText("No logs captured for this run yet.")).toBeTruthy();

    act(() => {
      liveSource.emit(
        "context_resolution",
        buildBottomPanelContextResolutionEvent("run_live", "draft", 1),
      );
    });

    expect(harness.contextAuditStore.appendEvents).toHaveBeenCalledWith("run_live", [
      expect.objectContaining({
        run_id: "run_live",
        node_id: "draft",
        sequence: 1,
      }),
    ]);
    expect(harness.contextAuditStore.eventsByRun.run_live).toEqual([
      expect.objectContaining({
        run_id: "run_live",
        node_id: "draft",
        sequence: 1,
      }),
    ]);
    expect(screen.getByText("No logs captured for this run yet.")).toBeTruthy();

    await selectRunFromRunsTab("#2");
    const otherSource = expectSingleStreamForRun("run_other");

    expect(harness.auditCalls.at(-1)).toMatchObject({
      runId: "run_other",
      params: { page_size: 100 },
    });
    expect(harness.contextAuditStore.replaceRunEvents).toHaveBeenLastCalledWith("run_other", []);
    expect(liveSource.closed).toBe(true);
    expect(otherSource).not.toBe(liveSource);
  });

  it("resets selection when the workflow context switches to a different run set", async () => {
    harness.runs = [
      buildBottomPanelRun("run_live", {
        createdAt: 200,
        runNumber: 1,
        workflowId: "wf_bottom_panel",
      }),
      buildBottomPanelRun("run_other", {
        createdAt: 100,
        runNumber: 2,
        workflowId: "wf_bottom_panel",
      }),
      buildBottomPanelRun("run_fresh", {
        createdAt: 300,
        runNumber: 1,
        workflowId: "wf_other_panel",
      }),
    ];

    const view = renderPanel({ runId: "run_live", workflowId: "wf_bottom_panel" });
    const liveSource = expectSingleStreamForRun("run_live");

    await selectRunFromRunsTab("#2");
    const otherSource = expectSingleStreamForRun("run_other");
    expect(harness.auditCalls.at(-1)).toMatchObject({
      runId: "run_other",
      params: { page_size: 100 },
    });

    view.rerender(
      <MemoryRouter>
        <SurfaceBottomPanel
          runId="run_fresh"
          workflowId="wf_other_panel"
          defaultState="expanded"
        />
      </MemoryRouter>,
    );

    expect(harness.auditCalls.at(-1)).toMatchObject({
      runId: "run_fresh",
      params: { page_size: 100 },
    });
    expect(liveSource.closed).toBe(true);
    expect(otherSource.closed).toBe(true);
    expect(expectSingleStreamForRun("run_fresh")?.url).toBe("/api/runs/run_fresh/stream");
  });

  it("passes audit row selection to the owner with the currently selected run", async () => {
    const user = userEvent.setup();
    const onAuditNodeSelect = vi.fn();
    renderPanel({ onAuditNodeSelect });
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit(
        "context_resolution",
        buildBottomPanelContextResolutionEvent("run_live", "draft", 1),
      );
    });

    await user.click(screen.getByTestId("workflow-audit-tab"));
    await user.click(screen.getByRole("button", { name: "Open context audit for draft" }));
    expect(onAuditNodeSelect).toHaveBeenLastCalledWith("draft", "run_live");

    await selectRunFromRunsTab("#2");
    const otherSource = expectSingleStreamForRun("run_other");
    act(() => {
      otherSource.emit(
        "context_resolution",
        buildBottomPanelContextResolutionEvent("run_other", "review", 2),
      );
    });

    await user.click(screen.getByTestId("workflow-audit-tab"));
    await user.click(screen.getByRole("button", { name: "Open context audit for review" }));
    expect(onAuditNodeSelect).toHaveBeenLastCalledWith("review", "run_other");
  });

  it("switches runs by closing the prior shared stream and ignoring stale log and audit events from it", async () => {
    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2026-04-22T12:00:00.000Z",
        message: "live only from run_live",
      }));
      liveSource.emit(
        "context_resolution",
        buildBottomPanelContextResolutionEvent("run_live", "draft", 1),
      );
    });

    expect(screen.getByText("live only from run_live")).toBeTruthy();

    await selectRunFromRunsTab("#2");
    const otherSource = expectSingleStreamForRun("run_other");

    expect(liveSource.closed).toBe(true);
    expect(screen.queryByText("live only from run_live")).toBeNull();

    act(() => {
      liveSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2026-04-22T12:01:00.000Z",
        level: "error",
        message: "stale event after switch",
      }));
      liveSource.emit(
        "context_resolution",
        buildBottomPanelContextResolutionEvent("run_live", "stale", 2),
      );
    });

    expect(screen.queryByText("stale event after switch")).toBeNull();
    expect(harness.contextAuditStore.eventsByRun.run_other ?? []).toEqual([]);

    act(() => {
      otherSource.emit(
        "context_resolution",
        buildBottomPanelContextResolutionEvent("run_other", "review", 1),
      );
      otherSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2026-04-22T12:02:00.000Z",
        message: "live only from run_other",
      }));
    });

    expect(harness.contextAuditStore.eventsByRun.run_other).toEqual([
      expect.objectContaining({
        run_id: "run_other",
        node_id: "review",
        sequence: 1,
      }),
    ]);
    expect(screen.getByText("live only from run_other")).toBeTruthy();
  });

  it("normalizes replayed history and live log entries into one visible row", () => {
    harness.runLogsById.run_live = [buildSurfaceLogEntry()];

    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("log_entry", buildSurfaceLogEntry());
    });

    expect(screen.getAllByText("Node draft started")).toHaveLength(1);
  });

  it("normalizes numeric epoch-second log timestamps before deduping live entries", () => {
    harness.runLogsById.run_live = [buildSurfaceLogEntry({ timestamp: 1713790800 })];

    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2024-04-22T13:00:00.000Z",
      }));
    });

    expect(screen.getAllByText("Node draft started")).toHaveLength(1);
  });

  it("renders replay-only lifecycle payloads when fetched history is empty", () => {
    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("replay", buildSurfaceReplayEvent());
    });

    expect(screen.getByText("Node draft started")).toBeTruthy();
  });

  it("drops replay placeholders once canonical log history arrives", () => {
    const view = renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("replay", buildSurfaceReplayEvent({
        id: 1,
        timestamp: "2026-04-22T13:01:00.000Z",
      }));
    });

    expect(screen.getByText("Node draft started")).toBeTruthy();

    harness.runLogsById.run_live = [
      {
        id: 1,
        timestamp: "2026-04-22T13:01:00.000Z",
        level: "info",
        message: '{"event":"block_start","block_id":"draft"}',
      },
    ];
    harness.runLogTotalsById.run_live = 1;

    view.rerender(
      <MemoryRouter>
        <SurfaceBottomPanel
          runId="run_live"
          workflowId="wf_bottom_panel"
          defaultState="expanded"
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("Node draft started")).toHaveLength(1);
  });

  it("keeps unmatched replay history visible when the fetched log page is partial", () => {
    const view = renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("replay", buildSurfaceReplayEvent({
        id: 1,
        timestamp: "2026-04-22T13:01:00.000Z",
      }));
      liveSource.emit("replay", buildSurfaceReplayEvent({
        id: 2,
        timestamp: "2026-04-22T13:02:00.000Z",
        event: "block_complete",
        block_id: "review",
      }));
    });

    harness.runLogsById.run_live = [
      {
        id: 1,
        timestamp: "2026-04-22T13:01:00.000Z",
        level: "info",
        message: '{"event":"block_start","block_id":"draft"}',
      },
    ];
    harness.runLogTotalsById.run_live = 2;

    view.rerender(
      <MemoryRouter>
        <SurfaceBottomPanel
          runId="run_live"
          workflowId="wf_bottom_panel"
          defaultState="expanded"
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("Node draft started")).toHaveLength(1);
    expect(screen.getByText("Node review completed")).toBeTruthy();
  });

  it("keeps repeated lifecycle occurrences for the same block distinct", () => {
    const view = renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("replay", buildSurfaceReplayEvent({
        id: 11,
        timestamp: "2026-04-22T13:01:00.000Z",
      }));
      liveSource.emit("replay", buildSurfaceReplayEvent({
        id: 12,
        timestamp: "2026-04-22T13:02:00.000Z",
      }));
    });

    expect(screen.getAllByText("Node draft started")).toHaveLength(2);

    harness.runLogsById.run_live = [
      {
        id: 11,
        timestamp: "2026-04-22T13:01:00.000Z",
        level: "info",
        message: '{"event":"block_start","block_id":"draft"}',
      },
      {
        id: 12,
        timestamp: "2026-04-22T13:02:00.000Z",
        level: "info",
        message: '{"event":"block_start","block_id":"draft"}',
      },
    ];
    harness.runLogTotalsById.run_live = 2;

    view.rerender(
      <MemoryRouter>
        <SurfaceBottomPanel
          runId="run_live"
          workflowId="wf_bottom_panel"
          defaultState="expanded"
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("Node draft started")).toHaveLength(2);
  });

  it("shows the existing no-log empty state after switching to a run with no history", async () => {
    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2026-04-22T13:05:00.000Z",
        message: "stale streamed entry",
      }));
    });

    expect(screen.getByText("stale streamed entry")).toBeTruthy();

    await selectRunFromRunsTab("#2");

    expect(screen.getByText("No logs captured for this run yet.")).toBeTruthy();
    expect(screen.queryByText("stale streamed entry")).toBeNull();
  });

  it("keeps historical logs scoped to the selected run after stale live streams are torn down", async () => {
    harness.runLogsById.run_other = [
      buildSurfaceLogEntry({
        timestamp: "2026-04-22T13:10:00.000Z",
        message: "historical entry from run_other",
      }),
    ];

    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2026-04-22T13:09:00.000Z",
        message: "live only from run_live",
      }));
    });

    expect(screen.getByText("live only from run_live")).toBeTruthy();

    const staleSource = liveSource;
    await selectRunFromRunsTab("#2");
    const otherSource = expectSingleStreamForRun("run_other");

    expect(staleSource.closed).toBe(true);
    expect(screen.getByText("historical entry from run_other")).toBeTruthy();
    expect(screen.queryByText("live only from run_live")).toBeNull();

    act(() => {
      staleSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2026-04-22T13:11:00.000Z",
        level: "error",
        message: "stale event after switch",
      }));
    });

    expect(screen.queryByText("stale event after switch")).toBeNull();

    act(() => {
      otherSource.emit("log_entry", buildSurfaceLogEntry({
        timestamp: "2026-04-22T13:12:00.000Z",
        message: "live only from run_other",
      }));
    });

    expect(screen.getByText("historical entry from run_other")).toBeTruthy();
    expect(screen.getByText("live only from run_other")).toBeTruthy();
  });

  it("closes the shared stream on terminal events while keeping audit data, logs, and canvas updates in sync", async () => {
    const user = userEvent.setup();
    renderPanel();
    const liveSource = expectSingleStreamForRun("run_live");

    act(() => {
      liveSource.emit(
        "context_resolution",
        buildBottomPanelContextResolutionEvent("run_live", "draft", 1),
      );
      liveSource.emit("node_completed", {
        node_id: "draft",
        cost_usd: 0.75,
      });
      liveSource.emit("run_completed", {
        run_id: "run_live",
        total_cost_usd: 1.23,
      });
    });

    expect(harness.contextAuditStore.eventsByRun.run_live).toEqual([
      expect.objectContaining({
        run_id: "run_live",
        node_id: "draft",
        sequence: 1,
      }),
    ]);
    expect(harness.canvasStore.setNodeStatus).toHaveBeenCalledWith("draft", "completed");
    expect(harness.canvasStore.setRunCost).toHaveBeenCalledWith(1.23);
    expect(harness.canvasStore.setActiveRunId).toHaveBeenCalledWith(null);
    expect(liveSource.closed).toBe(true);
    expect(screen.getByText("Run completed. Total cost: $1.2300")).toBeTruthy();

    await selectRunFromRunsTab("#2");
    expectSingleStreamForRun("run_other");
    await user.click(screen.getByTestId("workflow-audit-tab"));

    expect(harness.auditCalls.at(-1)).toMatchObject({
      runId: "run_other",
      params: { page_size: 100 },
    });

    await user.click(screen.getByTestId("workflow-logs-tab"));
    expect(screen.queryByText("Run completed. Total cost: $1.2300")).toBeNull();
  });
});

import { SurfaceBottomPanel } from "../SurfaceBottomPanel";
