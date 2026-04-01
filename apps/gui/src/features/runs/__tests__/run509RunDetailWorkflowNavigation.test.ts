// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";

import { RunDetailHeader } from "../RunDetailHeader";

afterEach(() => {
  cleanup();
});

function LocationEcho() {
  const location = useLocation();
  return React.createElement(
    "div",
    null,
    `location:${location.pathname}${location.search}`,
  );
}

type RunStatus = "completed" | "failed";

function buildRun(status: RunStatus = "completed") {
  return {
    id: "run_123456",
    workflow_id: "wf_research",
    workflow_name: "Research & Review",
    status,
    total_cost_usd: 0.123,
    total_tokens: 456,
  };
}

function renderHeader(status: RunStatus) {
  const router = createMemoryRouter(
    [
      {
        path: "/runs/:id",
        element: React.createElement(RunDetailHeader, {
          run: buildRun(status),
        }),
      },
      {
        path: "/workflows/:id/edit",
        element: React.createElement(LocationEcho),
      },
      {
        path: "/workflows/:id",
        element: React.createElement("div", null, "legacy-workflow-surface"),
      },
    ],
    { initialEntries: ["/runs/run_123456"] },
  );

  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

describe("RUN-509 run detail workflow navigation", () => {
  it("opens the canonical /edit workflow surface from completed runs", async () => {
    const { router, user } = renderHeader("completed");

    expect(
      screen.getByRole("button", { name: "Open Workflow" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /open canvas/i })).toBeNull();

    await user.click(screen.getByRole("button", { name: /open workflow/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("location:/workflows/wf_research/edit")).toBeTruthy();
    expect(screen.queryByText("legacy-workflow-surface")).toBeNull();
  });

  it("opens the canonical /edit workflow surface from failed runs too", async () => {
    const { router, user } = renderHeader("failed");

    expect(
      screen.getByRole("button", { name: "Open Workflow" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /open canvas/i })).toBeNull();

    await user.click(screen.getByRole("button", { name: /open workflow/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("location:/workflows/wf_research/edit")).toBeTruthy();
    expect(screen.queryByText("legacy-workflow-surface")).toBeNull();
  });
});
