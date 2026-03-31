import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  soulListComponent: vi.fn(() => React.createElement("div", null, "SoulList")),
  soulLibraryPageComponent: vi.fn(() => React.createElement("div", null, "SoulLibraryPage")),
  soulFormPageComponent: vi.fn(() => React.createElement("div", null, "SoulFormPage")),
}));

vi.mock("react-router", () => ({
  createBrowserRouter: (routes: unknown) => ({ routes }),
  Navigate: () => React.createElement("navigate"),
  NavLink: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement(
      "navlink",
      props,
      typeof children === "function" ? children({ isActive: false }) : children,
    ),
  Outlet: () => React.createElement("outlet"),
}));

vi.mock("@/features/sidebar/SoulList", () => ({
  Component: mocks.soulListComponent,
}));

vi.mock("@/features/souls/SoulLibraryPage", () => ({
  Component: mocks.soulLibraryPageComponent,
}), { virtual: true });

vi.mock("@/features/souls/SoulFormPage", () => ({
  Component: mocks.soulFormPageComponent,
}));

vi.mock("@/components/shared/ErrorBoundary", () => ({
  RouteErrorBoundary: ({ children }: { children?: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
}));

vi.mock("@/features/dev/ComponentShowcase", () => ({
  default: () => React.createElement("div", null, "ComponentShowcase"),
}));

vi.mock("../guards", () => ({
  createSetupGuardLoader: () => () => null,
  createReverseGuardLoader: () => () => null,
}));

vi.mock("@/lib/queryClient", () => ({
  queryClient: {},
}));

vi.mock("@/utils/helpers", () => ({
  cn: (...classes: Array<string | undefined | false | null>) =>
    classes.filter(Boolean).join(" "),
}));

function findRoute(router: { routes: Array<{ children?: Array<{ path?: string; lazy?: () => Promise<{ Component: unknown }> }> }> }, path: string) {
  const branch = router.routes.find((route) => Array.isArray(route.children));
  const route = branch?.children?.find((child) => child.path === path);

  expect(route, `Expected route with path ${path} to exist`).toBeDefined();
  return route!;
}

beforeEach(() => {
  mocks.soulListComponent.mockClear();
  mocks.soulLibraryPageComponent.mockClear();
  mocks.soulFormPageComponent.mockClear();
});

describe("RUN-452 route wiring", () => {
  it("routes /souls to SoulLibraryPage instead of the legacy SoulList", async () => {
    const { router } = await import("../index");

    const soulsRoute = findRoute(router, "souls");
    const resolved = await soulsRoute.lazy?.();

    expect(resolved?.Component).toBe(mocks.soulLibraryPageComponent);
    expect(resolved?.Component).not.toBe(mocks.soulListComponent);
  });

  it("keeps /souls/new and /souls/:id/edit wired to SoulFormPage", async () => {
    const { router } = await import("../index");

    const newRoute = findRoute(router, "souls/new");
    const editRoute = findRoute(router, "souls/:id/edit");

    await expect(newRoute.lazy?.()).resolves.toEqual(
      expect.objectContaining({ Component: mocks.soulFormPageComponent }),
    );
    await expect(editRoute.lazy?.()).resolves.toEqual(
      expect.objectContaining({ Component: mocks.soulFormPageComponent }),
    );
  });
});
