// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { AttentionItem, RunResponse } from "@runsight/shared/zod";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  navigate: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: () => harness.navigate,
}));

vi.mock("@runsight/ui/card", () => ({
  Card: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => React.createElement("article", { onClick }, children),
}));

vi.mock("@runsight/ui/badge", () => ({
  Badge: ({ children, variant }: { children?: React.ReactNode; variant?: string }) =>
    React.createElement("span", { "data-variant": variant }, children),
}));

vi.mock("lucide-react", () => ({
  Activity: () => React.createElement("span", null),
  AlertTriangle: () => React.createElement("span", null),
}));

import { AttentionItems } from "../components/AttentionItems";

function attentionItem(overrides: Partial<AttentionItem>): AttentionItem {
  return {
    type: "regression",
    title: "Regression · summarize",
    description: "Score dropped",
    run_id: "run_1",
    workflow_id: "wf_1",
    node_id: "summarize",
    severity: "warning",
    created_at: 1_710_000_000,
    ...overrides,
  } as AttentionItem;
}

function runInfo(overrides: Partial<RunResponse>): RunResponse {
  return {
    id: "run_1",
    workflow_id: "wf_1",
    workflow_name: "Review Flow",
    status: "completed",
    error: null,
    started_at: 1_710_000_000,
    completed_at: 1_710_000_100,
    duration_seconds: 100,
    total_cost_usd: 1,
    total_tokens: 100,
    created_at: 1_710_000_000,
    branch: "main",
    source: "manual",
    commit_sha: "abc123",
    run_number: 12,
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
  } as RunResponse;
}

beforeEach(() => {
  harness.navigate.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("AttentionItems", () => {
  it("shows the first three attention items with run context and opens the selected run", () => {
    const items = [
      attentionItem({ run_id: "run_1", title: "Regression · summarize" }),
      attentionItem({ run_id: "run_2", title: "Regression · review" }),
      attentionItem({ run_id: "run_3", title: "New baseline · draft", type: "new_baseline" }),
      attentionItem({ run_id: "run_4", title: "Regression · hidden" }),
    ];
    const recentRunsById = new Map<string, RunResponse>([
      ["run_1", runInfo({ id: "run_1", workflow_name: "Review Flow", run_number: 12 })],
      ["run_2", runInfo({ id: "run_2", workflow_name: "Audit Flow", run_number: 8 })],
      ["run_3", runInfo({ id: "run_3", workflow_name: "Draft Flow", run_number: null })],
    ]);

    render(<AttentionItems items={items} recentRunsById={recentRunsById} />);

    expect(screen.getByText("Review Flow #12")).toBeTruthy();
    expect(screen.getByText("Audit Flow #8")).toBeTruthy();
    expect(screen.getByText("Draft Flow")).toBeTruthy();
    expect(screen.queryByText(/hidden/i)).toBeNull();
    expect(screen.getByText("new baseline").getAttribute("data-variant")).toBe("info");

    fireEvent.click(screen.getByText("Review Flow #12"));

    expect(harness.navigate).toHaveBeenCalledWith("/runs/run_1");
  });

  it("links to the full attention-filtered runs list when more than three items exist", () => {
    render(
      <AttentionItems
        items={[
          attentionItem({ run_id: "run_1" }),
          attentionItem({ run_id: "run_2" }),
          attentionItem({ run_id: "run_3" }),
          attentionItem({ run_id: "run_4" }),
        ]}
        recentRunsById={new Map()}
      />,
    );

    fireEvent.click(screen.getByText("see all \u2192"));

    expect(harness.navigate).toHaveBeenCalledWith("/runs?attention=only");
  });
});
