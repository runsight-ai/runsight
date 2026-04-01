// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
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

vi.mock("../layouts/ShellLayout", () => ({
  ShellLayout: () => React.createElement(Outlet),
}));

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
  Component: () => React.createElement(RouteEcho, { label: "workflow-editor" }),
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
  render(React.createElement(RouterProvider, { router }));

  return router;
}

describe("RUN-509 canonical workflow editor route", () => {
  it("redirects legacy /workflows/:id visits to the canonical /workflows/:id/edit surface", async () => {
    const router = await renderAppAt("/workflows/wf_research");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf_research/edit");
      expect(router.state.location.search).toBe("");
    });
  });
});
