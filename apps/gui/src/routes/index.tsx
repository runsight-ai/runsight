import { createBrowserRouter, Navigate, useParams } from "react-router";
import { ShellLayout } from "./layouts/ShellLayout";
import { createSetupGuardLoader, createReverseGuardLoader } from "./guards";
import { queryClient } from "@/lib/queryClient";
import { WorkflowSurface } from "@/features/surface/WorkflowSurface";
const ROUTE_HYDRATE_FALLBACK = <div aria-hidden="true" />;

function WorkflowEditRoute() {
  const { id } = useParams<{ id: string }>();
  return <WorkflowSurface mode="edit" workflowId={id!} />;
}

function ReadonlyRunRoute() {
  const { id } = useParams<{ id: string }>();
  return <WorkflowSurface mode="readonly" runId={id!} />;
}

export const router = createBrowserRouter([
  {
    path: "setup/unavailable",
    hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
    lazy: () =>
      import("@/features/setup/SetupUnavailablePage").then((m) => ({
        Component: m.Component,
      })),
  },
  {
    path: "setup/start",
    loader: createReverseGuardLoader(queryClient),
    hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
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
        hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
        lazy: () =>
          import("@/features/dashboard/DashboardOrOnboarding").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "flows",
        hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
        lazy: () =>
          import("@/features/flows/FlowsPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "workflows/:id/edit",
        Component: WorkflowEditRoute,
      },
      {
        path: "runs",
        hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
        lazy: () =>
          import("@/features/runs/RunsPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "runs/:id",
        Component: ReadonlyRunRoute,
      },
      {
        path: "souls",
        hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
        lazy: () =>
          import("@/features/souls/SoulLibraryPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "souls/new",
        hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
        lazy: () =>
          import("@/features/souls/SoulFormPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "souls/:id/edit",
        hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
        lazy: () =>
          import("@/features/souls/SoulFormPage").then((m) => ({
            Component: m.Component,
          })),
      },
      {
        path: "settings",
        hydrateFallbackElement: ROUTE_HYDRATE_FALLBACK,
        lazy: () =>
          import("@/features/settings/SettingsPage").then((m) => ({
            Component: m.Component,
          })),
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
