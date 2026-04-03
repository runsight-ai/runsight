// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Outlet, useLocation } from "react-router";

const mocks = vi.hoisted(() => ({
  productionRuns: [
    {
      id: "run_research_7",
      workflow_id: "wf_research",
      workflow_name: "Research & Review",
      run_number: 7,
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
      regression_count: 3,
      created_at: 1_774_414_399,
    },
    {
      id: "run_pipeline_12",
      workflow_id: "wf_pipeline",
      workflow_name: "Content Pipeline",
      run_number: 12,
      status: "failed",
      commit_sha: "a463263feedbeef",
      source: "webhook",
      branch: "main",
      started_at: 1_774_410_800,
      completed_at: 1_774_410_808,
      duration_seconds: 8.1,
      total_cost_usd: 0.02,
      total_tokens: 900,
      eval_pass_pct: 75,
      regression_count: 0,
      created_at: 1_774_410_799,
    },
    {
      id: "run_digest_3",
      workflow_id: "wf_docs",
      workflow_name: "Daily Digest",
      run_number: 3,
      status: "completed",
      commit_sha: "705ebea99999999",
      source: "schedule",
      branch: "main",
      started_at: 1_774_407_200,
      completed_at: 1_774_407_209,
      duration_seconds: 9.2,
      total_cost_usd: 0.03,
      total_tokens: 640,
      eval_pass_pct: null,
      regression_count: null,
      created_at: 1_774_407_199,
    },
  ],
  simulationRun: {
    id: "run_research_sim_8",
    workflow_id: "wf_research",
    workflow_name: "Research & Review",
    run_number: 8,
    status: "running",
    commit_sha: "9c1deaf77777777",
    source: "simulation",
    branch: "sim/research-review/20260331/abc12",
    started_at: 1_774_416_200,
    completed_at: null,
    duration_seconds: 4.8,
    total_cost_usd: 0.01,
    total_tokens: 320,
    eval_pass_pct: null,
    regression_count: 1,
    created_at: 1_774_416_199,
  },
  runsQueryCalls: [] as unknown[],
  refetchRuns: vi.fn(),
  runsQueryState: {
    data: null as {
      items: Array<Record<string, unknown>>;
      total: number;
      offset: number;
      limit: number;
    } | null,
    isLoading: false,
    error: null as Error | null,
  },
}));

function normalizeSources(params: unknown): string[] {
  if (params instanceof URLSearchParams) {
    return params.getAll("source").sort();
  }

  if (
    params &&
    typeof params === "object" &&
    "source" in params &&
    Array.isArray((params as { source?: unknown }).source)
  ) {
    return [...((params as { source: string[] }).source)].sort();
  }

  return [];
}

function getWorkflowId(params: unknown): string | null {
  if (params instanceof URLSearchParams) {
    return params.get("workflow_id");
  }

  if (params && typeof params === "object") {
    const record = params as Record<string, unknown>;
    if (typeof record.workflow_id === "string") {
      return record.workflow_id;
    }
  }

  return null;
}

function buildRunList(items: Array<Record<string, unknown>>) {
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
    const requestedSources = normalizeSources(params);
    const workflowId = getWorkflowId(params);

    let items =
      requestedSources.length === 0
        ? [...mocks.productionRuns, mocks.simulationRun]
        : [...mocks.productionRuns];

    if (workflowId) {
      items = items.filter(
        (run) => run.workflow_id === workflowId,
      );
    }

    return {
      data: mocks.runsQueryState.data ?? buildRunList(items),
      isLoading: mocks.runsQueryState.isLoading,
      error: mocks.runsQueryState.error,
      refetch: mocks.refetchRuns,
    };
  },
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

vi.mock("@/lib/queryClient", () => ({
  queryClient: {},
}));

function RouteEcho({ label }: { label: string }) {
  const location = useLocation();
  return React.createElement(
    "div",
    null,
    `${label}:${location.pathname}${location.search}`,
  );
}

vi.mock("@/features/runs/RunDetail", () => ({
  Component: () => React.createElement(RouteEcho, { label: "run-detail" }),
}));

vi.mock("@/features/canvas/CanvasPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "workflow-editor" }),
}));

let activeRouter: { dispose?: () => void; state?: { location: Location } } | null = null;

afterEach(() => {
  cleanup();
  activeRouter?.dispose?.();
  activeRouter = null;
  window.history.pushState({}, "", "/");
});

beforeEach(() => {
  mocks.runsQueryCalls.length = 0;
  mocks.refetchRuns.mockReset();
  mocks.runsQueryState.data = null;
  mocks.runsQueryState.isLoading = false;
  mocks.runsQueryState.error = null;
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

function findRunRow(workflowName: string) {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .find((row) => within(row).queryByText(workflowName));
}

function getVisibleWorkflowOrder() {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => {
      const cells = within(row).getAllByRole("cell");
      const workflowCell = cells[1];
      const button = within(workflowCell).queryByRole("button");
      return button?.textContent ?? workflowCell.textContent ?? "";
    });
}

describe("RUN-562 workflow filter via ?workflow query param", () => {
  it("passes workflow_id to useRuns when ?workflow param is present", async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      const lastCall = mocks.runsQueryCalls.at(-1);
      expect(getWorkflowId(lastCall)).toBe("wf_research");
    });
  });

  it("shows only runs matching the filtered workflow_id", async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      expect(screen.getByText("Research & Review")).toBeTruthy();
    });

    expect(screen.queryByText("Content Pipeline")).toBeNull();
    expect(screen.queryByText("Daily Digest")).toBeNull();
  });

  it("renders page header as 'Runs — [Name]' when filtered by workflow", async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading.textContent).toContain("Runs");
    expect(heading.textContent).toContain("Research & Review");
  });

  it("renders a clear (×) button in the header when filtered", async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      expect(screen.getByText("Research & Review")).toBeTruthy();
    });

    const clearButton = screen.getByRole("button", { name: /clear.*filter/i });
    expect(clearButton).toBeTruthy();
  });

  it("removes ?workflow param and shows all runs when clear button is clicked", async () => {
    const { router, user } = await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      expect(screen.getByText("Research & Review")).toBeTruthy();
    });

    const clearButton = screen.getByRole("button", { name: /clear.*filter/i });
    await user.click(clearButton);

    await waitFor(() => {
      const lastCall = mocks.runsQueryCalls.at(-1);
      expect(getWorkflowId(lastCall)).toBeNull();
    });

    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading.textContent).not.toContain("Research & Review");
    expect(heading.textContent).toContain("Runs");
  });

  it("does not pass workflow_id to useRuns when ?workflow param is absent", async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      const lastCall = mocks.runsQueryCalls.at(-1);
      expect(getWorkflowId(lastCall)).toBeNull();
    });
  });

  it("does not render clear button when no workflow filter is active", async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Runs" })).toBeTruthy();
    });

    expect(screen.queryByRole("button", { name: /clear.*filter/i })).toBeNull();
  });
});

describe("RUN-562 regressions column", () => {
  it("renders a Regr column header in the table", async () => {
    await renderRunsRoute("/runs");

    const table = await screen.findByRole("table");
    const regrHeader = within(table).getByRole("columnheader", { name: "Regr" });
    expect(regrHeader).toBeTruthy();
  });

  it("shows regression count with warning indicator when count > 0", async () => {
    await renderRunsRoute("/runs");

    const researchRow = await waitFor(() => {
      const row = findRunRow("Research & Review");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    const cells = within(researchRow).getAllByRole("cell");
    const regrCell = cells.find((cell) => cell.textContent?.includes("3"));
    expect(regrCell).toBeTruthy();
    expect(regrCell?.textContent).toContain("3");
  });

  it("shows em dash (—) when regression count is 0", async () => {
    await renderRunsRoute("/runs");

    const pipelineRow = await waitFor(() => {
      const row = findRunRow("Content Pipeline");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    const cells = within(pipelineRow).getAllByRole("cell");
    // Regressions column comes after eval column — check for em dash
    const regrCell = cells.find(
      (cell) =>
        cell.textContent === "—" &&
        cell !== cells[0], // skip status cell
    );
    expect(regrCell).toBeTruthy();
  });

  it("shows em dash (—) when regression count is null", async () => {
    await renderRunsRoute("/runs");

    const digestRow = await waitFor(() => {
      const row = findRunRow("Daily Digest");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    // Count the em dash cells — Daily Digest has null eval AND null regressions
    const cells = within(digestRow).getAllByRole("cell");
    const dashCells = cells.filter((cell) => cell.textContent === "—");
    // Should have at least 2 dashes: eval and regressions
    expect(dashCells.length).toBeGreaterThanOrEqual(2);
  });

  it("Regr column is sortable (ascending click sets aria-sort)", async () => {
    const { user } = await renderRunsRoute("/runs");

    const regrHeader = await screen.findByRole("columnheader", { name: "Regr" });
    await user.click(regrHeader);

    expect(regrHeader.getAttribute("aria-sort")).toBe("ascending");
  });

  it("Regr column toggles to descending on second click", async () => {
    const { user } = await renderRunsRoute("/runs");

    const regrHeader = await screen.findByRole("columnheader", { name: "Regr" });
    await user.click(regrHeader);
    await user.click(regrHeader);

    expect(regrHeader.getAttribute("aria-sort")).toBe("descending");
  });

  it("sorts runs by regression count when Regr header is clicked", async () => {
    const { user } = await renderRunsRoute("/runs");

    const regrHeader = await screen.findByRole("columnheader", { name: "Regr" });
    await user.click(regrHeader);

    const order = getVisibleWorkflowOrder();
    // Ascending: 0 (Content Pipeline) first, 3 (Research) second, null (Daily Digest) last
    expect(order[0]).toBe("Content Pipeline");
    expect(order[1]).toBe("Research & Review");
    expect(order.at(-1)).toBe("Daily Digest");
  });

  it("Regr column appears after Eval in column order", async () => {
    await renderRunsRoute("/runs");

    const table = await screen.findByRole("table");
    const headers = within(table).getAllByRole("columnheader");
    const headerLabels = headers.map((h) => h.textContent ?? "");

    const evalIndex = headerLabels.indexOf("Eval");
    const regrIndex = headerLabels.indexOf("Regr");

    expect(evalIndex).toBeGreaterThanOrEqual(0);
    expect(regrIndex).toBe(evalIndex + 1);
  });
});
