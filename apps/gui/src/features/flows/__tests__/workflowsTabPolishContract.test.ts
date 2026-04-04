// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";

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
    {
      id: "wf_ops",
      name: "Ops + Alerts",
      enabled: true,
      block_count: 2,
      modified_at: 1_774_414_300,
      commit_sha: "aa11bb22cc33dd44",
      health: {
        run_count: 4,
        eval_pass_pct: 88,
        total_cost_usd: 0.2,
        regression_count: 1,
      },
    },
    {
      id: "wf_docs",
      name: "Docs [Beta]",
      enabled: false,
      block_count: 1,
      modified_at: 1_774_414_200,
      commit_sha: "ee55ff66aa77bb88",
      health: {
        run_count: 1,
        eval_pass_pct: 100,
        total_cost_usd: 0.05,
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
  createWorkflow: vi.fn(),
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
  useCreateWorkflow: () => ({
    mutate: mocks.createWorkflow,
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
  mocks.createWorkflow.mockReset();
});

async function renderWorkflowsTab() {
  const { WorkflowsTab } = await import("../WorkflowsTab");
  const user = userEvent.setup();
  render(React.createElement(WorkflowsTab, { onCreateWorkflow: vi.fn() }));
  return { user };
}

async function renderFlowsRoute(initialPath = "/flows") {
  const { FlowsPage } = await import("../FlowsPage");
  const router = createMemoryRouter(
    [
      {
        path: "/flows",
        element: React.createElement(FlowsPage),
      },
      {
        path: "/runs",
        element: React.createElement("div", null, "Runs stub"),
      },
    ],
    { initialEntries: [initialPath] },
  );
  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));
  return { router, user };
}

describe("RUN-430 /flows search polish", () => {
  it("autofocuses the Search workflows input when the workflows page loads", async () => {
    await renderWorkflowsTab();

    const searchInput = screen.getByRole("searchbox", { name: "Search workflows" });

    expect(document.activeElement).toBe(searchInput);
  });

  it("treats special characters literally in workflow search", async () => {
    const { user } = await renderWorkflowsTab();
    const searchInput = screen.getByRole("searchbox", { name: "Search workflows" });

    await user.type(searchInput, "&");

    expect(screen.getByText("Research & Review")).toBeTruthy();
    expect(screen.queryByText("Ops + Alerts")).toBeNull();
    expect(screen.queryByText("Docs [Beta]")).toBeNull();
  });

  it("resets flows search after leaving and re-entering the page", async () => {
    const { router, user } = await renderFlowsRoute("/flows");
    const searchInput = await screen.findByRole("searchbox", {
      name: "Search workflows",
    });

    await user.type(searchInput, "ops");
    expect((searchInput as HTMLInputElement).value).toBe("ops");
    expect(screen.getByText("Ops + Alerts")).toBeTruthy();
    expect(screen.queryByText("Research & Review")).toBeNull();

    await router.navigate("/runs");
    await screen.findByText("Runs stub");

    await router.navigate("/flows");
    const restoredSearchInput = await screen.findByRole("searchbox", {
      name: "Search workflows",
    });

    expect((restoredSearchInput as HTMLInputElement).value).toBe("");
    expect(screen.getByText("Research & Review")).toBeTruthy();
    expect(screen.getByText("Ops + Alerts")).toBeTruthy();
  });
});
