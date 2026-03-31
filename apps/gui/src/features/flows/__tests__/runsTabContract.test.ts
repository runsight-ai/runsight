// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";

const mocks = vi.hoisted(() => ({
  runs: [
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

    return {
      data: mocks.runsQueryState.data,
      isLoading: mocks.runsQueryState.isLoading,
      error: mocks.runsQueryState.error,
      refetch: mocks.refetchRuns,
    };
  },
}));

function loadFlowsPage() {
  return import("../FlowsPage").then((module) => module.Component ?? module.FlowsPage);
}

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

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  mocks.refetchRuns.mockReset();
  mocks.createWorkflow.mockReset();
  mocks.createWorkflowAsync.mockReset();
  mocks.deleteWorkflow.mockReset();
  mocks.runsQueryCalls.length = 0;
  mocks.runsQueryState.data = {
    items: mocks.runs,
    total: mocks.runs.length,
    offset: 0,
    limit: 20,
  };
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

    await user.click(await screen.findByText("Research & Review"));

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
