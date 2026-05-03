// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import type { RunResponse } from "@runsight/shared/zod";

const mocks = vi.hoisted(() => ({
  onOpen: vi.fn(),
  runsQueryCalls: [] as unknown[],
  refetchRuns: vi.fn(),
  runs: [] as RunResponse[],
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

function buildRunList(items: RunResponse[]) {
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
    const runs =
      requestedSources.length === 0
        ? mocks.runs
        : mocks.runs.filter((run) => requestedSources.includes(run.source));

    return {
      data: buildRunList(runs),
      isLoading: false,
      error: null,
      refetch: mocks.refetchRuns,
    };
  },
  useRunRegressions: () => ({
    data: undefined,
  }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: { items: [] },
    isLoading: false,
    error: null,
  }),
}));

import { RunRow } from "../RunRow";
import { RunsTab } from "../RunsTab";

function makeRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return {
    id: "run_940",
    workflow_id: "wf_940",
    workflow_name: "API Source Flow",
    status: "completed",
    started_at: 1_774_414_400,
    completed_at: 1_774_414_412,
    duration_seconds: 12,
    total_cost_usd: 0.04,
    total_tokens: 1200,
    created_at: 1_774_414_399,
    branch: "main",
    source: "manual",
    commit_sha: "f078f13deadbeef",
    run_number: 7,
    eval_pass_pct: 92,
    eval_score_avg: null,
    regression_count: 0,
    regression_types: [],
    warnings: [],
    node_summary: null,
    parent_run_id: null,
    root_run_id: null,
    depth: 0,
    workflow_inputs: null,
    workflow_input_schema: null,
    ...overrides,
  };
}

function renderRows(runs: RunResponse[]) {
  render(
    <table>
      <tbody>
        {runs.map((run) => (
          <RunRow key={run.id} run={run} onOpen={mocks.onOpen} />
        ))}
      </tbody>
    </table>,
  );
}

function getSourceCell(row: HTMLElement): HTMLElement {
  const cell = within(row).getAllByRole("cell")[4];
  expect(cell).toBeTruthy();
  return cell;
}

function renderRunsTab() {
  render(
    <MemoryRouter>
      <RunsTab
        RowComponent={RunRow}
        workflowFilter={null}
        attentionOnly={false}
        activeOnly={false}
        onWorkflowFilterChange={vi.fn()}
        onAttentionFilterChange={vi.fn()}
        onActiveFilterChange={vi.fn()}
        onClearFilters={vi.fn()}
      />
    </MemoryRouter>,
  );
}

function findSourceSelectOption(label: "All runs" | "Production runs") {
  return (
    screen.queryByRole("option", { name: label }) ??
    screen.queryByRole("menuitemradio", { name: label }) ??
    screen.getByText(label)
  );
}

beforeEach(() => {
  mocks.onOpen.mockReset();
  mocks.runsQueryCalls.length = 0;
  mocks.refetchRuns.mockReset();
  mocks.runs = [];
});

afterEach(() => {
  cleanup();
});

describe("api run source UI", () => {
  it("renders api source runs as API without leaking request provenance metadata", () => {
    renderRows([
      makeRun({
        id: "run_api_940",
        workflow_name: "API Intake",
        source: "api",
        source_correlation_id: "req-run-940",
        source_metadata: {
          authorization: "Bearer secret-run-940",
          idempotency_key: "idem-key-run-940",
        },
      } as Partial<RunResponse>),
    ]);

    const row = screen.getByRole("row");
    const sourceCell = getSourceCell(row);
    const apiBadge = within(sourceCell).getByText("API");

    expect(sourceCell.textContent).toBe("API");
    expect(apiBadge.className).toContain("whitespace-nowrap");

    const renderedText = row.textContent ?? "";
    expect(renderedText).not.toContain("req-run-940");
    expect(renderedText).not.toContain("idem-key-run-940");
    expect(renderedText).not.toContain("Bearer");
    expect(renderedText).not.toContain("secret-run-940");
  });

  it("keeps existing manual and simulation source labels unchanged", () => {
    renderRows([
      makeRun({ id: "run_manual", source: "manual" }),
      makeRun({ id: "run_simulation", source: "simulation" }),
    ]);

    const [manualRow, simulationRow] = screen.getAllByRole("row");
    expect(getSourceCell(manualRow).textContent).toBe("manual");
    expect(getSourceCell(simulationRow).textContent).toBe("simulation");
  });

  it("keeps unknown source values visible on the safe fallback path", () => {
    renderRows([
      makeRun({
        id: "run_partner_unknown",
        source: "partner_console",
      }),
    ]);

    expect(getSourceCell(screen.getByRole("row")).textContent).toBe("partner_console");
  });

  it("includes api in the Production runs source filter", async () => {
    const user = userEvent.setup();
    renderRunsTab();

    await user.click(screen.getByLabelText("Filter runs by source"));
    await screen.findByText("Production runs");
    await user.click(findSourceSelectOption("Production runs"));

    await waitFor(() => {
      expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([
        "api",
        "manual",
        "schedule",
        "webhook",
      ]);
    });
  });

  it("shows filtered-empty copy instead of first-run copy when source filtering hides runs", async () => {
    const user = userEvent.setup();
    mocks.runs = [makeRun({ id: "run_simulation_only", source: "simulation" })];
    renderRunsTab();

    await user.click(screen.getByLabelText("Filter runs by source"));
    await screen.findByText("Production runs");
    await user.click(findSourceSelectOption("Production runs"));

    expect(await screen.findByText("No matching runs")).toBeTruthy();
    expect(screen.queryByText("No runs yet")).toBeNull();
  });

  it("clears local source and search filters from the RunsTab empty state", async () => {
    const user = userEvent.setup();
    mocks.runs = [makeRun({ id: "run_clear_filters", workflow_name: "Visible After Clear" })];
    renderRunsTab();

    await user.click(screen.getByLabelText("Filter runs by source"));
    await screen.findByText("Production runs");
    await user.click(findSourceSelectOption("Production runs"));
    await user.type(screen.getByRole("searchbox", { name: "Search runs" }), "missing");

    expect(await screen.findByText("No matching runs")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Filter runs by source").textContent).toContain("All runs");
    });
    expect((screen.getByRole("searchbox", { name: "Search runs" }) as HTMLInputElement).value).toBe(
      "",
    );
    expect(screen.getByText("Visible After Clear")).toBeTruthy();
    expect(normalizeSources(mocks.runsQueryCalls.at(-1))).toEqual([]);
  });
});
