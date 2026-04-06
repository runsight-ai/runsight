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
      created_at: 1_774_407_199,
    },
  ],
  simulationRun: {
    id: "run_research_sim_8",
    workflow_id: "wf_research",
    workflow_name: "Research & Review (Sim)",
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
    eval_pass_pct: 88,
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
  attentionItems: {
    items: [] as Array<Record<string, unknown>>,
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

function buildRunList(items: Array<Record<string, unknown>>) {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 20,
  };
}

function getSearchParam(params: unknown): string | null {
  if (params instanceof URLSearchParams) {
    return params.get("search") ?? params.get("query");
  }

  if (params && typeof params === "object") {
    const record = params as Record<string, unknown>;

    if (typeof record.search === "string") {
      return record.search;
    }

    if (typeof record.query === "string") {
      return record.query;
    }
  }

  return null;
}

function findSourceSelectOption(label: "All runs" | "Production runs") {
  return (
    screen.queryByRole("option", { name: label }) ??
    screen.queryByRole("menuitemradio", { name: label }) ??
    screen.getByText(label)
  );
}

vi.mock("@/queries/runs", () => ({
  useRuns: (params?: unknown) => {
    mocks.runsQueryCalls.push(params);
    const requestedSources = normalizeSources(params);
    const items =
      requestedSources.length === 0
        ? [...mocks.productionRuns, mocks.simulationRun]
        : [...mocks.productionRuns];

    return {
      data: mocks.runsQueryState.data ?? buildRunList(items),
      isLoading: mocks.runsQueryState.isLoading,
      error: mocks.runsQueryState.error,
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
  useAttentionItems: () => ({ data: mocks.attentionItems }),
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

// /runs/:id now renders HistoricalRunRoute which uses WorkflowSurface
vi.mock("@/features/canvas/WorkflowSurface", () => ({
  WorkflowSurface: () =>
    React.createElement(RouteEcho, { label: "run-detail" }),
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
  mocks.attentionItems.items = [];
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
    .map((row) => within(row).getAllByRole("cell")[1]?.textContent ?? "");
}

describe("RUN-487 canonical /runs page", () => {
  it("autofocuses the Search runs input when the runs page loads", async () => {
    await renderRunsRoute("/runs");

    const searchInput = await screen.findByRole("searchbox", { name: "Search runs" });

    expect(document.activeElement).toBe(searchInput);
  });

  it("renders the canonical runs page at /runs with All runs selected by default", async () => {
    await renderRunsRoute("/runs");

    expect(await screen.findByRole("heading", { name: "Runs" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: /runs/i })).toBeNull();
    expect(screen.getByLabelText("Filter runs by source").textContent).toContain(
      "All runs",
    );
    expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([]);

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Source" })).toBeTruthy();
    expect(screen.getByText("simulation")).toBeTruthy();
    expect(findRunRow("Research & Review (Sim)")?.textContent).toContain("88%");
  });

  it("switches to Production runs, adds the source filter, and hides simulation rows", async () => {
    const { user } = await renderRunsRoute("/runs");

    await user.click(await screen.findByLabelText("Filter runs by source"));
    await screen.findByText("Production runs");
    await user.click(findSourceSelectOption("Production runs"));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([
        "manual",
        "schedule",
        "webhook",
      ]);
    });

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Source" })).toBeTruthy();
    expect(screen.queryByText("simulation")).toBeNull();
  });

  it("keeps search client-side after switching to Production runs", async () => {
    const { user } = await renderRunsRoute("/runs");

    await user.click(await screen.findByLabelText("Filter runs by source"));
    await screen.findByText("Production runs");
    await user.click(findSourceSelectOption("Production runs"));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([
        "manual",
        "schedule",
        "webhook",
      ]);
    });

    await user.clear(screen.getByRole("searchbox", { name: "Search runs" }));
    await user.type(screen.getByRole("searchbox", { name: "Search runs" }), "content");

    const finalRequest = mocks.runsQueryCalls.at(-1);

    expect(normalizeSources(finalRequest)).toEqual([
      "manual",
      "schedule",
      "webhook",
    ]);
    expect(getSearchParam(finalRequest)).toBeNull();
    expect(screen.queryByText("Research & Review")).toBeNull();
    expect(screen.getByText("Content Pipeline")).toBeTruthy();
  });

  it("treats special characters literally in runs search", async () => {
    const { user } = await renderRunsRoute("/runs");
    const searchInput = await screen.findByRole("searchbox", { name: "Search runs" });

    await user.type(searchInput, "&");

    expect(screen.getByText("Research & Review")).toBeTruthy();
    expect(screen.queryByText("Content Pipeline")).toBeNull();
    expect(screen.queryByText("Daily Digest")).toBeNull();
    expect(getSearchParam(mocks.runsQueryCalls.at(-1))).toBeNull();
  });

  it("keeps null eval values sorted last in both ascending and descending eval sorts", async () => {
    const { user } = await renderRunsRoute("/runs");
    const evalHeader = await screen.findByRole("columnheader", { name: "Eval" });

    await user.click(evalHeader);
    const ascendingOrder = getVisibleWorkflowOrder();

    await user.click(screen.getByRole("columnheader", { name: "Eval" }));
    const descendingOrder = getVisibleWorkflowOrder();

    const nullEvalWorkflow = "Daily Digest";

    expect({
      ascendingLast: ascendingOrder.at(-1) === nullEvalWorkflow,
      descendingLast: descendingOrder.at(-1) === nullEvalWorkflow,
    }).toEqual({
      ascendingLast: true,
      descendingLast: true,
    });
  });

  it("resets search, filter, and sort state after leaving and re-entering the runs page", async () => {
    const { router, user } = await renderRunsRoute("/runs");

    await user.click(await screen.findByLabelText("Filter runs by source"));
    await screen.findByText("Production runs");
    await user.click(findSourceSelectOption("Production runs"));
    await user.type(screen.getByRole("searchbox", { name: "Search runs" }), "content");
    await user.click(screen.getByRole("columnheader", { name: "Eval" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs");
      expect(screen.getByRole("columnheader", { name: "Eval" }).getAttribute("aria-sort")).toBe(
        "ascending",
      );
      expect(screen.getByLabelText("Filter runs by source").textContent).toContain(
        "Production runs",
      );
    });

    await router.navigate("/runs/run_research_7");
    await screen.findByText("run-detail:/runs/run_research_7");

    await router.navigate("/runs");
    await screen.findByRole("heading", { name: "Runs" });

    expect(
      (
        screen.getByRole("searchbox", {
          name: "Search runs",
        }) as HTMLInputElement
      ).value,
    ).toBe("");
    expect(screen.getByLabelText("Filter runs by source").textContent).toContain("All runs");
    expect(screen.getByRole("columnheader", { name: "Started" }).getAttribute("aria-sort")).toBe(
      "descending",
    );
  });

  it("opens /runs/:id when the user activates a run row", async () => {
    const { router, user } = await renderRunsRoute("/runs");
    const researchRow = await waitFor(() => {
      const row = findRunRow("Research & Review");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    await user.click(researchRow);

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs/run_research_7");
    });
  });

  it("opens /runs/:id when the user activates the workflow name", async () => {
    const { router, user } = await renderRunsRoute("/runs");
    const researchRow = await waitFor(() => {
      const row = findRunRow("Research & Review");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    await user.click(within(researchRow).getByText("Research & Review"));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs/run_research_7");
    });
  });

  it("shows commit unavailable instead of 'uncommitted' when a historical run has no commit_sha", async () => {
    mocks.runsQueryState.data = buildRunList([
      {
        ...mocks.productionRuns[0],
        id: "run_missing_sha",
        workflow_name: "Missing Commit",
        commit_sha: null,
      },
    ]);

    await renderRunsRoute("/runs");

    const missingRow = await waitFor(() => {
      const row = findRunRow("Missing Commit");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    expect(within(missingRow).getByLabelText("Commit unavailable")).toBeTruthy();
    expect(within(missingRow).queryByText("uncommitted")).toBeNull();
  });
});
