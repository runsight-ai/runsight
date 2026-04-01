// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import type { QueryClient } from "@tanstack/react-query";
import { createReverseGuardLoader, createSetupGuardLoader } from "../guards";

type FetchQueryImpl = (options: unknown) => Promise<unknown>;

function renderGuardRouter(initialEntry: string, fetchQueryImpl: FetchQueryImpl) {
  const fetchQuery = vi.fn(fetchQueryImpl);
  const queryClient = {
    fetchQuery,
  } as unknown as QueryClient;

  const router = createMemoryRouter(
    [
      {
        path: "/setup/unavailable",
        element: React.createElement(
          "div",
          null,
          React.createElement("h1", null, "Guard unavailable"),
          React.createElement("button", { type: "button" }, "Retry"),
        ),
      },
      {
        path: "/setup/start",
        loader: createReverseGuardLoader(queryClient),
        element: React.createElement("div", null, "Setup start"),
      },
      {
        path: "/",
        loader: createSetupGuardLoader(queryClient),
        element: React.createElement("div", null, "Protected app"),
      },
    ],
    {
      initialEntries: [initialEntry],
    },
  );

  render(React.createElement(RouterProvider, { router }));

  return { router, fetchQuery };
}

afterEach(() => {
  cleanup();
});

describe("RUN-496 routed setup guard fallback", () => {
  it("redirects protected-route navigation to /setup/unavailable when settings fetch fails", async () => {
    const { router } = renderGuardRouter("/", async () => {
      throw new Error("settings request failed");
    });

    expect(await screen.findByText("Guard unavailable")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    expect(screen.queryByText("Protected app")).toBeNull();
    expect(router.state.location.pathname).toBe("/setup/unavailable");
  });

  it("redirects reverse-guard navigation to /setup/unavailable when onboarding state cannot be loaded", async () => {
    const { router } = renderGuardRouter("/setup/start", async () => {
      throw new Error("settings request failed");
    });

    expect(await screen.findByText("Guard unavailable")).toBeTruthy();
    expect(screen.queryByText("Setup start")).toBeNull();
    expect(router.state.location.pathname).toBe("/setup/unavailable");
  });

  it("treats a malformed settings payload as unavailable instead of first-run setup", async () => {
    const { router } = renderGuardRouter("/", async () => ({}));

    expect(await screen.findByText("Guard unavailable")).toBeTruthy();
    expect(screen.queryByText("Setup start")).toBeNull();
    expect(router.state.location.pathname).toBe("/setup/unavailable");
  });

  it("preserves the first-run redirect when onboarding_completed is explicitly false", async () => {
    const { router } = renderGuardRouter("/", async () => ({
      onboarding_completed: false,
    }));

    expect(await screen.findByText("Setup start")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/setup/start");
  });

  it("preserves the reverse redirect when onboarding_completed is explicitly true", async () => {
    const { router } = renderGuardRouter("/setup/start", async () => ({
      onboarding_completed: true,
    }));

    expect(await screen.findByText("Protected app")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/");
  });
});
