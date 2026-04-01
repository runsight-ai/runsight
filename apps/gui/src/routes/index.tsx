import type { ComponentType } from "react";
import { createBrowserRouter, Navigate, useParams } from "react-router";
import { ShellLayout } from "./layouts/ShellLayout";
import { createSetupGuardLoader, createReverseGuardLoader } from "./guards";
import { queryClient } from "@/lib/queryClient";

function LegacyWorkflowEditorRedirect() {
  const { id } = useParams<{ id: string }>();

  return <Navigate to={`/workflows/${id}/edit`} replace />;
}

export const router = createBrowserRouter([
  {
    path: "setup/unavailable",
    lazy: () =>
      import("@/features/setup/SetupUnavailablePage").then((m) => ({
        Component: m.Component,
      })),
  },
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
            Component:
              "LegacyWorkflowRedirect" in m
                ? (m.LegacyWorkflowRedirect as ComponentType)
                : LegacyWorkflowEditorRedirect,
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
