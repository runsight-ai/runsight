// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Outlet } from "react-router";

type RunFixture = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  run_number: number;
  status: string;
  commit_sha: string;
  source: string;
  branch: string;
  started_at: number;
  completed_at: number;
  duration_seconds: number;
  total_cost_usd: number;
  total_tokens: number;
  eval_pass_pct: number | null;
  regression_count: number | null;
  created_at: number;
};

const mocks = vi.hoisted(() => ({
  runs: [] as RunFixture[],
  runsQueryCalls: [] as unknown[],
  refetchRuns: vi.fn(),
}));

function makeRun(overrides: Partial<RunFixture>): RunFixture {
  return {
    id: "run_default",
    workflow_id: "wf_default",
    workflow_name: "Default Workflow",
    run_number: 1,
    status: "completed",
    commit_sha: "f078f13deadbeef",
    source: "manual",
    branch: "main",
    started_at: 1_774_414_400,
    completed_at: 1_774_414_412,
    duration_seconds: 12.3,
    total_cost_usd: 0.04,
    total_tokens: 1200,
    eval_pass_pct: 92,
    regression_count: 0,
    created_at: 1_774_414_399,
    ...overrides,
  };
}

function buildRunList(items: RunFixture[]) {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 20,
  };
}

vi.mock("@/queries/runs", () => ({
  useRuns: (params?: unknown) => {
    mocks.runsQueryCalls.push(params);

    return {
      data: buildRunList([...mocks.runs]),
      isLoading: false,
      error: null,
      refetch: mocks.refetchRuns,
    };
  },
  useRunRegressions: (runId?: string) => ({
    data: runId
      ? {
          count: 0,
          issues: [],
        }
      : undefined,
  }),
}));

vi.mock("@/queries/dashboard", () => ({
  useAttentionItems: () => ({ data: { items: [] } }),
}));

vi.mock("@runsight/ui/skeleton", () => ({
  Skeleton: (props: Record<string, unknown>) =>
    React.createElement("div", {
      ...props,
      "data-testid": "shared-skeleton",
      "data-slot": "skeleton",
    }),
}));

vi.mock("../../../routes/guards", () => ({
  createSetupGuardLoader: () => async () => null,
  createReverseGuardLoader: () => async () => null,
}));

vi.mock("../../../routes/layouts/ShellLayout", () => ({
  ShellLayout: () => React.createElement(Outlet),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: {
      items: [
        { id: "wf_research", name: "Research & Review" },
        { id: "wf_pipeline", name: "Content Pipeline" },
        { id: "wf_docs", name: "Daily Digest" },
      ],
      total: 3,
    },
    isLoading: false,
    error: null,
  }),
  useWorkflowRegressions: () => ({ data: undefined }),
}));

vi.mock("@/lib/queryClient", () => ({
  queryClient: {},
}));

let activeRouter: { dispose?: () => void; state?: { location: Location } } | null = null;

afterEach(() => {
  cleanup();
  activeRouter?.dispose?.();
  activeRouter = null;
  window.history.pushState({}, "", "/");
});

beforeEach(() => {
  mocks.runs = [
    makeRun({
      id: "run_research_7",
      workflow_id: "wf_research",
      workflow_name: "Research & Review",
      run_number: 7,
      regression_count: 3,
      started_at: 1_774_414_400,
    }),
    makeRun({
      id: "run_pipeline_12",
      workflow_id: "wf_pipeline",
      workflow_name: "Content Pipeline",
      run_number: 12,
      status: "failed",
      source: "webhook",
      eval_pass_pct: 75,
      regression_count: 0,
      started_at: 1_774_410_800,
    }),
    makeRun({
      id: "run_digest_3",
      workflow_id: "wf_docs",
      workflow_name: "Daily Digest",
      run_number: 3,
      source: "schedule",
      eval_pass_pct: null,
      regression_count: null,
      started_at: 1_774_407_200,
    }),
  ];
  mocks.runsQueryCalls.length = 0;
  mocks.refetchRuns.mockReset();
});

async function renderRunsRoute(initialPath = "/runs") {
  vi.resetModules();
  window.history.pushState({}, "", initialPath);

  const { RouterProvider } = await import("react-router");
  const { router } = await import("../../../routes");

  activeRouter = router;
  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

function getVisibleColumnHeaders() {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("columnheader")
    .map((th) => th.textContent?.trim() ?? "");
}

function getVisibleWorkflowOrder() {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[1]?.textContent ?? "");
}

function findRunRow(workflowName: string) {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .find((row) => within(row).queryByText(workflowName));
}

function getCellsInColumn(columnName: string): HTMLElement[] {
  const table = screen.getByRole("table");
  const headers = within(table).getAllByRole("columnheader");
  const colIndex = headers.findIndex((th) => th.textContent?.trim() === columnName);

  if (colIndex === -1) {
    return [];
  }

  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[colIndex])
    .filter(Boolean);
}

describe("runs warnings column display", () => {
  it('renders a "Warnings" column header after Eval', async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      expect(screen.getByRole("table")).toBeTruthy();
    });

    const headers = getVisibleColumnHeaders();
    const evalIndex = headers.indexOf("Eval");
    expect(evalIndex).toBeGreaterThanOrEqual(0);
    expect(headers[evalIndex + 1]).toBe("Warnings");
  });

  it("displays regression count with warning icon when regression_count is positive", async () => {
    await renderRunsRoute("/runs");

    const researchRow = await waitFor(() => {
      const row = findRunRow("Research & Review");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    expect(within(researchRow).getByText("3", { exact: true })).toBeTruthy();
    expect(researchRow.querySelector("svg")).toBeTruthy();
  });

  it("displays a dash for zero and null regression counts", async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      expect(findRunRow("Daily Digest")).toBeTruthy();
    });

    const warningsCells = getCellsInColumn("Warnings");
    expect(warningsCells[1].textContent).toBe("—");
    expect(warningsCells[2].textContent).toBe("—");
  });
});

describe("runs warnings column sorting", () => {
  it("toggles Warnings sort direction from ascending to descending", async () => {
    const { user } = await renderRunsRoute("/runs");

    const warningsHeader = await waitFor(() => {
      const header = screen.getByRole("columnheader", { name: "Warnings" });
      expect(header).toBeTruthy();
      return header;
    });

    await user.click(warningsHeader);
    expect(warningsHeader.getAttribute("aria-sort")).toBe("ascending");

    await user.click(warningsHeader);
    expect(warningsHeader.getAttribute("aria-sort")).toBe("descending");
  });

  it("sorts runs by combined warning and regression count", async () => {
    const { user } = await renderRunsRoute("/runs");

    const warningsHeader = await waitFor(() => {
      const header = screen.getByRole("columnheader", { name: "Warnings" });
      expect(header).toBeTruthy();
      return header;
    });

    await user.click(warningsHeader);
    expect(getVisibleWorkflowOrder()).toEqual([
      "Content Pipeline",
      "Daily Digest",
      "Research & Review",
    ]);

    await user.click(warningsHeader);
    expect(getVisibleWorkflowOrder()).toEqual([
      "Research & Review",
      "Content Pipeline",
      "Daily Digest",
    ]);
  });
});
