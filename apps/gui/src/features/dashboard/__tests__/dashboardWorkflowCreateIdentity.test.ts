// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  createWorkflow: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: () => mocks.navigate,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: { items: [] },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useCreateWorkflow: () => ({
    mutateAsync: mocks.createWorkflow,
    isPending: false,
  }),
}));

vi.mock("@/queries/dashboard", () => ({
  useDashboardKPIs: () => ({
    data: {
      runs_today: 0,
      cost_today_usd: 0,
      eval_pass_rate: 0,
      regressions: 0,
      runs_previous_period: 0,
      cost_previous_period_usd: 0,
      eval_pass_rate_previous_period: 0,
      regressions_previous_period: 0,
    },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useAttentionItems: () => ({ data: { items: [] } }),
  useRecentRuns: () => ({ data: { items: [] } }),
}));

vi.mock("@/queries/runs", () => ({
  useActiveRuns: () => ({
    activeRuns: [],
    subscribeToRunStream: vi.fn(),
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/components/shared/PageHeader", () => ({
  PageHeader: ({
    title,
    actions,
  }: {
    title: string;
    actions?: React.ReactNode;
  }) =>
    React.createElement("header", null, [
      React.createElement("h1", { key: "title" }, title),
      React.createElement("div", { key: "actions" }, actions),
    ]),
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: ({
    title,
    description,
    action,
  }: {
    title: string;
    description: string;
    action?: { label: string; onClick?: () => void };
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

vi.mock("@runsight/ui/badge", () => ({
  Badge: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("span", null, children),
}));

vi.mock("@runsight/ui/card", () => ({
  Card: ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/status-dot", () => ({
  StatusDot: () => React.createElement("span", null, "status-dot"),
}));

vi.mock("@runsight/ui/stat-card", () => ({
  StatCard: ({ label, value }: { label?: string; value?: unknown }) =>
    React.createElement("div", null, `${label ?? ""}:${String(value ?? "")}`),
}));

vi.mock("@runsight/ui/skeleton", () => ({
  Skeleton: () => React.createElement("div", null, "skeleton"),
}));

vi.mock("@runsight/ui/table", () => ({
  Table: ({ children }: { children?: React.ReactNode }) => React.createElement("table", null, children),
  TableBody: ({ children }: { children?: React.ReactNode }) => React.createElement("tbody", null, children),
  TableCell: ({ children }: { children?: React.ReactNode }) => React.createElement("td", null, children),
  TableHead: ({ children }: { children?: React.ReactNode }) => React.createElement("th", null, children),
  TableHeader: ({ children }: { children?: React.ReactNode }) => React.createElement("thead", null, children),
  TableRow: ({ children }: { children?: React.ReactNode }) => React.createElement("tr", null, children),
}));

vi.mock("lucide-react", () => ({
  Plus: () => React.createElement("span", { "aria-hidden": "true" }, "+"),
  Workflow: () => React.createElement("span", { "aria-hidden": "true" }, "wf"),
  Play: () => React.createElement("span", { "aria-hidden": "true" }, "play"),
  AlertTriangle: () => React.createElement("span", { "aria-hidden": "true" }, "alert"),
  Activity: () => React.createElement("span", { "aria-hidden": "true" }, "activity"),
}));

import { Component as DashboardOrOnboarding } from "../DashboardOrOnboarding";

describe("Dashboard workflow create identity", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.createWorkflow.mockReset();

    mocks.createWorkflow.mockImplementation(
      async (_createRequest: unknown): Promise<{ id: string }> => {
        const createdWorkflowIds = ["created_research_flow", "created_review_flow"];
        const createdWorkflowIndex = mocks.createWorkflow.mock.calls.length - 1;
        return {
          id: createdWorkflowIds[createdWorkflowIndex] ?? "created_extra_flow",
        };
      },
    );
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("creates workflows and navigates to each created workflow editor", async () => {
    const user = userEvent.setup();

    render(React.createElement(DashboardOrOnboarding));

    const createButton = screen.getByRole("button", { name: "New Workflow" });

    await user.click(createButton);
    await user.click(createButton);

    await waitFor(() => expect(mocks.createWorkflow).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledTimes(2));

    expect(mocks.navigate).toHaveBeenNthCalledWith(
      1,
      "/workflows/created_research_flow/edit",
    );
    expect(mocks.navigate).toHaveBeenNthCalledWith(
      2,
      "/workflows/created_review_flow/edit",
    );
  });
});
