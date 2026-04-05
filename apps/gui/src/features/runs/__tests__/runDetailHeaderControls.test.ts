// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";

const mocks = vi.hoisted(() => ({
  forkWorkflow: vi.fn(),
  cancelRun: vi.fn(),
}));

vi.mock("../useForkWorkflow", () => ({
  useForkWorkflow: (options: { onTransition?: (id: string) => void }) => ({
    isForking: false,
    forkedWorkflowId: undefined,
    forkWorkflow: () => {
      mocks.forkWorkflow();
      options.onTransition?.("wf_forked");
    },
  }),
}));

vi.mock("@/queries/runs", () => ({
  useCancelRun: () => ({
    mutate: mocks.cancelRun,
    isPending: false,
  }),
}));

import { RunDetailHeader } from "../RunDetailHeader";

afterEach(() => {
  cleanup();
  mocks.forkWorkflow.mockReset();
  mocks.cancelRun.mockReset();
});

type RunStatus = "completed" | "failed" | "running";

function LocationEcho() {
  const location = useLocation();
  return React.createElement(
    "div",
    null,
    `location:${location.pathname}${location.search}`,
  );
}

function buildRun({
  status = "completed",
  workflowId = "wf_research",
}: {
  status?: RunStatus;
  workflowId?: string | null;
} = {}) {
  return {
    id: "run_123456",
    workflow_id: workflowId ?? undefined,
    workflow_name: "Research & Review",
    status,
    commit_sha: "abc123def456",
    total_cost_usd: 0.123,
    total_tokens: 456,
  };
}

function renderHeader(options?: { status?: RunStatus; workflowId?: string | null }) {
  const run = buildRun(options);
  const router = createMemoryRouter(
    [
      {
        path: "/runs/:id",
        element: React.createElement(RunDetailHeader, { run }),
      },
      {
        path: "/runs",
        element: React.createElement(LocationEcho),
      },
      {
        path: "/workflows/:id/edit",
        element: React.createElement(LocationEcho),
      },
    ],
    { initialEntries: [`/runs/${run.id}`] },
  );

  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

describe("Run detail header controls (RUN-510)", () => {
  it("keeps the back control usable and navigates to /runs", async () => {
    const { router, user } = renderHeader();

    await user.click(screen.getByRole("button", { name: "Back to runs" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("location:/runs")).toBeTruthy();
  });

  it("uses honest Open Workflow labeling and navigates to the editable workflow surface when workflow_id exists", async () => {
    const { router, user } = renderHeader({ status: "completed" });

    expect(
      screen.queryByRole("button", { name: /run again/i }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: /open workflow/i })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /open workflow/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("location:/workflows/wf_research/edit")).toBeTruthy();
  });

  it("does not surface misleading Retry copy for failed runs when the retained action only opens the workflow", async () => {
    const { router, user } = renderHeader({ status: "failed" });

    expect(screen.queryByRole("button", { name: /retry/i })).toBeNull();
    expect(screen.getByRole("button", { name: /open workflow/i })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /open workflow/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("location:/workflows/wf_research/edit")).toBeTruthy();
  });

  it("does not render standalone dead zoom controls in the header", () => {
    renderHeader();

    expect(
      screen.queryByRole("group", { name: /canvas zoom controls/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /zoom in/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /zoom out/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /fit to screen/i })).toBeNull();
  });

  it("does not expose a misleading workflow action when workflow_id is absent", () => {
    renderHeader({ workflowId: null });

    expect(screen.queryByRole("button", { name: /open workflow/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /run again/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /retry/i })).toBeNull();
  });

  it("shows a live cancel control for active runs and calls the cancel mutation", async () => {
    const { user } = renderHeader({ status: "running" });

    expect(screen.getByRole("button", { name: /cancel run/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /open workflow/i })).toBeNull();
    expect(screen.getByRole("button", { name: "Fork" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /cancel run/i }));

    expect(mocks.cancelRun).toHaveBeenCalledWith("run_123456");
  });

  it("opens the new forked workflow editor after forking from a run", async () => {
    const { router, user } = renderHeader({ status: "completed" });

    await user.click(screen.getByRole("button", { name: "Fork" }));

    await waitFor(() => {
      expect(mocks.forkWorkflow).toHaveBeenCalledTimes(1);
      expect(router.state.location.pathname).toBe("/workflows/wf_forked/edit");
      expect(router.state.location.search).toBe("");
    });
  });
});
