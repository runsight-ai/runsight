// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
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

describe("RUN-507 shipped router route contract", () => {
  const routesSource = readFileSync(resolve(__dirname, "..", "index.tsx"), "utf-8");

  it("keeps /setup/start as the supported onboarding entry point", () => {
    expect(routesSource).toMatch(/path:\s*"setup\/start"/);
  });

  it("keeps legacy /workflows list traffic pointed at /flows", () => {
    expect(routesSource).toMatch(/path:\s*"workflows"/);
    expect(routesSource).toMatch(/Navigate\s+to="\/flows"\s+replace/);
  });

  it("removes the placeholder /health route from the shipped router", () => {
    expect(routesSource).not.toMatch(/path:\s*"health"/);
    expect(routesSource).not.toMatch(/features\/health\/HealthPage/);
  });

  it("removes the dev-only /test-components route from the shipped router", () => {
    expect(routesSource).not.toMatch(/path:\s*"test-components"/);
    expect(routesSource).not.toMatch(/ComponentShowcase/);
  });
});

describe("RUN-507 retired route behavior", () => {
  it("keeps /setup/start reachable for onboarding", async () => {
    await renderAppAt("/setup/start");

    expect(await screen.findByText("setup:/setup/start")).toBeTruthy();
  });

  it("redirects bookmarked /health visits back to the supported shell", async () => {
    await renderAppAt("/health");

    expect(await screen.findByText("dashboard:/")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("");
    });
    expect(screen.queryByText("health:/health")).toBeNull();
  });

  it("redirects /test-components away from the shipped product router", async () => {
    await renderAppAt("/test-components");

    expect(await screen.findByText("dashboard:/")).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("");
    });
    expect(screen.queryByText("test-components:/test-components")).toBeNull();
  });
});
