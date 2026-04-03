// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createBrowserRouter, RouterProvider } from "react-router";

type TestRunStatus = "completed" | "failed" | "running" | "pending" | "success" | "error";

type TestRun = ReturnType<typeof buildRun>;

let currentRun: TestRun = buildRun();
const getGitFileMock = vi.fn();
const createWorkflowMock = vi.fn();
const createRunMutateMock = vi.fn();
const setActiveRunIdMock = vi.fn();

function buildRun({
  status = "completed" as TestRunStatus,
  commitSha = "abc123" as string | null | undefined,
  source = "manual",
}: {
  status?: TestRunStatus;
  commitSha?: string | null | undefined;
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

vi.mock("../../canvas/workflowSurfaceQueries", () => ({
  useWorkflow: () => ({
    data: { id: "wf-fork-draft", name: "Fork Draft Workflow", commit_sha: null },
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

vi.mock("../RunCanvasNode", () => ({
  RunCanvasNode: () => null,
  CanvasNodeComponent: () => null,
  nodeTypes: {},
}));

vi.mock("../RunInspectorPanel", () => ({
  RunInspectorPanel: () => null,
}));

vi.mock("../RunBottomPanel", () => ({
  RunBottomPanel: () => null,
}));

vi.mock("../runDetailUtils", () => ({
  getIconForBlockType: () => "icon",
  mapRunStatus: (status: string) => status,
}));

vi.mock("../../canvas/CanvasStatusBar", () => ({
  CanvasStatusBar: () => null,
}));

vi.mock("../../canvas/CanvasBottomPanel", () => ({
  CanvasBottomPanel: () => null,
}));

vi.mock("../../canvas/FirstTimeTooltip", () => ({
  FirstTimeTooltip: () => null,
}));

vi.mock("../../canvas/PaletteSidebar", () => ({
  PaletteSidebar: () => null,
}));

vi.mock("../../canvas/WorkflowCanvas", () => ({
  WorkflowCanvas: () => React.createElement("div", null, "workflow-canvas"),
}));

vi.mock("../../canvas/YamlEditor", () => ({
  YamlEditor: () => React.createElement("div", { "aria-label": "yaml editor" }, "yaml-editor"),
}));

async function renderWorkflowSurfaceApp() {
  const [{ Component: RunDetail }, { Component: CanvasPage }] = await Promise.all([
    import("../RunDetail"),
    import("../../canvas/CanvasPage"),
  ]);

  window.history.replaceState(null, "", "/runs/run_123456");

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

describe("RUN-595 in-place workflow surface fork transition", () => {
  it("keeps the same workflow surface shell while transitioning a historical run into fork-draft editing", async () => {
    const { router, user } = await renderWorkflowSurfaceApp();
    const surfaceBefore = document.querySelector("[data-layout='workflow-surface']");

    expect(surfaceBefore).not.toBeNull();
    expect(surfaceBefore).toHaveAttribute("data-mode", "historical");
    expect(screen.getByText(/Read-only review/i)).not.toBeNull();

    await user.click(screen.getByRole("button", { name: /fork/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf-fork-draft/edit");
    });

    const surfaceAfter = document.querySelector("[data-layout='workflow-surface']");

    expect(router.state.location.state).toMatchObject({
      workflowSurfaceMode: "fork-draft",
    });
    expect(surfaceAfter).toBe(surfaceBefore);
    expect(surfaceAfter).toHaveAttribute("data-mode", "fork-draft");
    expect(surfaceAfter).toHaveAttribute("data-workflow-id", "wf-fork-draft");
    expect(surfaceAfter).not.toHaveAttribute("data-run-id");
    expect(screen.getByRole("button", { name: /save/i })).not.toBeNull();
    expect(screen.getByRole("tab", { name: /canvas/i })).not.toBeNull();
    expect(screen.getByRole("tab", { name: /yaml/i })).not.toBeNull();
    expect(screen.queryByText(/Read-only review/i)).toBeNull();
    expect(screen.queryByText(/Total Cost/i)).toBeNull();
  });

  it("preserves the same shared surface when forking a failed run", async () => {
    currentRun = buildRun({ status: "failed" });

    const { router, user } = await renderWorkflowSurfaceApp();
    const surfaceBefore = document.querySelector("[data-layout='workflow-surface']");

    expect(screen.getByText(/Failed/i)).not.toBeNull();

    await user.click(screen.getByRole("button", { name: /fork/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf-fork-draft/edit");
    });

    expect(document.querySelector("[data-layout='workflow-surface']")).toBe(surfaceBefore);
    expect(screen.getByRole("button", { name: /save/i })).not.toBeNull();
    expect(screen.queryByText(/Read-only review/i)).toBeNull();
  });

  it("treats simulation runs like the same shared surface transition into fork-draft editing", async () => {
    currentRun = buildRun({ status: "success", source: "simulation" });

    const { router, user } = await renderWorkflowSurfaceApp();
    const surfaceBefore = document.querySelector("[data-layout='workflow-surface']");

    await user.click(screen.getByRole("button", { name: /fork/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/workflows/wf-fork-draft/edit");
    });

    expect(document.querySelector("[data-layout='workflow-surface']")).toBe(surfaceBefore);
    expect(screen.getByRole("button", { name: /save/i })).not.toBeNull();
    expect(screen.queryByText(/Read-only review/i)).toBeNull();
  });

  it("keeps snapshot-unavailable runs on the historical shared surface", async () => {
    currentRun = buildRun({ commitSha: undefined });

    const { router } = await renderWorkflowSurfaceApp();
    const surface = document.querySelector("[data-layout='workflow-surface']");
    const forkButton = screen.getByRole("button", { name: /fork/i });

    expect(
      forkButton.hasAttribute("disabled")
        || forkButton.getAttribute("aria-disabled") === "true",
    ).toBe(true);
    expect(forkButton).toHaveAttribute("title", "Snapshot unavailable");
    expect(router.state.location.pathname).toBe("/runs/run_123456");
    expect(surface).toHaveAttribute("data-mode", "historical");
    expect(screen.getByText(/Read-only review/i)).not.toBeNull();
  });
});
