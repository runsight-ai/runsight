// @vitest-environment jsdom

import React from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RunResponse } from "@runsight/shared/zod";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  onRowClick: vi.fn(),
  clipboardWriteText: vi.fn().mockResolvedValue(undefined),
  runRegressions: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  })),
}));

vi.mock("@/queries/runs", () => ({
  useRunRegressions: (runId?: string) => {
    mocks.runRegressions(runId ?? "");

    return {
      data: undefined,
      isLoading: false,
      isError: false,
    };
  },
}));

Object.defineProperty(navigator, "clipboard", {
  value: {
    writeText: mocks.clipboardWriteText,
  },
  configurable: true,
});

const { SurfaceRunsTable } = await import("../SurfaceRunsTable");

type WorkflowInputSnapshotEntry = {
  type: string;
  sensitive: boolean;
  source: string;
  value?: unknown;
};

function makeRun(
  overrides: Partial<RunResponse> & {
    workflow_inputs?: Record<string, WorkflowInputSnapshotEntry> | null;
    workflow_input_schema?: Record<string, Record<string, unknown>> | null;
  } = {},
): RunResponse {
  return {
    id: "run_inputs_history",
    workflow_id: "wf_inputs_history",
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
    run_number: 12,
    eval_pass_pct: 95,
    eval_score_avg: 0.95,
    regression_count: 0,
    warnings: [],
    workflow_inputs: null,
    workflow_input_schema: null,
    ...overrides,
  };
}

function renderSurfaceRunsTable(run: RunResponse) {
  render(
    <SurfaceRunsTable
      runs={[run]}
      onRowClick={mocks.onRowClick}
    />,
  );
}

function getDataRow() {
  const rows = screen.getAllByRole("row");
  expect(rows.length).toBeGreaterThan(1);

  const row = rows[1];
  expect(row).toBeTruthy();

  return row;
}

function getCellByColumn(row: HTMLElement, columnName: string): HTMLElement {
  const headerIndex = screen
    .getAllByRole("columnheader")
    .findIndex((header) => header.textContent?.trim() === columnName);

  expect(headerIndex).toBeGreaterThanOrEqual(0);
  const cell = within(row).getAllByRole("cell")[headerIndex];
  expect(cell).toBeTruthy();

  return cell;
}

beforeEach(() => {
  mocks.onRowClick.mockReset();
  mocks.clipboardWriteText.mockReset();
  mocks.runRegressions.mockReset();
  mocks.runRegressions.mockImplementation(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("surface run input cell import safety", () => {
  it("imports the cell renderer when navigator is missing", async () => {
    vi.resetModules();
    vi.stubGlobal("navigator", undefined);

    await expect(import("../SurfaceRunInputsCell")).resolves.toHaveProperty(
      "SurfaceRunInputsCell",
    );
  });
});

describe("surface run input history", () => {
  it("renders api run history source as API without displaying request provenance metadata", () => {
    renderSurfaceRunsTable(
      makeRun({
        id: "surface_api_history_run",
        source: "api",
        source_correlation_id: "req-surface-history",
        source_metadata: {
          authorization: "Bearer surface-history-secret",
          idempotency_key: "idem-surface-history",
        },
      } as Partial<RunResponse>),
    );

    const row = getDataRow();
    const sourceCell = getCellByColumn(row, "Source");
    const apiBadge = within(sourceCell).getByText("API");

    expect(sourceCell.textContent).toBe("API");
    expect(apiBadge.className).toContain("whitespace-nowrap");

    const renderedText = row.textContent ?? "";
    expect(renderedText).not.toContain("req-surface-history");
    expect(renderedText).not.toContain("idem-surface-history");
    expect(renderedText).not.toContain("Bearer");
    expect(renderedText).not.toContain("surface-history-secret");
  });

  it("shows the stored snapshot preview and ignores later workflow schema defaults", () => {
    renderSurfaceRunsTable(
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
        },
        workflow_input_schema: {
          query: {
            type: "string",
            required: true,
            default: "future-default",
            description: "Changed after the run",
            sensitive: false,
          },
        },
      }),
    );

    expect(screen.getByRole("columnheader", { name: /inputs|params/i })).toBeTruthy();

    const row = getDataRow();
    expect(within(row).getByText(/query/i)).toBeTruthy();
    expect(within(row).getByText(/refunds/i)).toBeTruthy();
    expect(within(row).queryByText(/future-default/i)).toBeNull();
  });

  it("opens formatted JSON details and copies safe JSON for JSON and array inputs", async () => {
    const user = userEvent.setup();

    renderSurfaceRunsTable(
      makeRun({
        workflow_inputs: {
          config: {
            type: "json",
            sensitive: false,
            source: "provided",
            value: { mode: "fast", retries: 2 },
          },
          tags: {
            type: "array",
            sensitive: false,
            source: "provided",
            value: ["vip", "priority"],
          },
        },
      }),
    );

    const row = getDataRow();
    const inputsTrigger = within(row).getByRole("button", {
      name: /inputs|params|details|view/i,
    });

    await user.click(inputsTrigger);

    expect(screen.getByText(/"mode":\s*"fast"/)).toBeTruthy();
    expect(screen.getByText(/"retries":\s*2/)).toBeTruthy();
    expect(screen.getByText(/"vip"/)).toBeTruthy();
    expect(screen.getByText(/"priority"/)).toBeTruthy();

    const copyButton = screen.getByRole("button", { name: /copy/i });
    await user.click(copyButton);

    expect(mocks.clipboardWriteText).toHaveBeenCalledTimes(1);
    const copied = String(mocks.clipboardWriteText.mock.calls[0]?.[0] ?? "");

    expect(JSON.parse(copied)).toEqual({
      config: { mode: "fast", retries: 2 },
      tags: ["vip", "priority"],
    });
  });

  it("marks sensitive inputs as sensitive and omits them from copied JSON", async () => {
    const user = userEvent.setup();

    renderSurfaceRunsTable(
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
          api_token: {
            type: "string",
            sensitive: true,
            source: "provided",
          },
        },
      }),
    );

    const row = getDataRow();
    const inputsTrigger = within(row).getByRole("button", {
      name: /inputs|params|details|view/i,
    });

    await user.click(inputsTrigger);

    expect(screen.getByText(/api_token/i)).toBeTruthy();
    expect(screen.getByText(/sensitive|omitted/i)).toBeTruthy();
    expect(screen.queryByText(/undefined|null|secret-token/i)).toBeNull();

    await user.click(screen.getByRole("button", { name: /copy/i }));

    const copied = String(mocks.clipboardWriteText.mock.calls[0]?.[0] ?? "");
    expect(JSON.parse(copied)).toEqual({
      query: "refunds",
    });
    expect(copied).not.toContain("api_token");
  });

  it("shows No inputs when the run snapshot is empty", () => {
    renderSurfaceRunsTable(
      makeRun({
        workflow_inputs: null,
      }),
    );

    expect(screen.getByText(/no inputs/i)).toBeTruthy();
  });
});
