// @vitest-environment jsdom

import type { RunResponse, WarningItem } from "@runsight/shared/zod";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

const mocks = vi.hoisted(() => ({
  runs: [] as RunResponse[],
  runRegressionsById: {} as Record<string, { issues: Array<Record<string, unknown>> }>,
  navigate: vi.fn(),
  onOpenRun: vi.fn(),
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
  Play: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "Play" }),
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

vi.mock("@/queries/runs", () => ({
  useRuns: () => ({
    data: {
      items: mocks.runs,
      total: mocks.runs.length,
      offset: 0,
      limit: 20,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRunRegressions: (runId?: string) => ({
    data: runId ? mocks.runRegressionsById[runId] : undefined,
  }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: {
      items: [],
      total: 0,
    },
    isLoading: false,
    error: null,
  }),
}));

import { RunRow } from "../RunRow";
import { RunsTab } from "../RunsTab";
import type { RunRowProps } from "../RunRow";

function makeWarning(message: string): WarningItem {
  return {
    message,
    source: "tool_definitions",
    context: "lookup_profile",
  };
}

function makeRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return {
    id: "run_1",
    workflow_id: "wf_1",
    workflow_name: "Workflow One",
    status: "completed",
    started_at: 1_776_120_000,
    completed_at: 1_776_120_030,
    duration_seconds: 30,
    total_cost_usd: 0.01,
    total_tokens: 42,
    created_at: 1_776_119_999,
    branch: "main",
    source: "manual",
    commit_sha: "abcdef1234567890",
    run_number: 10,
    eval_pass_pct: 95,
    eval_score_avg: 0.95,
    regression_count: 0,
    warnings: [],
    ...overrides,
  };
}

function renderRunRow(run: RunResponse) {
  render(
    <table>
      <tbody>
        <RunRow run={run} onOpen={mocks.onOpenRun} />
      </tbody>
    </table>,
  );
}

function getRunAttentionCell(row: HTMLElement) {
  return within(row).getAllByRole("cell")[8];
}

function HarnessRunRow({ run }: RunRowProps) {
  return (
    <tr data-testid={`run-row-${run.id}`}>
      <td>{run.status}</td>
      <td>{run.workflow_name}</td>
      <td>{run.run_number ?? "—"}</td>
      <td>{run.commit_sha ?? "—"}</td>
      <td>{run.source}</td>
      <td>{run.duration_seconds ?? "—"}</td>
      <td>{run.total_cost_usd}</td>
      <td>{run.eval_pass_pct ?? "—"}</td>
      <td>{(run.regression_count ?? 0) + (run.warnings?.length ?? 0)}</td>
      <td>{run.started_at ?? "—"}</td>
    </tr>
  );
}

function renderRunsTab(props: Partial<React.ComponentProps<typeof RunsTab>> = {}) {
  render(
    <MemoryRouter>
      <RunsTab
        RowComponent={HarnessRunRow}
        workflowFilter={null}
        attentionOnly={false}
        activeOnly={false}
        onWorkflowFilterChange={vi.fn()}
        onAttentionFilterChange={vi.fn()}
        onActiveFilterChange={vi.fn()}
        onClearFilters={vi.fn()}
        {...props}
      />
    </MemoryRouter>,
  );
}

function getVisibleWorkflowOrder() {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[1]?.textContent ?? "");
}

beforeEach(() => {
  mocks.runs.length = 0;
  mocks.navigate.mockReset();
  mocks.onOpenRun.mockReset();
  mocks.runRegressionsById = {};
});

afterEach(() => {
  mocks.runs.length = 0;
  mocks.runRegressionsById = {};
});

describe("RUN-843 RunRow warnings + regressions cell", () => {
  it("renders a dash when both regression_count and warnings are empty", () => {
    renderRunRow(makeRun({
      regression_count: 0,
      warnings: [],
    }));

    const row = screen.getByRole("row");
    const attentionCell = getRunAttentionCell(row);

    expect(within(attentionCell).getByText("—")).toBeTruthy();
  });

  it("renders only the blue warning badge for warning-only runs", () => {
    const run = makeRun({
      id: "run_warning_only",
      workflow_name: "Warning Only Workflow",
      regression_count: 0,
      warnings: [makeWarning("Tool warning")],
    });

    renderRunRow(run);

    const row = screen.getByRole("row");
    const attentionCell = getRunAttentionCell(row);
    const warningBadge = within(attentionCell).getByRole("status", {
      name: /1 warnings?/i,
    });

    expect(warningBadge).toBeTruthy();
    expect(warningBadge.textContent).toContain("1");
    expect(attentionCell.querySelector('[data-icon="Info"]')).toBeTruthy();
    expect(attentionCell.querySelector('[data-icon="AlertTriangle"]')).toBeNull();
  });

  it("renders both regression and warning badges when both are present", () => {
    const run = makeRun({
      id: "run_both",
      workflow_name: "Regression + Warning Workflow",
      regression_count: 2,
      warnings: [makeWarning("Provider warning")],
    });

    mocks.runRegressionsById[run.id] = {
      issues: [
        {
          node_id: "node_1",
          node_name: "Writer",
          type: "assertion_regression",
          delta: {},
        },
      ],
    };

    renderRunRow(run);

    const row = screen.getByRole("row");
    const attentionCell = getRunAttentionCell(row);
    const badgeGroup = attentionCell.querySelector("span.inline-flex.items-center.gap-2");

    expect(badgeGroup).toBeTruthy();
    expect(badgeGroup?.textContent).toContain("2");
    expect(badgeGroup?.textContent).toContain("1");
    expect(badgeGroup?.querySelector('[data-icon="AlertTriangle"]')).toBeTruthy();
    expect(badgeGroup?.querySelector('[data-icon="Info"]')).toBeTruthy();
  });
});

describe("RUN-843 RunsTab attention + sorting", () => {
  it("renames the regressions column label to Warnings", () => {
    mocks.runs.push(
      makeRun({
        id: "run_header_1",
        workflow_name: "Header Workflow",
        warnings: [makeWarning("Header warning")],
      }),
    );

    renderRunsTab();

    expect(
      screen.getByRole("columnheader", { name: "Warnings" }),
    ).toBeTruthy();
  });

  it("includes warning-only runs when Needs attention is active", () => {
    mocks.runs.push(
      makeRun({
        id: "run_warn_only",
        workflow_name: "Warning Only Workflow",
        regression_count: 0,
        warnings: [makeWarning("Warning found")],
      }),
      makeRun({
        id: "run_clear",
        workflow_name: "No Attention Workflow",
        regression_count: 0,
        warnings: [],
      }),
    );

    renderRunsTab({ attentionOnly: true });

    expect(screen.getByText("Warning Only Workflow")).toBeTruthy();
    expect(screen.queryByText("No Attention Workflow")).toBeNull();
  });

  it("sorts the attention column by combined regression_count + warnings.length", async () => {
    const user = userEvent.setup();

    mocks.runs.push(
      makeRun({
        id: "run_regression_two",
        workflow_name: "Regression Two",
        regression_count: 2,
        warnings: [],
      }),
      makeRun({
        id: "run_warning_two",
        workflow_name: "Warning Two",
        regression_count: 0,
        warnings: [makeWarning("Warning one"), makeWarning("Warning two")],
      }),
      makeRun({
        id: "run_attention_one",
        workflow_name: "Attention One",
        regression_count: 1,
        warnings: [],
      }),
    );

    renderRunsTab();

    const attentionHeader = screen.getByRole("columnheader", {
      name: /warnings|regr/i,
    });
    await user.click(attentionHeader);

    expect(getVisibleWorkflowOrder()).toEqual([
      "Attention One",
      "Regression Two",
      "Warning Two",
    ]);
  });

  it("does not use regressions-only copy in the empty attention state", () => {
    mocks.runs.push(
      makeRun({
        id: "run_no_attention",
        workflow_name: "No Attention Workflow",
        regression_count: 0,
        warnings: [],
      }),
    );

    renderRunsTab({ attentionOnly: true });

    expect(screen.getByText("No runs need attention")).toBeTruthy();
    expect(screen.queryByText("No runs with regressions found.")).toBeNull();
  });
});
