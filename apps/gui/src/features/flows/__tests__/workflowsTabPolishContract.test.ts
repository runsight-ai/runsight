// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  workflows: [
    {
      id: "wf_research",
      name: "Research & Review",
      enabled: true,
      block_count: 3,
      modified_at: 1_774_414_400,
      commit_sha: "f078f13deadbeef",
      health: {
        run_count: 12,
        eval_pass_pct: 92,
        total_cost_usd: 0.42,
        regression_count: 0,
      },
    },
  ],
  queryState: {
    data: {
      items: [] as Array<Record<string, unknown>>,
      total: 0,
    },
    isLoading: false,
    error: null as Error | null,
  },
  refetch: vi.fn(),
  deleteWorkflow: vi.fn(),
  setWorkflowEnabled: vi.fn(),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: mocks.queryState.data,
    isLoading: mocks.queryState.isLoading,
    error: mocks.queryState.error,
    refetch: mocks.refetch,
  }),
  useDeleteWorkflow: () => ({
    mutateAsync: mocks.deleteWorkflow,
    isPending: false,
  }),
  useSetWorkflowEnabled: () => ({
    mutateAsync: mocks.setWorkflowEnabled,
    isPending: false,
  }),
}));

vi.mock("../WorkflowRow", () => ({
  WorkflowRow: ({ workflow }: { workflow: { name?: string | null } }) =>
    React.createElement("li", null, workflow.name ?? "Untitled"),
}));

vi.mock("@/components/shared/DeleteConfirmDialog", () => ({
  DeleteConfirmDialog: () => null,
}));

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  mocks.queryState.data = {
    items: mocks.workflows,
    total: mocks.workflows.length,
  };
  mocks.queryState.isLoading = false;
  mocks.queryState.error = null;
  mocks.refetch.mockReset();
  mocks.deleteWorkflow.mockReset();
  mocks.setWorkflowEnabled.mockReset();
});

async function renderWorkflowsTab() {
  const { WorkflowsTab } = await import("../WorkflowsTab");
  render(React.createElement(WorkflowsTab, { onCreateWorkflow: vi.fn() }));
}

describe("RUN-430 /flows search polish", () => {
  it("autofocuses the Search workflows input when the workflows page loads", async () => {
    await renderWorkflowsTab();

    const searchInput = screen.getByRole("searchbox", { name: "Search workflows" });

    expect(document.activeElement).toBe(searchInput);
  });
});
