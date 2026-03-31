// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useLocation, Outlet } from "react-router";

const SRC_DIR = resolve(__dirname, "../..");

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
  Component: () => React.createElement("div", null, "Setup start page"),
}));

vi.mock("@/features/dashboard/DashboardOrOnboarding", () => ({
  Component: () => React.createElement(RouteEcho, { label: "dashboard" }),
}));

vi.mock("@/features/dev/ComponentShowcase", () => ({
  default: () => React.createElement("div", null, "Component showcase"),
}));

vi.mock("@/features/workflows/WorkflowList", () => ({
  Component: () => React.createElement(RouteEcho, { label: "legacy-workflows" }),
}));

vi.mock("@/features/flows/FlowsPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "flows" }),
}));

vi.mock("@/features/canvas/WorkflowCanvas", () => ({
  Component: () => React.createElement("div", null, "Workflow canvas page"),
  WorkflowCanvas: () => React.createElement("div", null, "Workflow canvas page"),
}));

vi.mock("@/features/canvas/CanvasPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "workflow-editor" }),
}));

vi.mock("@/features/runs/RunList", () => ({
  Component: () => React.createElement(RouteEcho, { label: "legacy-runs" }),
}));

vi.mock("@/features/runs/RunDetail", () => ({
  Component: () => React.createElement(RouteEcho, { label: "run-detail" }),
}));

vi.mock("@/features/sidebar/SoulList", () => ({
  Component: () => React.createElement("div", null, "Soul list page"),
}));

vi.mock("@/features/sidebar/TaskList", () => ({
  Component: () => React.createElement(RouteEcho, { label: "tasks" }),
}));

vi.mock("@/features/sidebar/StepList", () => ({
  Component: () => React.createElement(RouteEcho, { label: "steps" }),
}));

vi.mock("@/features/health/HealthPage", () => ({
  Component: () => React.createElement("div", null, "Health page"),
}));

vi.mock("@/features/settings/SettingsPage", () => ({
  Component: () => React.createElement("div", null, "Settings page"),
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

describe("RUN-431 legacy list route cleanup", () => {
  it("redirects /workflows to /flows", async () => {
    await renderAppAt("/workflows");

    expect(await screen.findByText("flows:/flows")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/flows");
      expect(window.location.search).toBe("");
    });
    expect(screen.queryByText("legacy-workflows:/workflows")).toBeNull();
  });

  it("redirects /runs to /flows?tab=runs", async () => {
    await renderAppAt("/runs");

    expect(await screen.findByText("flows:/flows?tab=runs")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/flows");
      expect(window.location.search).toBe("?tab=runs");
    });
    expect(screen.queryByText("legacy-runs:/runs")).toBeNull();
  });

  it.each([
    ["/tasks", "tasks:/tasks"],
    ["/steps", "steps:/steps"],
  ])("does not resolve removed route %s", async (initialPath, removedRouteMarker) => {
    await renderAppAt(initialPath);

    expect(await screen.findByText("dashboard:/")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("");
    });
    expect(screen.queryByText(removedRouteMarker)).toBeNull();
  });

  it("keeps /workflows/:id/edit working", async () => {
    await renderAppAt("/workflows/wf_123/edit");

    expect(await screen.findByText("workflow-editor:/workflows/wf_123/edit")).toBeTruthy();
  });

  it("keeps /runs/:id working", async () => {
    await renderAppAt("/runs/run_123");

    expect(await screen.findByText("run-detail:/runs/run_123")).toBeTruthy();
  });
});

describe("RUN-431 stale list-page files are deleted", () => {
  const removedFiles = [
    "features/workflows/WorkflowList.tsx",
    "features/workflows/NewWorkflowModal.tsx",
    "features/runs/RunList.tsx",
    "features/sidebar/TaskList.tsx",
    "features/sidebar/StepList.tsx",
  ];

  for (const relativePath of removedFiles) {
    it(`${relativePath} is removed from the GUI source tree`, () => {
      const filePath = resolve(SRC_DIR, relativePath);

      expect(existsSync(filePath), `Expected ${relativePath} to be deleted`).toBe(false);
    });
  }
});
