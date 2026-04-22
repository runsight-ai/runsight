// @vitest-environment jsdom

import React from "react";
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

type RunRecord = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: "completed" | "failed" | "running" | "pending";
  commit_sha: string;
  duration_seconds: number;
  total_tokens: number;
  total_cost_usd: number;
  source: string;
  branch: string;
  error: string | null;
  created_at: number;
  started_at: number;
  run_number: number | null;
  eval_pass_pct: number | null;
  regression_count: number | null;
  warnings?: Array<Record<string, unknown>>;
};

type LogEntry = {
  timestamp: string;
  level: string;
  message: string;
};

type EventSourceListener = (event: MessageEvent) => void;

const harness = vi.hoisted(() => ({
  runs: [] as RunRecord[],
  runLogsById: {} as Record<string, LogEntry[]>,
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
    appendEvents: vi.fn(),
    clearRun: vi.fn(),
  },
}));

const eventSources: MockEventSource[] = [];

class MockEventSource {
  public readonly url: string;
  public closed = false;
  private readonly listeners = new Map<string, EventSourceListener[]>();

  constructor(url: string) {
    this.url = url;
    eventSources.push(this);
  }

  addEventListener(type: string, listener: EventSourceListener) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  close = vi.fn(() => {
    this.closed = true;
  });

  emit(type: string, payload: Record<string, unknown>) {
    if (this.closed) {
      return;
    }
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(payload) }));
    }
  }
}

vi.mock("@/queries/runs", () => ({
  useRuns: () => ({
    data: { items: harness.runs },
    isLoading: false,
    isError: false,
  }),
  useRunLogs: (runId: string) => ({
    data: { items: harness.runLogsById[runId] ?? [] },
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
  },
  useRunRegressions: () => ({
    data: harness.runRegressions,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/queries/workflows", () => ({
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
  contextAuditRowsFromEvents: () => [],
}));

function makeRun(
  id: string,
  {
    createdAt,
    runNumber,
  }: {
    createdAt: number;
    runNumber: number;
  },
): RunRecord {
  return {
    id,
    workflow_id: "wf_957",
    workflow_name: "Bottom Panel Workflow",
    status: "completed",
    commit_sha: `${id}_sha`,
    duration_seconds: 30,
    total_tokens: 100,
    total_cost_usd: 0.42,
    source: "manual",
    branch: "main",
    error: null,
    created_at: createdAt,
    started_at: createdAt,
    run_number: runNumber,
    eval_pass_pct: null,
    regression_count: 0,
    warnings: [],
  };
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <SurfaceBottomPanel
        runId="run_live"
        workflowId="wf_957"
        defaultState="expanded"
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
    makeRun("run_live", { createdAt: 200, runNumber: 1 }),
    makeRun("run_other", { createdAt: 100, runNumber: 2 }),
  ];
  harness.runLogsById = {};
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
  eventSources.length = 0;
  vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RUN-957 bottom panel controller boundaries", () => {
  it("clears run-scoped live log buffers when the selected run changes", async () => {
    renderPanel();

    expect(eventSources.map((source) => source.url)).toEqual([
      "/api/runs/run_live/stream",
    ]);

    act(() => {
      eventSources[0].emit("log_entry", {
        timestamp: "2026-04-22T12:00:00.000Z",
        level: "info",
        message: "live only from run_live",
      });
    });

    expect(screen.getByText("live only from run_live")).toBeTruthy();

    await selectRunFromRunsTab("#2");

    expect(eventSources[0].closed).toBe(true);
    expect(eventSources.at(-1)?.url).toBe("/api/runs/run_other/stream");
    expect(screen.queryByText("live only from run_live")).toBeNull();
  });

  it("normalizes replayed history and live log entries into one visible row", () => {
    harness.runLogsById.run_live = [
      {
        timestamp: "2026-04-22T13:00:00.000Z",
        level: "info",
        message: "Node draft started",
      },
    ];

    renderPanel();

    act(() => {
      eventSources[0].emit("log_entry", {
        timestamp: "2026-04-22T13:00:00.000Z",
        level: "info",
        message: "Node draft started",
      });
    });

    expect(screen.getAllByText("Node draft started")).toHaveLength(1);
  });

  it("shows the existing no-log empty state after switching to a run with no history", async () => {
    renderPanel();

    act(() => {
      eventSources[0].emit("log_entry", {
        timestamp: "2026-04-22T13:05:00.000Z",
        level: "info",
        message: "stale streamed entry",
      });
    });

    expect(screen.getByText("stale streamed entry")).toBeTruthy();

    await selectRunFromRunsTab("#2");

    expect(screen.getByText("No logs captured for this run yet.")).toBeTruthy();
    expect(screen.queryByText("stale streamed entry")).toBeNull();
  });

  it("keeps historical logs scoped to the selected run after stale live streams are torn down", async () => {
    harness.runLogsById.run_other = [
      {
        timestamp: "2026-04-22T13:10:00.000Z",
        level: "info",
        message: "historical entry from run_other",
      },
    ];

    renderPanel();

    act(() => {
      eventSources[0].emit("log_entry", {
        timestamp: "2026-04-22T13:09:00.000Z",
        level: "info",
        message: "live only from run_live",
      });
    });

    expect(screen.getByText("live only from run_live")).toBeTruthy();

    const staleSource = eventSources[0];
    await selectRunFromRunsTab("#2");

    expect(staleSource.closed).toBe(true);
    expect(screen.getByText("historical entry from run_other")).toBeTruthy();
    expect(screen.queryByText("live only from run_live")).toBeNull();

    act(() => {
      staleSource.emit("log_entry", {
        timestamp: "2026-04-22T13:11:00.000Z",
        level: "error",
        message: "stale event after switch",
      });
    });

    expect(screen.queryByText("stale event after switch")).toBeNull();

    act(() => {
      eventSources.at(-1)?.emit("log_entry", {
        timestamp: "2026-04-22T13:12:00.000Z",
        level: "info",
        message: "live only from run_other",
      });
    });

    expect(screen.getByText("historical entry from run_other")).toBeTruthy();
    expect(screen.getByText("live only from run_other")).toBeTruthy();
  });

  it("retargets the audit tab to the new run without keeping terminal log entries from the old run", async () => {
    const user = userEvent.setup();
    renderPanel();

    act(() => {
      eventSources[0].emit("run_completed", {
        run_id: "run_live",
        total_cost_usd: 1.23,
      });
    });

    expect(eventSources[0].closed).toBe(true);
    expect(screen.getByText("Run completed. Total cost: $1.2300")).toBeTruthy();

    await selectRunFromRunsTab("#2");
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
