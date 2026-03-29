import { createBrowserRouter, Navigate } from "react-router";
import { ShellLayout } from "./layouts/ShellLayout";
import ComponentShowcase from "@/features/dev/ComponentShowcase";

export const router = createBrowserRouter([
  {
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
        path: "workflows",
        lazy: () =>
          import("@/features/workflows/WorkflowList").then((m) => ({
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
        path: "runs",
        lazy: () =>
          import("@/features/runs/RunList").then((m) => ({
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
          import("@/features/sidebar/SoulList").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "tasks",
        lazy: () =>
          import("@/features/sidebar/TaskList").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "steps",
        lazy: () =>
          import("@/features/sidebar/StepList").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "health",
        lazy: () =>
          import("@/features/health/HealthPage").then((m) => ({
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
      {
        path: "test-components",
        element: <ComponentShowcase />,
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
