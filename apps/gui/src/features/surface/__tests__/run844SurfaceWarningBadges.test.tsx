// @vitest-environment jsdom

import React from "react";
import type { RunResponse, WarningItem } from "@runsight/shared/zod";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  onSelect: vi.fn(),
  runRegressionsById: {} as Record<string, { issues: Array<Record<string, unknown>> }>,
  runRegressionCalls: [] as string[],
}));

vi.mock("lucide-react", () => ({
  AlertTriangle: (props: Record<string, unknown>) =>
    React.createElement("svg", {
      ...props,
      "data-icon": "AlertTriangle",
      "data-testid": "alert-triangle-icon",
    }),
  Info: (props: Record<string, unknown>) =>
    React.createElement("svg", {
      ...props,
      "data-icon": "Info",
      "data-testid": "info-icon",
    }),
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
  useRunRegressions: (runId?: string) => {
    mocks.runRegressionCalls.push(runId ?? "");
    return {
      data: runId ? mocks.runRegressionsById[runId] : undefined,
      isLoading: false,
      isError: false,
    };
  },
}));

import { SurfaceRunRow } from "../SurfaceRunRow";
import { SurfaceRunsTable } from "../SurfaceRunsTable";

function makeWarning(message: string): WarningItem {
  return {
    message,
    source: "tool_definitions",
    context: "lookup_profile",
  };
}

function makeRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return {
    id: "surface_run_1",
    workflow_id: "wf_1",
    workflow_name: "Surface Workflow",
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

function renderSurfaceRunRow(run: RunResponse) {
  render(
    <table>
      <tbody>
        <SurfaceRunRow run={run} onSelect={mocks.onSelect} />
      </tbody>
    </table>,
  );
}

function getWarningsCell(row: HTMLElement) {
  return within(row).getAllByRole("cell")[7];
}

beforeEach(() => {
  mocks.onSelect.mockReset();
  mocks.runRegressionsById = {};
  mocks.runRegressionCalls = [];
});

describe("RUN-844 SurfaceRunRow merged warnings cell", () => {
  it("shows an accessible warning badge when warnings are present and regression_count is zero", () => {
    renderSurfaceRunRow(makeRun({
      id: "surface_warning_only",
      regression_count: 0,
      warnings: [makeWarning("Provider warning"), makeWarning("Second warning")],
    }));

    const row = screen.getByRole("row");
    const warningsCell = getWarningsCell(row);
    const warningBadge = within(warningsCell).getByRole("status", {
      name: /2 warnings?/i,
    });

    expect(warningBadge).toHaveTextContent("2");
    expect(warningBadge.className).toContain("inline-flex");

    const infoIcon = within(warningBadge).getByTestId("info-icon");
    expect(infoIcon).toHaveAttribute("aria-hidden", "true");
    expect(infoIcon.getAttribute("class")).toContain("text-info-9");

    const warningTooltip = within(warningsCell)
      .getAllByTestId("tooltip-content")
      .find((tooltip) => within(tooltip).queryByText("2 warnings"));

    expect(warningTooltip).toBeTruthy();
    if (warningTooltip) {
      expect(within(warningTooltip).getByText("2 warnings")).toBeTruthy();
      expect(
        within(warningTooltip).getByText(
          "Provider warning (tool_definitions: lookup_profile)",
        ),
      ).toBeTruthy();
    }
  });

  it("shows both regression and warning badges in the merged inline-flex container when both are present", () => {
    const run = makeRun({
      id: "surface_both",
      regression_count: 3,
      warnings: [makeWarning("Both badges warning")],
    });

    mocks.runRegressionsById[run.id] = { issues: [] };

    renderSurfaceRunRow(run);

    const row = screen.getByRole("row");
    const warningsCell = getWarningsCell(row);
    const warningBadge = within(warningsCell).getByRole("status", {
      name: /1 warnings?/i,
    });

    expect(within(warningsCell).getAllByTestId("alert-triangle-icon").length).toBeGreaterThan(0);
    expect(within(warningsCell).getByText("3")).toBeTruthy();
    expect(mocks.runRegressionCalls).toContain(run.id);

    const mergedBadgesContainer = warningsCell.querySelector("span.inline-flex.items-center.gap-2");
    expect(mergedBadgesContainer).toBeTruthy();
    expect(mergedBadgesContainer).toContainElement(warningBadge);
  });

  it("shows a dash when regression_count and warnings are both empty", () => {
    renderSurfaceRunRow(makeRun({
      id: "surface_none",
      regression_count: 0,
      warnings: [],
    }));

    const row = screen.getByRole("row");
    const warningsCell = getWarningsCell(row);

    expect(within(warningsCell).getByText("—")).toBeTruthy();
    expect(within(warningsCell).queryByRole("status", { name: /warnings?/i })).toBeNull();
    expect(within(warningsCell).queryByTestId("alert-triangle-icon")).toBeNull();
    expect(within(warningsCell).queryByTestId("info-icon")).toBeNull();
  });
});

describe("RUN-844 SurfaceRunsTable header", () => {
  it("uses Warnings as the merged column header and does not render Regr", () => {
    render(
      <SurfaceRunsTable
        runs={[makeRun({ id: "surface_header" })]}
        onRowClick={mocks.onSelect}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Warnings" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "Regr" })).toBeNull();
  });
});
