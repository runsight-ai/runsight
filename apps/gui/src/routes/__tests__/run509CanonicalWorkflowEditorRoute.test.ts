// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Outlet, useLocation } from "react-router";

function RouteEcho({ label }: { label: string }) {
  const location = useLocation();
  return React.createElement(
    "div",
    null,
    `${label}:${location.pathname}${location.search}`,
  );
}

vi.mock("../guards", () => ({
  createSetupGuardLoader: () => async () => null,
  createReverseGuardLoader: () => async () => null,
}));

vi.mock("../layouts/ShellLayout", async () => {
  const actual = await vi.importActual<typeof import("react-router")>(
    "react-router",
  );

  return {
    ShellLayout: () => {
      const navigate = actual.useNavigate();

      return React.createElement(
        React.Fragment,
        null,
        React.createElement(
          "button",
          {
            type: "button",
            onClick: () => navigate("/flows"),
          },
          "Flows",
        ),
        React.createElement(actual.Outlet),
      );
    },
  };
});

vi.mock("@/lib/queryClient", () => ({
  queryClient: {},
}));

vi.mock("@/features/setup/SetupStartPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "setup" }),
}));

vi.mock("@/features/dashboard/DashboardOrOnboarding", () => ({
  Component: () => React.createElement(RouteEcho, { label: "dashboard" }),
}));

vi.mock("@/features/flows/FlowsPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "flows" }),
}));

vi.mock("@/features/canvas/CanvasPage", () => ({
  Component: () =>
    React.createElement(
      "section",
      null,
      React.createElement("h1", null, "Workflow editor"),
      React.createElement(
        "button",
        {
          type: "button",
        },
        "Save workflow",
      ),
      React.createElement(RouteEcho, { label: "workflow-editor" }),
    ),
}));

vi.mock("@/features/canvas/WorkflowCanvas", () => ({
  Component: () => React.createElement(RouteEcho, { label: "legacy-canvas" }),
  WorkflowCanvas: () => React.createElement(RouteEcho, { label: "legacy-canvas" }),
}));

vi.mock("@/features/runs/RunsPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "runs" }),
}));

vi.mock("@/features/runs/RunDetail", () => ({
  Component: () => React.createElement(RouteEcho, { label: "run-detail" }),
}));

vi.mock("@/features/souls/SoulLibraryPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "souls" }),
}));

vi.mock("@/features/souls/SoulFormPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "soul-form" }),
}));

vi.mock("@/features/settings/SettingsPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "settings" }),
}));

let activeRouter: { dispose?: () => void } | null = null;

afterEach(() => {
  cleanup();
  activeRouter?.dispose?.();
  activeRouter = null;
  window.history.pushState({}, "", "/");
});

async function renderAppAt(initialPath: string) {
  vi.resetModules();
  window.history.pushState({}, "", initialPath);

  const { RouterProvider } = await import("react-router");
  const { router } = await import("../index");

  activeRouter = router;
  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

describe("RUN-509 canonical workflow editor route", () => {
  it("redirects legacy /workflows/:id visits onto the canonical editor with save available", async () => {
    const { router } = await renderAppAt("/workflows/wf_research");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
      expect(router.state.location.search).toBe("");
    });

    expect(
      screen.getByRole("heading", { name: "Workflow editor" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Save workflow" }),
    ).toBeTruthy();
    expect(screen.queryByText(/legacy-canvas:/)).toBeNull();
  });

  it("lets people return to the Flows list from the canonical editor path", async () => {
    const { router, user } = await renderAppAt("/workflows/wf_research");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
      expect(router.state.location.search).toBe("");
    });

    await user.click(screen.getByRole("button", { name: "Flows" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/flows");
      expect(router.state.location.search).toBe("");
    });
    expect(screen.getByText("flows:/flows")).toBeTruthy();
  });
});
