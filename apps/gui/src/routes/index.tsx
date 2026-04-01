import { createBrowserRouter, Navigate } from "react-router";
import { ShellLayout } from "./layouts/ShellLayout";
import { createSetupGuardLoader, createReverseGuardLoader } from "./guards";
import { queryClient } from "@/lib/queryClient";

const RETIRED_DIRECT_ENTRY_PATHS = new Set(["/health", "/test-components"]);

if (
  typeof window !== "undefined" &&
  RETIRED_DIRECT_ENTRY_PATHS.has(window.location.pathname)
) {
  window.history.replaceState(null, "", "/");
}

export const router = createBrowserRouter([
  {
    path: "setup/start",
    loader: createReverseGuardLoader(queryClient),
    lazy: () =>
      import("@/features/setup/SetupStartPage").then((m) => ({
        Component: m.Component,
      })),
  },
  {
    loader: createSetupGuardLoader(queryClient),
    element: <ShellLayout />,
    children: [
      {
        index: true,
        lazy: () =>
          import("@/features/dashboard/DashboardOrOnboarding").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "flows",
        lazy: () =>
          import("@/features/flows/FlowsPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "workflows/:id",
        lazy: () =>
          import("@/features/canvas/WorkflowCanvas").then((m) => ({
            Component: m.Component ?? m.WorkflowCanvas,
          })),
      },
      {
        path: "workflows/:id/edit",
        lazy: () =>
          import("@/features/canvas/CanvasPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "workflows",
        element: <Navigate to="/flows" replace />,
      },
      {
        path: "runs",
        lazy: () =>
          import("@/features/runs/RunsPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "runs/:id",
        lazy: () =>
          import("@/features/runs/RunDetail").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "souls",
        lazy: () =>
          import("@/features/souls/SoulLibraryPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "souls/new",
        lazy: () =>
          import("@/features/souls/SoulFormPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "souls/:id/edit",
        lazy: () =>
          import("@/features/souls/SoulFormPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "settings",
        lazy: () =>
          import("@/features/settings/SettingsPage").then((m) => ({
            Component: m.Component,
          })),
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
