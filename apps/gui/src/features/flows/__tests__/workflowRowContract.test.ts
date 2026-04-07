// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

const fixtures = {
  populatedWorkflow: {
    id: "wf_research",
    name: "Research & Review",
    description: "Customer interviews and synthesis",
    enabled: true,
    block_count: 3,
    modified_at: Date.parse("2026-03-31T10:00:00Z") / 1000,
    commit_sha: "f078f13deadbeef",
    health: {
      run_count: 12,
      eval_pass_pct: 92,
      eval_health: "success",
      total_cost_usd: 0.42,
      regression_count: 0,
    },
  },
  partialWorkflow: {
    id: "wf_partial",
    name: "New Draft",
    description: "Fresh workflow with no runs",
    enabled: false,
    block_count: 2,
    modified_at: Date.parse("2026-03-28T12:00:00Z") / 1000,
    commit_sha: null,
    health: {
      run_count: 0,
      eval_pass_pct: null,
      eval_health: null,
      total_cost_usd: 0,
      regression_count: 0,
    },
  },
};

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  deleteRequests: [] as Array<unknown>,
}));

vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

async function loadWorkflowRowComponent() {
  const module = await import("../WorkflowRow");
  return (module.Component ??
    (module as Record<string, unknown>).WorkflowRow) as React.ComponentType<Record<string, unknown>>;
}

async function renderWorkflowRow(props: Record<string, unknown>) {
  const WorkflowRow = await loadWorkflowRowComponent();

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  render(
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(
        MemoryRouter,
        null,
        React.createElement(
          "ul",
          { role: "list" },
          React.createElement(WorkflowRow, props),
        ),
      ),
    ),
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-03-31T12:00:00Z"));
  mocks.navigate.mockReset();
  mocks.deleteRequests.length = 0;
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("RUN-426 WorkflowRow behavior", () => {
  it("renders the two-line workflow content from the enhanced workflow payload", async () => {
    await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    const row = screen.getByRole("listitem", {
      name: "Open Research & Review workflow",
    });

    expect(within(row).getByText("Research & Review")).toBeTruthy();
    expect(within(row).getByText(/3 blocks?|3 block/)).toBeTruthy();
    expect(within(row).getByText("f078f13")).toBeTruthy();
    expect(within(row).getByText(/12 runs?|12 run/)).toBeTruthy();
    expect(within(row).getByText(/92% eval/)).toBeTruthy();
    expect(within(row).getByText(/\$0\.42 cost|0\.42 cost/)).toBeTruthy();
    expect(within(row).getByText(/0 regressions?|0 regression/)).toBeTruthy();
  });

  it("uses partial-state fallbacks for workflows with no runs yet", async () => {
    await renderWorkflowRow({
      workflow: fixtures.partialWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    const row = screen.getByRole("listitem", {
      name: "Open New Draft workflow",
    });

    expect(within(row).getByText("New Draft")).toBeTruthy();
    expect(within(row).getByText(/0 runs?|0 run/)).toBeTruthy();
    expect(within(row).getByText("No runs yet")).toBeTruthy();
    expect(within(row).getByText(/uncommitted|Uncommitted/)).toBeTruthy();
  });

  it("renders each workflow as a semantic list item", async () => {
    await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    expect(
      screen.getByRole("listitem", {
        name: "Open Research & Review workflow",
      }),
    ).toBeTruthy();
  });

  it("opens /workflows/:id/edit when the row is activated by click or keyboard", async () => {
    await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    const row = screen.getByRole("listitem", {
      name: "Open Research & Review workflow",
    });

    fireEvent.click(row);

    expect(mocks.navigate).toHaveBeenCalledWith("/workflows/wf_research/edit");

    mocks.navigate.mockClear();

    fireEvent.keyDown(row, {
      key: "Enter",
    });

    expect(mocks.navigate).toHaveBeenCalledWith("/workflows/wf_research/edit");
  });

  it("keeps the accessible trash control available on keyboard focus", async () => {
    await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    const row = screen.getByRole("listitem", {
      name: "Open Research & Review workflow",
    });
    const deleteButton = screen.getByRole("button", {
      name: "Delete Research & Review workflow",
    });

    row.focus();

    expect(document.activeElement).toBe(row);

    deleteButton.focus();

    expect(document.activeElement).toBe(deleteButton);
  });
});
