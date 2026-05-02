import React from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

export type RunFixture = Record<string, unknown>;

export type RunsQueryState = {
  data: {
    items: RunFixture[];
    total: number;
    offset: number;
    limit: number;
  } | null;
  isLoading: boolean;
  error: Error | null;
};

type ActiveRouter = {
  dispose?: () => void;
  state?: { location: Location };
};

let activeRouter: ActiveRouter | null = null;

export function buildProductionRuns(): RunFixture[] {
  return [
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
  ];
}

export function buildSimulationRun(): RunFixture {
  return {
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
  };
}

export function buildRunsQueryState(): RunsQueryState {
  return {
    data: null,
    isLoading: false,
    error: null,
  };
}

export function normalizeSources(params: unknown): string[] {
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

export function buildRunList(items: RunFixture[]) {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 20,
  };
}

export function getSearchParam(params: unknown): string | null {
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

export function findSourceSelectOption(label: "All runs" | "Production runs") {
  return (
    screen.queryByRole("option", { name: label }) ??
    screen.queryByRole("menuitemradio", { name: label }) ??
    screen.getByText(label)
  );
}

export async function renderRunsRoute(initialPath = "/runs") {
  vi.resetModules();
  window.history.pushState({}, "", initialPath);

  const { RouterProvider } = await import("react-router");
  const { router } = await import("../../../routes");

  activeRouter = router;
  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

export function cleanupRunsRoute() {
  cleanup();
  activeRouter?.dispose?.();
  activeRouter = null;
  window.history.pushState({}, "", "/");
}

export function findRunRow(workflowName: string) {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .find((row) => within(row).queryByText(workflowName));
}

export function getVisibleWorkflowOrder() {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[1]?.textContent ?? "");
}
