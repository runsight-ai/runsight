import { screen, within } from "@testing-library/react";
import type { RunListResponse, RunResponse } from "@runsight/shared/zod";
import { vi } from "vitest";

type EventSourceListener = (event: MessageEvent) => void;

export const eventSources: MockEventSource[] = [];

export class MockEventSource {
  readonly url: string;
  readonly close = vi.fn();
  private readonly listeners = new Map<string, EventSourceListener[]>();

  constructor(url: string) {
    this.url = url;
    eventSources.push(this);
  }

  addEventListener(type: string, listener: EventSourceListener) {
    const existing = this.listeners.get(type) ?? [];
    this.listeners.set(type, [...existing, listener]);
  }

  emit(type: string, payload: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(payload) }));
    }
  }
}

function makeRun(overrides: Partial<RunResponse>): RunResponse {
  return {
    id: "run_root",
    workflow_id: "wf_root",
    workflow_name: "Root Flow",
    status: "running",
    error: null,
    started_at: 1_710_000_000,
    completed_at: null,
    duration_seconds: null,
    total_cost_usd: 1.25,
    total_tokens: 123,
    created_at: 1_710_000_100,
    branch: "main",
    source: "manual",
    commit_sha: "sha-root",
    run_number: 42,
    eval_pass_pct: null,
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

export function buildRunList(items: RunResponse[]): RunListResponse {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 50,
  };
}

export function getRequestedSources(params: unknown): string[] {
  if (params instanceof URLSearchParams) {
    return params.getAll("source").sort();
  }

  if (params && typeof params === "object") {
    const source = (params as { source?: unknown }).source;

    if (Array.isArray(source)) {
      return source.filter((value): value is string => typeof value === "string").sort();
    }

    if (typeof source === "string") {
      return [source];
    }
  }

  return [];
}

export function rootRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return makeRun(overrides);
}

export function secondRootRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return makeRun({
    id: "run_root_2",
    workflow_id: "wf_root_2",
    workflow_name: "Second Root Flow",
    run_number: 43,
    total_cost_usd: 2.5,
    created_at: 1_710_000_150,
    ...overrides,
  });
}

export function childRun(overrides: Partial<RunResponse> = {}): RunResponse {
  return makeRun({
    id: "run_child",
    workflow_id: "wf_child",
    workflow_name: "Child Flow",
    run_number: 99,
    total_cost_usd: 0.4,
    created_at: 1_710_000_200,
    parent_run_id: "run_root",
    root_run_id: "run_root",
    depth: 1,
    ...overrides,
  });
}

export function getRunRow(workflowName: string): HTMLTableRowElement {
  const row = screen.getByText(workflowName).closest("tr");

  if (!row) {
    throw new Error(`Could not find run row for ${workflowName}`);
  }

  return row as HTMLTableRowElement;
}

export function getRunCostCell(workflowName: string, formattedCost: string): HTMLElement {
  return within(getRunRow(workflowName)).getByText(formattedCost);
}

export function findStream(runId: string): MockEventSource {
  const source = eventSources.find((candidate) => candidate.url === `/api/runs/${runId}/stream`);

  if (!source) {
    throw new Error(`Could not find stream for run ${runId}`);
  }

  return source;
}
