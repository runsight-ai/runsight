// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";

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
    created_at: 1_774_416_199,
  },
  refetchRuns: vi.fn(),
  createWorkflow: vi.fn(),
  createWorkflowAsync: vi.fn(),
  deleteWorkflow: vi.fn(),
  runsQueryCalls: [] as unknown[],
  runsQueryState: {
    data: {
      items: [] as Array<Record<string, unknown>>,
      total: 0,
      offset: 0,
      limit: 20,
    },
    isLoading: false,
    error: null as Error | null,
  },
  workflowsQueryState: {
    data: {
      items: [] as Array<Record<string, unknown>>,
      total: 0,
    },
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
    const search = record.search;
    const query = record.query;

    if (typeof search === "string") {
      return search;
    }

    if (typeof query === "string") {
      return query;
    }
  }

  return null;
}

vi.mock("@/queries/workflows", () => ({
  useCreateWorkflow: () => ({
    mutate: mocks.createWorkflow,
    mutateAsync: mocks.createWorkflowAsync,
    isPending: false,
  }),
  useWorkflows: () => ({
    data: mocks.workflowsQueryState.data,
    isLoading: mocks.workflowsQueryState.isLoading,
    error: mocks.workflowsQueryState.error,
    refetch: vi.fn(),
  }),
  useDeleteWorkflow: () => ({
    mutateAsync: mocks.deleteWorkflow,
    isPending: false,
  }),
}));

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
}));

function loadFlowsPage() {
  return import("../FlowsPage").then((module) => module.Component ?? module.FlowsPage);
}

async function renderFlowsPage(initialEntry: string) {
  const FlowsPage = await loadFlowsPage();
  const router = createMemoryRouter(
    [
      { path: "/flows", element: React.createElement(FlowsPage) },
      {
        path: "/workflows/:id/edit",
        element: React.createElement("div", null, "Workflow editor"),
      },
    ],
    { initialEntries: [initialEntry] },
  );

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

function findEvalValue(row: HTMLElement, value: string) {
  return within(row).queryByText(value) ?? within(row).queryByLabelText(value);
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  mocks.refetchRuns.mockReset();
  mocks.createWorkflow.mockReset();
  mocks.createWorkflowAsync.mockReset();
  mocks.deleteWorkflow.mockReset();
  mocks.runsQueryCalls.length = 0;
  mocks.runsQueryState.data = null as unknown as typeof mocks.runsQueryState.data;
  mocks.runsQueryState.isLoading = false;
  mocks.runsQueryState.error = null;
  mocks.workflowsQueryState.data = {
    items: [],
    total: 0,
  };
  mocks.workflowsQueryState.isLoading = false;
  mocks.workflowsQueryState.error = null;
});

describe("RUN-427 FlowsPage runs tab", () => {
  it("uses /flows?tab=runs as URL-driven state and hides the New Workflow header action", async () => {
    await renderFlowsPage("/flows?tab=runs");

    const runsTab = await screen.findByRole("tab", { name: /^Runs$/i });

    expect(runsTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.queryByRole("button", { name: "New Workflow" })).toBeNull();
    expect(normalizeSources(mocks.runsQueryCalls[0])).toEqual([
      "manual",
      "schedule",
      "webhook",
    ]);
  });

  it("updates the /flows tab query param when the user activates the Runs tab", async () => {
    const { router, user } = await renderFlowsPage("/flows");

    await user.click(screen.getByRole("tab", { name: /^Runs$/i }));

    await waitFor(() => {
      expect(router.state.location.search).toBe("?tab=runs");
    });
  });

  it("renders an 8-column runs table with run_number and eval_pass_pct, including partial rows", async () => {
    await renderFlowsPage("/flows?tab=runs");

    const table = await screen.findByRole("table");
    const headers = within(table).getAllByRole("columnheader").map((header) =>
      header.textContent?.trim(),
    );

    expect(headers).toEqual([
      "Status",
      "Workflow",
      "Run",
      "Commit",
      "Duration",
      "Cost",
      "Eval",
      "Started",
    ]);
    expect(screen.getByText("Research & Review")).toBeTruthy();
    expect(screen.getByText(/#?7/)).toBeTruthy();
    expect(screen.getByText("92%")).toBeTruthy();
    expect(screen.getByText("Daily Digest")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("filters runs by workflow name case-insensitively", async () => {
    const { user } = await renderFlowsPage("/flows?tab=runs");

    await user.type(
      await screen.findByRole("searchbox", { name: "Search runs" }),
      "research",
    );

    expect(screen.getByText("Research & Review")).toBeTruthy();
    expect(screen.queryByText("Content Pipeline")).toBeNull();
    expect(screen.queryByText("Daily Digest")).toBeNull();
  });

  it("marks Started as the default descending sort and lets the user sort by Workflow", async () => {
    const { user } = await renderFlowsPage("/flows?tab=runs");

    const startedHeader = await screen.findByRole("columnheader", { name: "Started" });
    expect(startedHeader.getAttribute("aria-sort")).toBe("descending");

    const workflowHeader = screen.getByRole("columnheader", { name: "Workflow" });
    await user.click(workflowHeader);

    await waitFor(() => {
      expect(workflowHeader.getAttribute("aria-sort")).toBe("ascending");
    });

    const rows = screen.getAllByRole("row");
    expect(rows[1]?.textContent).toContain("Content Pipeline");
  });

  it("opens the workflow editor when a runs-table row is activated", async () => {
    const { router, user } = await renderFlowsPage("/flows?tab=runs");

    const table = await screen.findByRole("table");
    const researchRow = within(table)
      .getAllByRole("row")
      .find((row) => within(row).queryByText("Research & Review"));

    expect(researchRow, "Expected a runs-table row for Research & Review").toBeTruthy();

    await user.click(researchRow!);

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
    });
  });

  it("keeps the Flows header visible while the Runs tab shows five loading skeleton rows", async () => {
    mocks.runsQueryState.isLoading = true;
    mocks.runsQueryState.data = undefined as unknown as typeof mocks.runsQueryState.data;

    await renderFlowsPage("/flows?tab=runs");

    expect(await screen.findByRole("heading", { name: "Flows" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "New Workflow" })).toBeNull();
    expect(screen.getAllByLabelText("Loading run row")).toHaveLength(5);
  });

  it("renders the runs error state with retry guidance", async () => {
    mocks.runsQueryState.error = new Error("connection lost");
    mocks.runsQueryState.data = undefined as unknown as typeof mocks.runsQueryState.data;

    const { user } = await renderFlowsPage("/flows?tab=runs");

    expect(await screen.findByText("Couldn't load runs.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(mocks.refetchRuns).toHaveBeenCalledTimes(1);
  });

  it("renders the empty runs state with a Go to Workflows action", async () => {
    mocks.runsQueryState.data = {
      items: [],
      total: 0,
      offset: 0,
      limit: 20,
    };

    await renderFlowsPage("/flows?tab=runs");

    expect(await screen.findByText("No runs yet")).toBeTruthy();
    expect(
      screen.getByText("Run a workflow to see execution history here."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Go to Workflows" })).toBeTruthy();
  });
});

describe("RUN-416 Runs source filter", () => {
  it("shows an accessible Production runs filter in the runs toolbar and hides the Source column by default", async () => {
    await renderFlowsPage("/flows?tab=runs");

    const searchbox = await screen.findByRole("searchbox", { name: "Search runs" });
    const sourceFilter = screen.getByLabelText("Filter runs by source");

    expect(sourceFilter.textContent).toContain("Production runs");
    expect(
      searchbox.compareDocumentPosition(sourceFilter) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([
      "manual",
      "schedule",
      "webhook",
    ]);

    const table = await screen.findByRole("table");
    expect(within(table).queryByRole("columnheader", { name: "Source" })).toBeNull();
    expect(screen.queryByText("simulation")).toBeNull();
  });

  it("switches to All runs with no source filter, shows the Source column, and keeps search client-side on the returned set", async () => {
    const { user } = await renderFlowsPage("/flows?tab=runs");

    await user.click(screen.getByLabelText("Filter runs by source"));
    await user.click(await screen.findByText("All runs"));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([]);
    });

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Source" })).toBeTruthy();
    expect(screen.getByText("manual")).toBeTruthy();
    expect(screen.getByText("webhook")).toBeTruthy();
    expect(screen.getByText("schedule")).toBeTruthy();
    expect(screen.getByText("simulation")).toBeTruthy();

    await user.clear(screen.getByRole("searchbox", { name: "Search runs" }));
    await user.type(screen.getByRole("searchbox", { name: "Search runs" }), "content");

    const finalRequest = mocks.runsQueryCalls.at(-1);

    expect(normalizeSources(finalRequest)).toEqual([]);
    expect(getSearchParam(finalRequest)).toBeNull();
    expect(screen.queryByText("Research & Review")).toBeNull();
    expect(screen.getByText("Content Pipeline")).toBeTruthy();
    expect(screen.queryByText("Daily Digest")).toBeNull();
    expect(screen.queryByText("simulation")).toBeNull();
  });

  it("renders source badges for manual, webhook, schedule, and simulation, and visually distinguishes simulation rows in all-runs view", async () => {
    const { user } = await renderFlowsPage("/flows?tab=runs");

    await user.click(screen.getByLabelText("Filter runs by source"));
    await user.click(await screen.findByText("All runs"));

    const manualBadge = await screen.findByText("manual");
    const webhookBadge = screen.getByText("webhook");
    const scheduleBadge = screen.getByText("schedule");
    const simulationBadge = screen.getByText("simulation");

    for (const badge of [manualBadge, webhookBadge, scheduleBadge, simulationBadge]) {
      expect(badge.getAttribute("data-slot")).toBe("badge");
      expect(String(badge.className)).not.toBe("");
    }

    const simulationRow = simulationBadge.closest("tr");
    const manualRow = manualBadge.closest("tr");

    expect(simulationRow, "Expected simulation row to render in All runs view").toBeTruthy();
    expect(manualRow, "Expected production row to render in All runs view").toBeTruthy();
    expect(String(simulationRow?.className)).toMatch(/muted|opacity|secondary|tertiary/i);
    expect(simulationRow?.className).not.toBe(manualRow?.className);
  });

  it("keeps the source filter ephemeral when leaving and re-entering the Runs tab", async () => {
    const { user } = await renderFlowsPage("/flows?tab=runs");

    await user.click(screen.getByLabelText("Filter runs by source"));
    await user.click(await screen.findByText("All runs"));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([]);
    });

    await user.click(screen.getByRole("tab", { name: "Workflows" }));
    await user.click(screen.getByRole("tab", { name: /^Runs$/i }));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([
        "manual",
        "schedule",
        "webhook",
      ]);
    });

    expect(screen.getByLabelText("Filter runs by source").textContent).toContain(
      "Production runs",
    );
    expect(screen.queryByRole("columnheader", { name: "Source" })).toBeNull();
  });
});

describe("RUN-428 Runs eval threshold polish", () => {
  it("keeps numeric eval values visible and styles 90 as success, 75 as warning, and 74 as danger", async () => {
    mocks.runsQueryState.data = buildRunList([
      {
        ...mocks.productionRuns[0],
        id: "run_success_90",
        workflow_id: "wf_success",
        workflow_name: "Success Boundary",
        eval_pass_pct: 90,
      },
      {
        ...mocks.productionRuns[1],
        id: "run_warning_75",
        workflow_id: "wf_warning",
        workflow_name: "Warning Boundary",
        eval_pass_pct: 75,
      },
      {
        ...mocks.productionRuns[2],
        id: "run_danger_74",
        workflow_id: "wf_danger",
        workflow_name: "Danger Threshold",
        eval_pass_pct: 74,
      },
      {
        ...mocks.productionRuns[2],
        id: "run_null_eval",
        workflow_id: "wf_none",
        workflow_name: "No Eval Yet",
        eval_pass_pct: null,
      },
    ]);

    await renderFlowsPage("/flows?tab=runs");

    const successRow = findRunRow("Success Boundary");
    const warningRow = findRunRow("Warning Boundary");
    const dangerRow = findRunRow("Danger Threshold");

    expect(successRow, "Expected a row for the 90% eval boundary").toBeTruthy();
    expect(warningRow, "Expected a row for the 75% eval boundary").toBeTruthy();
    expect(dangerRow, "Expected a row for the 74% eval threshold").toBeTruthy();

    const successEval = findEvalValue(successRow!, "90%");
    const warningEval = findEvalValue(warningRow!, "75%");
    const dangerEval = findEvalValue(dangerRow!, "74%");

    expect(successEval, "Expected 90% to stay visible in the eval cell").toBeTruthy();
    expect(warningEval, "Expected 75% to stay visible in the eval cell").toBeTruthy();
    expect(dangerEval, "Expected 74% to stay visible in the eval cell").toBeTruthy();

    expect(String(successEval?.className)).toMatch(/success/i);
    expect(String(warningEval?.className)).toMatch(/warning/i);
    expect(String(dangerEval?.className)).toMatch(/danger/i);
  });

  it("keeps null eval values as a muted dash instead of a numeric badge", async () => {
    mocks.runsQueryState.data = buildRunList([
      {
        ...mocks.productionRuns[2],
        id: "run_null_eval_only",
        workflow_id: "wf_none",
        workflow_name: "No Eval Yet",
        eval_pass_pct: null,
      },
    ]);

    await renderFlowsPage("/flows?tab=runs");

    const nullRow = findRunRow("No Eval Yet");

    expect(nullRow, "Expected a row for the null-eval case").toBeTruthy();

    const nullDash = within(nullRow!).getByText("—");

    expect(nullDash).toBeTruthy();
    expect(within(nullRow!).queryByLabelText(/\d+%/)).toBeNull();
    expect(String(nullDash.className)).toMatch(/muted|secondary/i);
  });
});
