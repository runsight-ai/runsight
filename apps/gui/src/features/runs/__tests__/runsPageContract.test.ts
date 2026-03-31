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

vi.mock("@runsight/ui/skeleton", () => ({
  Skeleton: (props: Record<string, unknown>) =>
    React.createElement("div", {
      ...props,
      "data-testid": "shared-skeleton",
      "data-slot": "skeleton",
    }),
}));

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  mocks.runsQueryCalls.length = 0;
  mocks.refetchRuns.mockReset();
  mocks.runsQueryState.data = null;
  mocks.runsQueryState.isLoading = false;
  mocks.runsQueryState.error = null;
});

async function renderRunsPage(initialEntry = "/runs") {
  const { Component: RunList } = await import("../RunList");
  const router = createMemoryRouter(
    [
      { path: "/runs", element: React.createElement(RunList) },
      { path: "/runs/:id", element: React.createElement("div", null, "Run detail") },
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

describe("RUN-487 canonical /runs page", () => {
  it("renders the canonical runs page at /runs with the production-only source filter by default", async () => {
    await renderRunsPage("/runs");

    expect(await screen.findByRole("heading", { name: "Runs" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: /runs/i })).toBeNull();
    expect(screen.getByLabelText("Filter runs by source").textContent).toContain(
      "Production runs",
    );
    expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([
      "manual",
      "schedule",
      "webhook",
    ]);

    const table = await screen.findByRole("table");
    expect(within(table).queryByRole("columnheader", { name: "Source" })).toBeNull();
  });

  it("switches to All runs without a source filter and reveals the Source column", async () => {
    const { user } = await renderRunsPage("/runs");

    await user.click(await screen.findByLabelText("Filter runs by source"));
    await user.click(await screen.findByText("All runs"));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([]);
    });

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Source" })).toBeTruthy();
    expect(screen.getByText("simulation")).toBeTruthy();
  });

  it("keeps search client-side on the canonical /runs page", async () => {
    const { user } = await renderRunsPage("/runs");

    await user.click(await screen.findByLabelText("Filter runs by source"));
    await user.click(await screen.findByText("All runs"));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([]);
    });

    await user.clear(screen.getByRole("searchbox", { name: "Search runs" }));
    await user.type(screen.getByRole("searchbox", { name: "Search runs" }), "content");

    const finalRequest = mocks.runsQueryCalls.at(-1);

    expect(normalizeSources(finalRequest)).toEqual([]);
    expect(getSearchParam(finalRequest)).toBeNull();
    expect(screen.queryByText("Research & Review")).toBeNull();
    expect(screen.getByText("Content Pipeline")).toBeTruthy();
  });

  it("opens /runs/:id when the user activates a run row", async () => {
    const { router, user } = await renderRunsPage("/runs");
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

  it("opens /workflows/:id/edit when the user activates the workflow name", async () => {
    const { router, user } = await renderRunsPage("/runs");
    const researchRow = await waitFor(() => {
      const row = findRunRow("Research & Review");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    await user.click(within(researchRow).getByText("Research & Review"));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
    });
  });
});
