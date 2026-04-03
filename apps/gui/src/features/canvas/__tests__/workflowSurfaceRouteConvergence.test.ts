// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createBrowserRouter, RouterProvider } from "react-router";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");

type TestRunStatus = "completed" | "failed" | "running" | "pending" | "success" | "error";
type TestRun = ReturnType<typeof buildRun>;

let currentRun: TestRun = buildRun();
const getGitFileMock = vi.fn();
const createWorkflowMock = vi.fn();
const createRunMutateMock = vi.fn();
const setActiveRunIdMock = vi.fn();

function readSource(relativePath: string) {
  return readFileSync(resolve(GUI_SRC_ROOT, relativePath), "utf8");
}

function countLines(relativePath: string) {
  return readSource(relativePath).split("\n").length;
}

function buildRun({
  status = "completed" as TestRunStatus,
  commitSha = "abc123",
  source = "manual",
}: {
  status?: TestRunStatus;
  commitSha?: string | null;
  source?: string;
} = {}) {
  return {
    id: "run_123456",
    workflow_id: "wf-research",
    workflow_name: "Research Workflow",
    status,
    source,
    total_cost_usd: 0.042,
    total_tokens: 1234,
    duration_seconds: 45,
    started_at: 1700000000,
    completed_at: 1700000045,
    created_at: 1700000000,
    commit_sha: commitSha,
  };
}

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
  ReactFlowProvider: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  useNodesState: () => [[], vi.fn(), vi.fn()],
  useEdgesState: () => [[], vi.fn(), vi.fn()],
}));

vi.mock("@/queries/runs", () => ({
  useRun: () => ({ data: currentRun, isLoading: false }),
  useRunNodes: () => ({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRunLogs: () => ({ data: { items: [] } }),
  useRunRegressions: () => ({ data: { count: 0 } }),
  useCreateRun: () => ({ mutate: createRunMutateMock }),
}));

vi.mock("@/components/shared/ErrorBoundary", () => ({
  CanvasErrorBoundary: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
}));

vi.mock("@/components/shared", () => ({
  PriorityBanner: () => null,
}));

vi.mock("@/components/shared/PriorityBanner", () => ({
  PriorityBanner: () => null,
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => null,
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: () => null,
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    getGitFile: (...args: unknown[]) => getGitFileMock(...args),
    createSimBranch: vi.fn(),
  },
}));

vi.mock("@/api/workflows", () => ({
  workflowsApi: {
    createWorkflow: (...args: unknown[]) => createWorkflowMock(...args),
  },
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => ({
    data: { items: [{ id: "provider-1", is_active: true }] },
  }),
}));

vi.mock("@/queries/git", () => ({
  useGitStatus: () => ({
    data: { is_clean: true, uncommitted_files: [] },
  }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock("@/store/canvas", () => {
  const state = {
    activeRunId: null,
    setActiveRunId: setActiveRunIdMock,
    blockCount: 0,
    edgeCount: 0,
    yamlContent: "name: Research Workflow\nenabled: true\n",
    toPersistedState: () => undefined,
  };

  return {
    useCanvasStore: Object.assign(
      (selector: (value: typeof state) => unknown) => selector(state),
      {
        getState: () => state,
      },
    ),
  };
});

vi.mock("../workflowSurfaceQueries", () => ({
  useWorkflow: () => ({
    data: { id: "wf-research", name: "Research Workflow", commit_sha: "abc123" },
  }),
  useWorkflowRegressions: () => ({ data: { count: 0 } }),
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  DialogContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogTitle: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogFooter: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: () => null,
}));

vi.mock("@runsight/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
}));

vi.mock("../../runs/RunCanvasNode", () => ({
  RunCanvasNode: () => null,
  CanvasNodeComponent: () => null,
  nodeTypes: {},
}));

vi.mock("../../runs/RunInspectorPanel", () => ({
  RunInspectorPanel: () => null,
}));

vi.mock("../../runs/RunBottomPanel", () => ({
  RunBottomPanel: () => null,
}));

vi.mock("../../runs/runDetailUtils", () => ({
  getIconForBlockType: () => "icon",
  mapRunStatus: (status: string) => status,
}));

vi.mock("../CanvasStatusBar", () => ({
  CanvasStatusBar: () => null,
}));

vi.mock("../CanvasBottomPanel", () => ({
  CanvasBottomPanel: () => null,
}));

vi.mock("../FirstTimeTooltip", () => ({
  FirstTimeTooltip: () => null,
}));

vi.mock("../PaletteSidebar", () => ({
  PaletteSidebar: () => null,
}));

vi.mock("../WorkflowCanvas", () => ({
  WorkflowCanvas: () => React.createElement("div", null, "workflow-canvas"),
}));

vi.mock("../YamlEditor", () => ({
  YamlEditor: () => React.createElement("div", { "aria-label": "yaml editor" }, "yaml-editor"),
}));

async function renderWorkflowSurfaceRouterApp(initialPath: string) {
  const [{ Component: RunDetail }, { Component: CanvasPage }] = await Promise.all([
    import("../../runs/RunDetail"),
    import("../CanvasPage"),
  ]);

  window.history.replaceState(null, "", initialPath);

  const router = createBrowserRouter([
    {
      path: "/runs/:id",
      element: React.createElement(RunDetail),
    },
    {
      path: "/workflows/:id/edit",
      element: React.createElement(CanvasPage),
    },
  ]);

  render(React.createElement(RouterProvider, { router }));

  return { router, user: userEvent.setup() };
}

beforeEach(() => {
  currentRun = buildRun();
  getGitFileMock.mockReset();
  createWorkflowMock.mockReset();
  createRunMutateMock.mockReset();
  setActiveRunIdMock.mockReset();

  getGitFileMock.mockResolvedValue({
    content: "name: Research Workflow\nenabled: true\n",
  });
  createWorkflowMock.mockResolvedValue({ id: "wf-fork-draft" });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("RUN-596 workflow surface route convergence", () => {
  it("direct loads /workflows/:id/edit into the shared workflow surface product", async () => {
    const { router } = await renderWorkflowSurfaceRouterApp("/workflows/wf-research/edit");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf-research/edit");
    });

    const surface = document.querySelector("[data-layout='workflow-surface']");

    expect(surface).not.toBeNull();
    expect(surface).toHaveAttribute("data-mode", "workflow");
    expect(surface).toHaveAttribute("data-workflow-id", "wf-research");
  });

  it("direct loads /runs/:id into the shared workflow surface product and keeps the same product shell across back/forward navigation", async () => {
    const { router, user } = await renderWorkflowSurfaceRouterApp("/runs/run_123456");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs/run_123456");
    });

    expect(document.querySelector("[data-layout='workflow-surface']")).not.toBeNull();
    expect(screen.getByText(/Read-only review/i)).not.toBeNull();

    await user.click(screen.getByRole("button", { name: /fork/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf-fork-draft/edit");
    });

    expect(document.querySelector("[data-layout='workflow-surface']")).not.toBeNull();
    expect(screen.getByRole("button", { name: /^save$/i })).not.toBeNull();

    window.history.back();
    window.dispatchEvent(new PopStateEvent("popstate"));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs/run_123456");
    });
    expect(document.querySelector("[data-layout='workflow-surface']")).not.toBeNull();
    expect(screen.getByText(/Read-only review/i)).not.toBeNull();

    window.history.forward();
    window.dispatchEvent(new PopStateEvent("popstate"));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf-fork-draft/edit");
    });
    expect(document.querySelector("[data-layout='workflow-surface']")).not.toBeNull();
    expect(screen.getByRole("button", { name: /^save$/i })).not.toBeNull();
  });

  it("reduces CanvasPage to a thin route wrapper instead of a page-level workflow surface owner", () => {
    expect(countLines("features/canvas/CanvasPage.tsx")).toBeLessThanOrEqual(160);
  });

  it("reduces RunDetail to a thin route wrapper instead of a page-level historical surface owner", () => {
    expect(countLines("features/runs/RunDetail.tsx")).toBeLessThanOrEqual(160);
  });
});
