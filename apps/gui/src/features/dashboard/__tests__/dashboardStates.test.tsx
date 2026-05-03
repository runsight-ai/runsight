// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  workflows: [] as Array<{ id: string; name: string }>,
  kpis: {
    runs_today: 0,
    cost_today_usd: 0,
    eval_pass_rate: null as number | null,
    regressions: null as number | null,
    runs_previous_period: 0,
    cost_previous_period_usd: 0,
    eval_pass_rate_previous_period: null as number | null,
    regressions_previous_period: null as number | null,
  },
  isPending: false,
  isError: false,
  isRunsError: false,
  activeRuns: [] as Array<{ id: string }>,
  attentionItems: [] as Array<Record<string, unknown>>,
  refetch: vi.fn(),
  handleNewWorkflow: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: () => harness.navigate,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({ data: { items: harness.workflows }, isLoading: false }),
}));

vi.mock("@/queries/dashboard", () => ({
  useDashboardKPIs: () => ({
    data: harness.kpis,
    isPending: harness.isPending,
    isError: harness.isError,
    refetch: harness.refetch,
  }),
  useAttentionItems: () => ({ data: { items: harness.attentionItems } }),
  useRecentRuns: () => ({ data: { items: [] } }),
}));

vi.mock("@/queries/runs", () => ({
  useActiveRuns: () => ({
    activeRuns: harness.activeRuns,
    subscribeToRunStream: vi.fn(() => ({ close: vi.fn() })),
    isLoading: false,
    isError: harness.isRunsError,
  }),
}));

vi.mock("../useNewWorkflow", () => ({
  useNewWorkflow: () => ({
    handleNewWorkflow: harness.handleNewWorkflow,
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

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => React.createElement("button", { type: "button", onClick, disabled }, children),
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: ({
    title,
    description,
    action,
  }: {
    title: string;
    description: string;
    action?: { label: string; onClick: () => void };
  }) =>
    React.createElement("section", null, [
      React.createElement("h2", { key: "title" }, title),
      React.createElement("p", { key: "description" }, description),
      action
        ? React.createElement("button", { key: "action", type: "button", onClick: action.onClick }, action.label)
        : null,
    ]),
}));

vi.mock("../components/DashboardKPIs", () => ({
  DashboardKPIs: (props: Record<string, unknown>) =>
    React.createElement("section", { "data-testid": "dashboard-kpis" }, [
      `runs:${String(props.runsToday)}`,
      `cost:${String(props.costTodayUsd)}`,
      `error:${String(props.isError)}`,
    ].join(" ")),
}));

vi.mock("../components/AttentionItems", () => ({
  AttentionItems: ({ items }: { items: unknown[] }) =>
    React.createElement("section", { "data-testid": "attention-items" }, `attention:${items.length}`),
}));

vi.mock("../components/ActiveRunsTable", () => ({
  ActiveRunsTable: ({ runs }: { runs: unknown[] }) =>
    React.createElement("section", { "data-testid": "active-runs" }, `active:${runs.length}`),
}));

vi.mock("lucide-react", () => ({
  Play: () => React.createElement("span", null),
  Plus: () => React.createElement("span", null),
  Workflow: () => React.createElement("span", null),
}));

import { Component as DashboardOrOnboarding } from "../DashboardOrOnboarding";

beforeEach(() => {
  harness.workflows = [];
  harness.kpis = {
    runs_today: 0,
    cost_today_usd: 0,
    eval_pass_rate: null,
    regressions: null,
    runs_previous_period: 0,
    cost_previous_period_usd: 0,
    eval_pass_rate_previous_period: null,
    regressions_previous_period: null,
  };
  harness.isPending = false;
  harness.isError = false;
  harness.isRunsError = false;
  harness.activeRuns = [];
  harness.attentionItems = [];
  harness.refetch.mockReset();
  harness.handleNewWorkflow.mockReset();
  harness.navigate.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("DashboardOrOnboarding states", () => {
  it("shows first-run onboarding when no workflows exist", () => {
    render(<DashboardOrOnboarding />);

    expect(screen.getByText("Welcome to Runsight")).toBeTruthy();
    fireEvent.click(screen.getByText("Create Workflow"));

    expect(harness.handleNewWorkflow).toHaveBeenCalledTimes(1);
  });

  it("shows the no-runs state after workflows exist but no runs were created today", () => {
    harness.workflows = [{ id: "review_flow", name: "Review Flow" }];

    render(<DashboardOrOnboarding />);

    expect(screen.getByText("No runs yet")).toBeTruthy();
    expect(screen.getByTestId("dashboard-kpis").textContent).toContain("runs:0");

    fireEvent.click(screen.getByText("Open Flows"));

    expect(harness.navigate).toHaveBeenCalledWith("/flows");
  });

  it("shows a retryable error banner while preserving loaded dashboard sections", () => {
    harness.workflows = [{ id: "review_flow", name: "Review Flow" }];
    harness.isError = true;
    harness.isRunsError = true;

    render(<DashboardOrOnboarding />);

    expect(screen.getByText("Couldn't load dashboard data. Check that the Runsight server is running.")).toBeTruthy();
    expect(screen.getByTestId("dashboard-kpis").textContent).toContain("error:true");

    fireEvent.click(screen.getByText("Retry"));

    expect(harness.refetch).toHaveBeenCalledTimes(1);
  });

  it("renders attention and active-run sections only when dashboard data calls for them", () => {
    harness.workflows = [{ id: "review_flow", name: "Review Flow" }];
    harness.kpis.runs_today = 3;
    harness.attentionItems = [{ run_id: "run_review_attention" }];
    harness.activeRuns = [{ id: "run_active" }];

    render(<DashboardOrOnboarding />);

    expect(screen.getByTestId("attention-items").textContent).toBe("attention:1");
    expect(screen.getByTestId("active-runs").textContent).toBe("active:1");
  });
});
