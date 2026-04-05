// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";

const mocks = vi.hoisted(() => ({
  workflows: {
    data: {
      items: [{ id: "wf_research", name: "Research & Review" }],
      total: 1,
    },
  },
  createWorkflow: {
    mutateAsync: vi.fn(),
    isPending: false,
  },
  dashboardKpis: {
    data: {
      runs_today: 0,
      cost_today_usd: 0,
      eval_pass_rate: null,
      regressions: 0,
    },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  },
  attentionItems: {
    data: {
      items: [] as Array<Record<string, unknown>>,
    },
  },
  activeRuns: {
    activeRuns: [] as Array<Record<string, unknown>>,
    subscribeToRunStream: vi.fn(() => ({
      close: vi.fn(),
    })),
    isLoading: false,
    isError: false,
  },
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => mocks.workflows,
  useCreateWorkflow: () => mocks.createWorkflow,
}));

vi.mock("@/queries/dashboard", () => ({
  useDashboardKPIs: () => mocks.dashboardKpis,
  useAttentionItems: () => mocks.attentionItems,
  useRecentRuns: () => ({ data: { items: [], total: 0 } }),
}));

vi.mock("@/queries/runs", () => ({
  useActiveRuns: () => mocks.activeRuns,
  useCancelRun: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

function LocationEcho() {
  const location = useLocation();
  return React.createElement(
    "div",
    null,
    `location:${location.pathname}${location.search}`,
  );
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  mocks.createWorkflow.mutateAsync.mockReset();
  mocks.dashboardKpis.refetch.mockReset();
  mocks.activeRuns.subscribeToRunStream.mockClear();
  mocks.workflows.data = {
    items: [{ id: "wf_research", name: "Research & Review" }],
    total: 1,
  };
  mocks.dashboardKpis.data = {
    runs_today: 0,
    cost_today_usd: 0,
    eval_pass_rate: null,
    regressions: 0,
  };
  mocks.dashboardKpis.isPending = false;
  mocks.dashboardKpis.isError = false;
  mocks.attentionItems.data = {
    items: [],
  };
  mocks.activeRuns.activeRuns = [];
  mocks.activeRuns.isLoading = false;
  mocks.activeRuns.isError = false;
});

async function renderDashboard() {
  const { Component: DashboardOrOnboarding } = await import(
    "../dashboard/DashboardOrOnboarding"
  );
  const router = createMemoryRouter(
    [
      { path: "/", element: React.createElement(DashboardOrOnboarding) },
      { path: "/flows", element: React.createElement(LocationEcho) },
      { path: "/runs", element: React.createElement(LocationEcho) },
    ],
    { initialEntries: ["/"] },
  );

  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

async function renderRunDetailHeader() {
  const { RunDetailHeader } = await import("../runs/RunDetailHeader");
  const router = createMemoryRouter(
    [
      {
        path: "/runs/:id",
        element: React.createElement(RunDetailHeader, {
          run: {
            id: "run_123456",
            workflow_id: "wf_research",
            workflow_name: "Research & Review",
            status: "completed",
            total_cost_usd: 0.123,
            total_tokens: 456,
          },
        }),
      },
      { path: "/flows", element: React.createElement(LocationEcho) },
      { path: "/runs", element: React.createElement(LocationEcho) },
    ],
    { initialEntries: ["/runs/run_123456"] },
  );

  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

describe("RUN-431 dashboard list-navigation cleanup", () => {
  it('sends the "Open Flows" CTA directly to /flows', async () => {
    const { router, user } = await renderDashboard();

    await user.click(await screen.findByRole("button", { name: "Open Flows" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/flows");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("location:/flows")).toBeTruthy();
  });

  it('sends the attention overflow "see all" action directly to the attention filter', async () => {
    mocks.dashboardKpis.data = {
      runs_today: 4,
      cost_today_usd: 1.25,
      eval_pass_rate: 0.91,
      regressions: 0,
    };
    mocks.attentionItems.data = {
      items: [
        { run_id: "run_1", type: "regression", title: "One", description: "One", workflow_id: "wf_research" },
        { run_id: "run_2", type: "regression", title: "Two", description: "Two", workflow_id: "wf_research" },
        { run_id: "run_3", type: "regression", title: "Three", description: "Three", workflow_id: "wf_research" },
        { run_id: "run_4", type: "regression", title: "Four", description: "Four", workflow_id: "wf_research" },
      ],
    };

    const { router, user } = await renderDashboard();

    await user.click(await screen.findByRole("button", { name: /see all/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs");
      expect(router.state.location.search).toBe("?attention=only");
    });
    expect(screen.getByText("location:/runs?attention=only")).toBeTruthy();
  });
});

describe("RUN-431 run detail list-navigation cleanup", () => {
  it('links the "Back to runs" affordance to /runs', async () => {
    const { router, user } = await renderRunDetailHeader();

    await user.click(await screen.findByRole("button", { name: "Back to runs" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("location:/runs")).toBeTruthy();
  });
});
