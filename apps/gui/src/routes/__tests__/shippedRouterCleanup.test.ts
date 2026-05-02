// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

vi.mock("@/features/health/HealthPage", () => ({
  Component: () => React.createElement(RouteEcho, { label: "health" }),
}));

vi.mock("@/features/dev/ComponentShowcase", () => ({
  default: () => React.createElement(RouteEcho, { label: "test-components" }),
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

describe("retired route behavior", () => {
  it("keeps /setup/start reachable for onboarding", async () => {
    await renderAppAt("/setup/start");

    expect(await screen.findByText("setup:/setup/start")).toBeTruthy();
  });

  it("lets direct /health visits fall through to normal unknown-route behavior", async () => {
    await renderAppAt("/health");

    expect(await screen.findByText("dashboard:/")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("");
    });
    expect(screen.queryByText("health:/health")).toBeNull();
  });
});
