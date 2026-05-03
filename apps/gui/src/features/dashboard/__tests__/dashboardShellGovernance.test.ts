// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const harness = vi.hoisted(() => ({
  handleNewWorkflow: vi.fn(),
  navigate: vi.fn(),
  refetch: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: () => harness.navigate,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({ data: { items: [] }, isLoading: false }),
}));

vi.mock("@/queries/dashboard", () => ({
  useDashboardKPIs: () => ({
    data: {
      runs_today: 0,
      cost_today_usd: 0,
      eval_pass_rate: null,
      regressions: null,
      runs_previous_period: 0,
      cost_previous_period_usd: 0,
      eval_pass_rate_previous_period: null,
      regressions_previous_period: null,
    },
    isPending: false,
    isError: false,
    refetch: harness.refetch,
  }),
  useAttentionItems: () => ({ data: { items: [] } }),
  useRecentRuns: () => ({ data: { items: [] } }),
}));

vi.mock("@/queries/runs", () => ({
  useActiveRuns: () => ({
    activeRuns: [],
    subscribeToRunStream: vi.fn(() => ({ close: vi.fn() })),
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../useNewWorkflow", () => ({
  useNewWorkflow: () => ({
    handleNewWorkflow: harness.handleNewWorkflow,
    isPending: false,
  }),
}));

vi.mock("@/components/shared/PageHeader", () => ({
  PageHeader: ({ title, actions }: { title: string; actions?: React.ReactNode }) =>
    React.createElement("header", null, [
      React.createElement("h1", { key: "title" }, title),
      React.createElement("div", { key: "actions" }, actions),
    ]),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    disabled,
    onClick,
  }: {
    children?: React.ReactNode;
    disabled?: boolean;
    onClick?: () => void;
  }) => React.createElement("button", { type: "button", disabled, onClick }, children),
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
        ? React.createElement(
            "button",
            { key: "action", type: "button", onClick: action.onClick },
            action.label,
          )
        : null,
    ]),
}));

vi.mock("../components/DashboardKPIs", () => ({
  DashboardKPIs: () => React.createElement("section", { "data-testid": "dashboard-kpis" }),
}));

vi.mock("../components/AttentionItems", () => ({
  AttentionItems: () => React.createElement("section", { "data-testid": "attention-items" }),
}));

vi.mock("../components/ActiveRunsTable", () => ({
  ActiveRunsTable: () => React.createElement("section", { "data-testid": "active-runs" }),
}));

vi.mock("lucide-react", () => ({
  Play: () => React.createElement("span", null),
  Plus: () => React.createElement("span", null),
  Workflow: () => React.createElement("span", null),
}));

import { Component as DashboardOrOnboarding } from "../DashboardOrOnboarding";

beforeEach(() => {
  harness.handleNewWorkflow.mockReset();
  harness.navigate.mockReset();
  harness.refetch.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("dashboard shell smoke", () => {
  it("renders the Home header with the direct New Workflow action", () => {
    render(React.createElement(DashboardOrOnboarding));

    expect(screen.getByRole("heading", { name: "Home" })).toBeTruthy();
    expect(screen.getByText("Welcome to Runsight")).toBeTruthy();
    expect(screen.queryByText(/Quick Actions|System Health|Active Workflows|Recent Runs/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "New Workflow" }));

    expect(harness.handleNewWorkflow).toHaveBeenCalledTimes(1);
  });
});
