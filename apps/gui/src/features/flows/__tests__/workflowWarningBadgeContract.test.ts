// @vitest-environment jsdom

import type { WarningItem } from "@runsight/shared/zod";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  regressionIssues: [] as Array<Record<string, unknown>>,
}));

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("lucide-react", () => ({
  AlertTriangle: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "AlertTriangle" }),
  Info: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "Info" }),
  Trash2: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "Trash2" }),
}));

vi.mock("@runsight/ui/tooltip", () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  Tooltip: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  TooltipTrigger: ({ render }: { render: React.ReactNode }) =>
    React.createElement(React.Fragment, null, render),
  TooltipContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "tooltip-content" }, children),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflowRegressions: () => ({
    data: {
      count: mocks.regressionIssues.length,
      issues: mocks.regressionIssues,
    },
  }),
}));

import { WorkflowRow } from "../WorkflowRow";

function makeWarning(message: string): WarningItem {
  return {
    message,
    source: "tool_definitions",
    context: "lookup_profile",
  };
}

function renderWorkflowRow(workflow: Record<string, unknown>) {
  render(
    <ul role="list">
      <WorkflowRow
        workflow={workflow as never}
        onDelete={vi.fn()}
      />
    </ul>,
  );
}

beforeEach(() => {
  mocks.navigate.mockReset();
  mocks.regressionIssues = [];
});

describe("RUN-843 WorkflowRow warning badge contract", () => {
  it("shows an Info warning badge next to the regression badge when warnings and regressions exist", () => {
    mocks.regressionIssues = [
      {
        node_id: "node_1",
        node_name: "Writer",
        type: "assertion_regression",
        delta: {},
      },
    ];

    renderWorkflowRow({
      id: "wf_research",
      name: "Research & Review",
      enabled: true,
      block_count: 3,
      modified_at: Date.parse("2026-04-10T10:00:00Z") / 1000,
      commit_sha: "f078f13deadbeef",
      warnings: [makeWarning("Tool warning")],
      health: {
        run_count: 8,
        eval_pass_pct: 92,
        total_cost_usd: 0.42,
        regression_count: 1,
      },
    });

    const row = screen.getByRole("listitem", {
      name: "Open Research & Review workflow",
    });

    expect(row.querySelector('[data-icon="AlertTriangle"]')).toBeTruthy();
    expect(within(row).getByRole("status", { name: /1 warnings?/i })).toBeTruthy();
    expect(row.querySelector('[data-icon="Info"]')).toBeTruthy();
  });

  it("shows the warning badge alongside the regression label when regressions are zero", () => {
    renderWorkflowRow({
      id: "wf_docs",
      name: "Docs Digest",
      enabled: true,
      block_count: 2,
      modified_at: Date.parse("2026-04-09T10:00:00Z") / 1000,
      commit_sha: "a463263feedbeef",
      warnings: [makeWarning("Provider warning")],
      health: {
        run_count: 4,
        eval_pass_pct: 88,
        total_cost_usd: 0.19,
        regression_count: 0,
      },
    });

    const row = screen.getByRole("listitem", {
      name: "Open Docs Digest workflow",
    });

    expect(within(row).getByText(/0 regressions?|0 regression/)).toBeTruthy();
    expect(within(row).getByRole("status", { name: /1 warnings?/i })).toBeTruthy();
    expect(row.querySelector('[data-icon="Info"]')).toBeTruthy();
  });
});
