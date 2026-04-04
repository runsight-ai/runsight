// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { useLocation, Outlet } from "react-router";

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

vi.mock("@/features/runs/RunsPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "canonical-runs" }),
}));

vi.mock("@/features/runs/RunDetail", () => ({
  Component: () => React.createElement(RouteEcho, { label: "run-detail" }),
}));

// RUN-590: /runs/:id now renders HistoricalRunRoute which uses WorkflowSurface
vi.mock("@/features/canvas/WorkflowSurface", () => ({
  WorkflowSurface: ({ runId }: { runId?: string }) =>
    React.createElement(RouteEcho, { label: `run-surface-${runId ?? "unknown"}` }),
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
  const routesSource = readFileSync(resolve(__dirname, "..", "index.tsx"), "utf-8");

  it("lets /workflows fall through to normal unknown-route behavior", async () => {
    await renderAppAt("/workflows");

    expect(await screen.findByText("dashboard:/")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("");
    });
    expect(screen.queryByText("legacy-workflows:/workflows")).toBeNull();
  });

  it("keeps /runs as the canonical runs page", async () => {
    await renderAppAt("/runs");

    expect(await screen.findByText("canonical-runs:/runs")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/runs");
      expect(window.location.search).toBe("");
    });
  });

  it.each(["/tasks", "/steps"])("redirects removed route %s away from the retired list UI", async (initialPath) => {
    await renderAppAt(initialPath);

    expect(await screen.findByText("dashboard:/")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("");
    });
  });

  it("keeps the router source free of retired sidebar route imports", () => {
    expect(routesSource).not.toMatch(/features\/sidebar\/(?:SoulList|TaskList|StepList)/);
    expect(routesSource).not.toMatch(/path:\s*"tasks"/);
    expect(routesSource).not.toMatch(/path:\s*"steps"/);
  });

  it("keeps the /workflows/:id/edit route definition wired to WorkflowSurface", () => {
    expect(routesSource).toMatch(/path:\s*"workflows\/:id\/edit"/);
    // RUN-590: routes now use WorkflowSurface via WorkflowEditRoute
    expect(routesSource).toMatch(/WorkflowSurface/);
  });

  it("keeps /runs/:id working", async () => {
    await renderAppAt("/runs/run_123");

    // RUN-590: /runs/:id now renders WorkflowSurface (HistoricalRunRoute) instead of RunDetail
    expect(await screen.findByText("run-surface-run_123:/runs/run_123")).toBeTruthy();
  });
});
