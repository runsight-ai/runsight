// @vitest-environment jsdom

import React from "react";
import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import type { RunListResponse, RunResponse } from "@runsight/shared/zod";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/testUtils";

const harness = vi.hoisted(() => ({
  listRuns: vi.fn<(params?: unknown) => Promise<RunListResponse>>(),
}));

vi.mock("@/api/runs", () => ({
  runsApi: {
    listRuns: (...args: unknown[]) => harness.listRuns(...args),
  },
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: { items: [{ id: "wf_root", name: "Root Flow" }] },
    isLoading: false,
    error: null,
  }),
}));

vi.mock("@/queries/dashboard", () => ({
  useDashboardKPIs: () => ({
    data: {
      runs_today: 2,
      cost_today_usd: 9.5,
      eval_pass_rate: 0.8,
      regressions: 0,
      runs_previous_period: 1,
      cost_previous_period_usd: 4.25,
      eval_pass_rate_previous_period: 0.7,
      regressions_previous_period: 0,
    },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useAttentionItems: () => ({ data: { items: [] } }),
  useRecentRuns: () => ({ data: { items: [] } }),
}));

vi.mock("../useNewWorkflow", () => ({
  useNewWorkflow: () => ({
    handleNewWorkflow: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/components/shared/PageHeader", () => ({
  PageHeader: ({
    title,
    subtitle,
    actions,
  }: {
    title: string;
    subtitle?: string;
    actions?: React.ReactNode;
  }) =>
    React.createElement("header", null, [
      React.createElement("h1", { key: "title" }, title),
      subtitle ? React.createElement("p", { key: "subtitle" }, subtitle) : null,
      React.createElement("div", { key: "actions" }, actions),
    ]),
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: ({
    title,
    description,
  }: {
    title: string;
    description: string;
  }) =>
    React.createElement("section", null, [
      React.createElement("h2", { key: "title" }, title),
      React.createElement("p", { key: "description" }, description),
    ]),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    type,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
  }) =>
    React.createElement(
      "button",
      {
        type: type ?? "button",
        onClick,
        disabled,
      },
      children,
    ),
}));

vi.mock("@runsight/ui/card", () => ({
  Card: ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/status-dot", () => ({
  StatusDot: () => React.createElement("span", null, "status-dot"),
}));

vi.mock("@runsight/ui/skeleton", () => ({
  Skeleton: () => React.createElement("div", null, "skeleton"),
}));

vi.mock("@runsight/ui/table", () => ({
  Table: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("table", null, children),
  TableBody: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("tbody", null, children),
  TableCell: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("td", null, children),
  TableHead: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("th", null, children),
  TableHeader: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("thead", null, children),
  TableRow: ({ children, onClick }: { children?: React.ReactNode; onClick?: () => void }) =>
    React.createElement("tr", { onClick }, children),
}));

vi.mock("../components/DashboardKPIs", () => ({
  DashboardKPIs: () => React.createElement("section", null, "dashboard-kpis"),
}));

vi.mock("../components/AttentionItems", () => ({
  AttentionItems: () => React.createElement("section", null, "attention-items"),
}));

vi.mock("lucide-react", () => ({
  Plus: () => React.createElement("span", { "aria-hidden": "true" }, "+"),
  Workflow: () => React.createElement("span", { "aria-hidden": "true" }, "wf"),
  Play: () => React.createElement("span", { "aria-hidden": "true" }, "play"),
}));

import { Component as DashboardOrOnboarding } from "../DashboardOrOnboarding";

type EventSourceListener = (event: MessageEvent) => void;

const eventSources: MockEventSource[] = [];

class MockEventSource {
  readonly url: string;
  readonly close = vi.fn();
  private readonly listeners = new Map<string, EventSourceListener[]>();

  constructor(url: string) {
    this.url = url;
    eventSources.push(this);
  }

  addEventListener(type: string, listener: EventSourceListener) {
    const existing = this.listeners.get(type) ?? [];
    this.listeners.set(type, [...existing, listener]);
  }

  emit(type: string, payload: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(payload) }));
    }
  }
}

function makeRun(overrides: Partial<RunResponse>): RunResponse {
  return {
    id: "run_root",
    workflow_id: "wf_root",
    workflow_name: "Root Flow",
    status: "running",
    error: null,
    started_at: 1_710_000_000,
    completed_at: null,
    duration_seconds: null,
    total_cost_usd: 1.25,
    total_tokens: 123,
    created_at: 1_710_000_100,
    branch: "main",
    source: "manual",
    commit_sha: "sha-root",
    run_number: 42,
    eval_pass_pct: null,
    eval_score_avg: null,
    regression_count: 0,
    regression_types: [],
    warnings: [],
    node_summary: null,
    parent_run_id: null,
    root_run_id: null,
    depth: 0,
    workflow_inputs: null,
    workflow_input_schema: null,
    ...overrides,
  };
}

function buildRunList(items: RunResponse[]): RunListResponse {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 50,
  };
}

function rootRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return makeRun(overrides);
}

function secondRootRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return makeRun({
    id: "run_root_2",
    workflow_id: "wf_root_2",
    workflow_name: "Second Root Flow",
    run_number: 43,
    total_cost_usd: 2.5,
    created_at: 1_710_000_150,
    ...overrides,
  });
}

function childRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return makeRun({
    id: "run_child",
    workflow_id: "wf_child",
    workflow_name: "Child Flow",
    run_number: 99,
    total_cost_usd: 0.4,
    created_at: 1_710_000_200,
    parent_run_id: "run_root",
    root_run_id: "run_root",
    depth: 1,
    ...overrides,
  });
}

function renderDashboard() {
  return renderWithProviders(React.createElement(DashboardOrOnboarding));
}

async function waitForInitialActiveRunsLoad(expectedWorkflowNames: string[]) {
  await waitFor(() => {
    expect(screen.queryByText("skeleton")).toBeNull();
    for (const workflowName of expectedWorkflowNames) {
      expect(screen.getByText(workflowName)).toBeTruthy();
    }
  });
}

function getRunRow(workflowName: string): HTMLTableRowElement {
  const row = screen.getByText(workflowName).closest("tr");
  expect(row).not.toBeNull();
  return row as HTMLTableRowElement;
}

function expectRunCost(workflowName: string, formattedCost: string) {
  expect(within(getRunRow(workflowName)).getByText(formattedCost)).toBeTruthy();
}

function findStream(runId: string): MockEventSource {
  const source = eventSources.find((candidate) => candidate.url === `/api/runs/${runId}/stream`);
  expect(source).toBeTruthy();
  return source as MockEventSource;
}

describe("active runs dashboard behavior", () => {
  let activeRunsData: RunResponse[] = [];

  beforeEach(() => {
    activeRunsData = [];
    harness.listRuns.mockReset();
    harness.listRuns.mockImplementation(async () => buildRunList(activeRunsData));
    eventSources.length = 0;
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows only eligible root runs and opens one stream per root run", async () => {
    activeRunsData = [rootRun(), secondRootRun(), childRun()];

    renderDashboard();
    await waitForInitialActiveRunsLoad(["Root Flow", "Second Root Flow"]);

    expect(screen.queryByText("Child Flow")).toBeNull();
    expect(eventSources.map((source) => source.url).sort()).toEqual([
      "/api/runs/run_root/stream",
      "/api/runs/run_root_2/stream",
    ]);
  });

  it.each(["run_completed", "run_failed"] as const)(
    "removes a root row through the %s refetch path without promoting child runs",
    async (eventName) => {
      activeRunsData = [rootRun()];

      renderDashboard();
      await waitForInitialActiveRunsLoad(["Root Flow"]);

      const rootSource = findStream("run_root");
      activeRunsData = [childRun()];

      act(() => {
        rootSource.emit(eventName, { run_id: "run_root" });
      });

      await waitFor(() => {
        expect(harness.listRuns.mock.calls.length).toBeGreaterThanOrEqual(2);
        expect(screen.queryByText("Root Flow")).toBeNull();
        expect(rootSource.close).toHaveBeenCalledTimes(1);
      });

      expect(screen.queryByText("Child Flow")).toBeNull();
      expect(eventSources.map((source) => source.url)).toEqual(["/api/runs/run_root/stream"]);
    },
  );

  it("updates rendered cost after a cost-bearing node_completed refetch without surfacing child runs", async () => {
    activeRunsData = [rootRun({ total_cost_usd: 1.25 })];

    renderDashboard();
    await waitForInitialActiveRunsLoad(["Root Flow"]);

    expectRunCost("Root Flow", "$1.25");

    const rootSource = findStream("run_root");
    activeRunsData = [rootRun({ total_cost_usd: 1.75 }), childRun({ total_cost_usd: 0.9 })];

    act(() => {
      rootSource.emit("node_completed", { cost_usd: 0.5 });
    });

    await waitFor(() => {
      expect(harness.listRuns.mock.calls.length).toBeGreaterThanOrEqual(2);
      expectRunCost("Root Flow", "$1.75");
    });

    expect(screen.queryByText("Child Flow")).toBeNull();
    expect(eventSources.map((source) => source.url)).toEqual(["/api/runs/run_root/stream"]);
  });

  it("ignores replay, context_resolution, node_eval_complete, and child_run_completed when the data does not change", async () => {
    activeRunsData = [rootRun()];

    renderDashboard();
    await waitForInitialActiveRunsLoad(["Root Flow"]);

    const rootSource = findStream("run_root");
    const initialCalls = harness.listRuns.mock.calls.length;

    act(() => {
      rootSource.emit("replay", { run_id: "run_root" });
      rootSource.emit("context_resolution", { run_id: "run_root" });
      rootSource.emit("node_eval_complete", { run_id: "run_root" });
      rootSource.emit("child_run_completed", { run_id: "run_child" });
    });

    expectRunCost("Root Flow", "$1.25");
    expect(harness.listRuns).toHaveBeenCalledTimes(initialCalls);
    expect(screen.queryByText("Child Flow")).toBeNull();
    expect(eventSources.map((source) => source.url)).toEqual(["/api/runs/run_root/stream"]);
  });

  it("closes root streams on unmount", async () => {
    activeRunsData = [rootRun(), secondRootRun()];

    const view = renderDashboard();
    await waitForInitialActiveRunsLoad(["Root Flow", "Second Root Flow"]);

    expect(eventSources.map((source) => source.url).sort()).toEqual([
      "/api/runs/run_root/stream",
      "/api/runs/run_root_2/stream",
    ]);

    view.unmount();

    expect(eventSources[0].close).toHaveBeenCalledTimes(1);
    expect(eventSources[1].close).toHaveBeenCalledTimes(1);
  });
});
