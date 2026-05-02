// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryRouter,
  MemoryRouter,
  RouterProvider,
  useLocation,
} from "react-router";

import { useCanvasStore } from "@/store/canvas";
import { useContextAuditStore } from "@/store/contextAudit";
import {
  buildContextAuditEvent,
  buildSurfaceRun,
  buildSurfaceWorkflow,
  eventSourceInstances,
  MockEventSource,
  type SurfaceRunRecord as RunRecord,
  type SurfaceRunStatus as RunStatus,
  type SurfaceWorkflowRecord as WorkflowRecord,
} from "./helpers/surfaceStreamTestHelpers";

type RunNodeRecord = {
  node_id: string;
  status: string;
  cost_usd?: number;
  duration_seconds?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
};

const harness = vi.hoisted(() => ({
  run: null as RunRecord | null,
  workflow: null as WorkflowRecord | null,
  runNodes: [] as RunNodeRecord[],
  runLogs: [] as Array<{ timestamp: string; level: string; message: string }>,
  runs: [] as RunRecord[],
  runRegressions: { count: 0, issues: [] as Array<Record<string, unknown>> },
  workflowRegressions: { count: 0, issues: [] as Array<Record<string, unknown>> },
  runCalls: [] as string[],
  runNodesCalls: [] as string[],
  runRegressionsCalls: [] as string[],
  runLogsCalls: [] as string[],
  workflowCalls: [] as string[],
  workflowRegressionsCalls: [] as string[],
  useRunsFilters: [] as Array<Record<string, unknown> | undefined>,
  getGitFile: vi.fn(),
  createWorkflow: vi.fn(),
  toastError: vi.fn(),
  queryClient: { invalidateQueries: vi.fn() },
  cancelRun: { mutate: vi.fn(), isPending: false },
  updateWorkflow: { mutate: vi.fn() },
}));

const localStorageState = new Map<string, string>();

vi.mock("@xyflow/react", async () => {
  const ReactModule = await import("react");

  return {
    ReactFlow: ({
      nodes,
      onNodeClick,
      onNodeDoubleClick,
      onPaneClick,
      nodesDraggable,
      nodesConnectable,
      deleteKeyCode,
      children,
    }: {
      nodes: Array<{ id: string; data?: Record<string, unknown> }>;
      onNodeClick?: (event: unknown, node: { id: string; data?: Record<string, unknown> }) => void;
      onNodeDoubleClick?: (event: unknown, node: { id: string; data?: Record<string, unknown> }) => void;
      onPaneClick?: () => void;
      nodesDraggable?: boolean;
      nodesConnectable?: boolean;
      deleteKeyCode?: string | null;
      children?: React.ReactNode;
    }) => (
      <div
        data-testid="react-flow"
        data-draggable={String(Boolean(nodesDraggable))}
        data-connectable={String(Boolean(nodesConnectable))}
        data-delete-key={deleteKeyCode ?? ""}
      >
        <button type="button" data-testid="react-flow-pane" onClick={() => onPaneClick?.()}>
          Pane
        </button>
        {nodes.map((node) => (
          <button
            key={node.id}
            type="button"
            data-testid={`react-flow-node-${node.id}`}
            onClick={() => onNodeClick?.({ type: "click" }, node)}
            onDoubleClick={() => onNodeDoubleClick?.({ type: "dblclick" }, node)}
          >
            {String(node.data?.name ?? node.id)}::{String(node.data?.status ?? "idle")}
          </button>
        ))}
        {children}
      </div>
    ),
    Background: () => <div data-testid="react-flow-background" />,
    Controls: () => <div data-testid="react-flow-controls" />,
    MiniMap: () => <div data-testid="react-flow-minimap" />,
    BackgroundVariant: { Dots: "dots" },
    applyNodeChanges: (_changes: unknown, nodes: unknown[]) => nodes,
    applyEdgeChanges: (_changes: unknown, edges: unknown[]) => edges,
    Handle: () => ReactModule.createElement("div", { "data-testid": "react-flow-handle" }),
    Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
  };
});

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => harness.queryClient,
}));

vi.mock("@/queries/runs", () => {
  return {
    useCreateRun: () => ({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
    }),
    useRun: (runId: string) => {
      harness.runCalls.push(runId);
      return {
        data: runId && harness.run?.id === runId ? harness.run : undefined,
        isLoading: false,
        isError: false,
      };
    },
    useRunNodes: (runId: string) => {
      harness.runNodesCalls.push(runId);
      return {
        data: runId && harness.run?.id === runId ? harness.runNodes : [],
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      };
    },
    useRunLogs: (runId: string) => {
      harness.runLogsCalls.push(runId);
      return {
        data: runId ? { items: harness.runLogs } : { items: [] },
        isLoading: false,
        isError: false,
      };
    },
    useRunContextAudit: () => ({ fetchNextPage: vi.fn(), hasNextPage: false }),
    useRunContextAuditStream: () => undefined,
    useRuns: (filters?: Record<string, unknown>) => {
      harness.useRunsFilters.push(filters);
      return {
        data: { items: harness.runs },
        isLoading: false,
        isError: false,
      };
    },
    useRunRegressions: (runId: string) => {
      harness.runRegressionsCalls.push(runId);
      return {
        data: runId ? harness.runRegressions : undefined,
        isLoading: false,
        isError: false,
      };
    },
    useCancelRun: () => harness.cancelRun,
  };
});

vi.mock("@/queries/workflows", () => ({
  useWorkflow: (workflowId: string) => {
    harness.workflowCalls.push(workflowId);
    return {
      data: workflowId && harness.workflow?.id === workflowId ? harness.workflow : undefined,
      isLoading: false,
      isError: false,
    };
  },
  useWorkflowRegressions: (workflowId: string) => {
    harness.workflowRegressionsCalls.push(workflowId);
    return {
      data: workflowId ? harness.workflowRegressions : undefined,
      isLoading: false,
      isError: false,
    };
  },
  useUpdateWorkflow: () => harness.updateWorkflow,
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    getGitFile: harness.getGitFile,
  },
}));

vi.mock("@/api/workflows", () => ({
  workflowsApi: {
    createWorkflow: harness.createWorkflow,
  },
}));

vi.mock("sonner", () => ({
  toast: {
    error: harness.toastError,
  },
}));

vi.mock("../../surface/SurfaceYamlEditor", () => ({
  SurfaceYamlEditor: ({
    workflowId,
    yaml,
    readOnly,
  }: {
    workflowId: string;
    yaml?: string;
    readOnly?: boolean;
  }) => (
    <div
      data-testid="yaml-editor"
      data-workflow-id={workflowId}
      data-read-only={String(Boolean(readOnly))}
    >
      {yaml}
    </div>
  ),
}));

vi.mock("../../surface/SurfaceStatusBar", () => ({
  SurfaceStatusBar: ({
    blockCount,
    edgeCount,
  }: {
    blockCount: number;
    edgeCount: number;
  }) => (
    <div data-testid="status-bar">
      {blockCount}:{edgeCount}
    </div>
  ),
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => null,
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: () => null,
}));

vi.mock("../../surface/RunButton", () => ({
  RunButton: () => <button type="button" data-testid="workflow-run-button">Run</button>,
}));

import { WorkflowSurface } from "../../surface/WorkflowSurface";

function RouteLocationProbe({ testId }: { testId: string }) {
  const location = useLocation();

  return <div data-testid={testId}>{location.pathname}</div>;
}

function buildRunNode(overrides: Partial<RunNodeRecord> = {}): RunNodeRecord {
  return {
    node_id: "node_brain",
    status: "completed",
    cost_usd: 1.25,
    duration_seconds: 42,
    tokens: { input: 12, output: 32, total: 44 },
    error: null,
    ...overrides,
  };
}

function setReadonlyFixtures({
  runStatus = "completed",
  regressionCount = 0,
  runNodes = [buildRunNode()],
  canvasState = buildSurfaceWorkflow().canvas_state,
}: {
  runStatus?: RunStatus;
  regressionCount?: number;
  runNodes?: RunNodeRecord[];
  canvasState?: WorkflowRecord["canvas_state"];
} = {}) {
  harness.run = buildSurfaceRun({
    status: runStatus,
    commit_sha: "run_commit_readonly",
  });
  harness.workflow = buildSurfaceWorkflow({ canvas_state: canvasState });
  harness.runNodes = runNodes;
  harness.runs = [harness.run];
  harness.runRegressions = { count: regressionCount, issues: [] };
  harness.workflowRegressions = { count: 0, issues: [] };
}

function resetHarness() {
  harness.run = null;
  harness.workflow = null;
  harness.runNodes = [];
  harness.runLogs = [];
  harness.runs = [];
  harness.runRegressions = { count: 0, issues: [] };
  harness.workflowRegressions = { count: 0, issues: [] };
  harness.runCalls = [];
  harness.runNodesCalls = [];
  harness.runRegressionsCalls = [];
  harness.runLogsCalls = [];
  harness.workflowCalls = [];
  harness.workflowRegressionsCalls = [];
  harness.useRunsFilters = [];
  harness.getGitFile.mockReset();
  harness.getGitFile.mockImplementation(async () => ({
    content: "workflow:\n  name: Historical Snapshot\n  enabled: true\n",
  }));
  harness.createWorkflow.mockReset();
  harness.createWorkflow.mockResolvedValue({ id: "wf_forked_readonly" });
  harness.toastError.mockReset();
  harness.queryClient.invalidateQueries.mockReset();
  harness.cancelRun.mutate.mockReset();
  harness.cancelRun.isPending = false;
  harness.updateWorkflow.mutate.mockReset();
  eventSourceInstances.splice(0, eventSourceInstances.length);
  localStorageState.clear();
  window.history.replaceState(null, "", "/runs/run_readonly_surface");
  useCanvasStore.getState().reset();
  useContextAuditStore.setState({ activeRunId: null, eventsByRun: {} });
}

function renderReadonlySurfaceWithRouter() {
  const router = createMemoryRouter(
    [
      {
        path: "/runs/:runId",
        element: (
          <>
            <RouteLocationProbe testId="readonly-route-location" />
            <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
          </>
        ),
      },
      {
        path: "/workflows/:workflowId/edit",
        element: <RouteLocationProbe testId="edit-route-location" />,
      },
    ],
    {
      initialEntries: ["/runs/run_readonly_surface"],
    },
  );

  const user = userEvent.setup();
  render(<RouterProvider router={router} />);

  return { router, user };
}

async function flushForkTransition() {
  await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
  await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
}

beforeEach(() => {
  cleanup();
  resetHarness();
  vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => localStorageState.get(key) ?? null,
    setItem: (key: string, value: string) => {
      localStorageState.set(key, value);
    },
    removeItem: (key: string) => {
      localStorageState.delete(key);
    },
    clear: () => {
      localStorageState.clear();
    },
  } as Storage);
  vi.stubGlobal("requestAnimationFrame", ((cb: FrameRequestCallback) => {
    cb(0);
    return 1;
  }) as typeof requestAnimationFrame);
});

afterEach(() => {
  cleanup();
  useCanvasStore.getState().reset();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("WorkflowSurface readonly integration", () => {
  it("hydrates readonly nodes from persisted canvas state and overlays run execution data", async () => {
    const user = userEvent.setup();
    setReadonlyFixtures();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const [node] = useCanvasStore.getState().nodes;
      expect(node?.id).toBe("node_brain");
      expect(node?.data.status).toBe("completed");
      expect(node?.data.executionCost).toBe(1.25);
      expect(node?.data.duration).toBe(42);
      expect(node?.data.tokens).toEqual({ input: 12, output: 32, total: 44 });
    });

    await user.click(screen.getByTestId("workflow-tab-canvas"));

    const canvas = screen.getByTestId("react-flow");
    expect(canvas.getAttribute("data-draggable")).toBe("false");
    expect(canvas.getAttribute("data-connectable")).toBe("false");
    expect(canvas.getAttribute("data-delete-key")).toBe("");
    expect(screen.getByTestId("react-flow-node-node_brain").textContent).toContain("completed");
  });

  it("shows historical YAML from the run commit and keeps it read-only", async () => {
    setReadonlyFixtures();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(harness.getGitFile).toHaveBeenCalledWith(
        "run_commit_readonly",
        "custom/workflows/wf_readonly_surface.yaml",
      );
    });

    const yamlEditor = await screen.findByTestId("yaml-editor");
    expect(yamlEditor.getAttribute("data-read-only")).toBe("true");
    expect(yamlEditor.textContent).toContain("Historical Snapshot");
  });

  it("opens the shared inspector on node click and closes it on pane click", async () => {
    const user = userEvent.setup();
    setReadonlyFixtures();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    await user.click(screen.getByTestId("workflow-tab-canvas"));
    await user.click(screen.getByTestId("react-flow-node-node_brain"));

    const inspector = await screen.findByTestId("right-inspector");
    expect(inspector.getAttribute("data-trigger")).toBe("single-click");
    expect(screen.getByRole("tab", { name: "Execution" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(within(inspector).getByText("Completed")).toBeTruthy();
    expect(within(inspector).getByText("$1.250")).toBeTruthy();

    await user.click(screen.getByRole("tab", { name: "Overview" }));
    const overviewPanel = screen.getByRole("tabpanel", { name: "Overview" });
    expect(within(overviewPanel).getByText("Research Soul")).toBeTruthy();

    await user.click(screen.getByTestId("react-flow-pane"));

    await waitFor(() => {
      expect(screen.queryByTestId("right-inspector")).toBeNull();
    });
  });

  it("opens the inspector Context tab for the run selected from an audit row", async () => {
    const user = userEvent.setup();
    setReadonlyFixtures();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    await user.click(screen.getByTestId("workflow-tab-canvas"));
    await waitFor(() => {
      expect(useCanvasStore.getState().nodes[0]?.id).toBe("node_brain");
    });

    useContextAuditStore
      .getState()
      .replaceRunEvents("run_readonly_surface", [buildContextAuditEvent()]);

    await user.click(screen.getByTestId("workflow-audit-tab"));
    await user.click(screen.getByRole("button", { name: "Open context audit for node_brain" }));

    await waitFor(() => {
      expect(useCanvasStore.getState().selectedNodeId).toBe("node_brain");
    });
    const inspector = await screen.findByTestId("right-inspector");
    expect(screen.getByRole("tab", { name: "Context" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(within(inspector).getByText("Access declared")).toBeTruthy();
    expect(within(inspector).getByText("research.summary")).toBeTruthy();
    expect(within(inspector).getByText("context from the selected audit run")).toBeTruthy();
  });

  it("shows the readonly regressions banner only when regressions are present", async () => {
    setReadonlyFixtures({ regressionCount: 3 });

    const { rerender } = render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    expect(await screen.findByText("3 regressions found")).toBeTruthy();

    resetHarness();
    setReadonlyFixtures({ regressionCount: 0 });
    rerender(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByText(/regressions found/i)).toBeNull();
    });
  });

  it("lays out readonly canvas from YAML when canvas_state is missing", async () => {
    const user = userEvent.setup();
    const layoutYaml = `
version: "1.0"
blocks:
  node_brain:
    type: linear
    soul_ref: souls/researcher
workflow:
  name: Historical Snapshot
  entry: node_brain
  transitions: []
`;
    setReadonlyFixtures({
      canvasState: null,
    });
    harness.workflow = buildSurfaceWorkflow({
      canvas_state: null,
      yaml: layoutYaml,
    });
    harness.getGitFile.mockResolvedValue({ content: layoutYaml });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    await user.click(screen.getByTestId("workflow-tab-canvas"));

    await waitFor(() => {
      expect(useCanvasStore.getState().nodes[0]?.id).toBe("node_brain");
      expect(useCanvasStore.getState().nodes[0]?.type).toBe("start");
      expect(useCanvasStore.getState().nodes[0]?.data.status).toBe("completed");
    });

    expect(screen.queryByText("Canvas layout unavailable")).toBeNull();
    expect(screen.getByTestId("react-flow-node-node_brain").textContent).toContain("completed");
  });

  it("shows a pre-execution failure card when a failed readonly run has no nodes", async () => {
    const user = userEvent.setup();
    setReadonlyFixtures({ runStatus: "failed", runNodes: [] });
    harness.run = buildSurfaceRun({
      status: "failed",
      commit_sha: "run_commit_readonly",
      error: "Provider configuration missing",
    });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_readonly_surface" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Run failed before execution started")).toBeNull();

    await user.click(screen.getByTestId("workflow-tab-canvas"));

    expect(await screen.findByText("Run failed before execution started")).toBeTruthy();
    expect(screen.queryByTestId("react-flow")).toBeNull();
    expect(screen.getByText(/could not prepare this workflow for execution/i)).toBeTruthy();
    expect(screen.getByText("Provider configuration missing")).toBeTruthy();
    expect(screen.getByTestId("surface-topbar")).toBeTruthy();
    expect(screen.getByTestId("surface-bottom-panel")).toBeTruthy();
    expect(screen.getByTestId("surface-status-bar")).toBeTruthy();

    await user.click(screen.getByTestId("workflow-tab-yaml"));
    expect(await screen.findByTestId("yaml-editor")).toBeTruthy();

    await user.click(screen.getByTestId("workflow-tab-canvas"));
    expect(await screen.findByText("Run failed before execution started")).toBeTruthy();
  });

  it("navigates a readonly run fork through the router into the editable workflow route", async () => {
    setReadonlyFixtures();

    const { router, user } = renderReadonlySurfaceWithRouter();

    await user.click(screen.getByRole("button", { name: "Fork" }));

    await waitFor(() => {
      expect(harness.createWorkflow).toHaveBeenCalledWith({
        name: expect.stringMatching(/^drft-readonly-surface-flow-/),
        yaml: expect.stringContaining("enabled: false"),
        commit: false,
      });
    });

    await flushForkTransition();

    expect(router.state.location.pathname).toBe("/workflows/wf_forked_readonly/edit");

    expect(screen.getByTestId("edit-route-location").textContent).toBe(
      "/workflows/wf_forked_readonly/edit",
    );
    expect(screen.queryByTestId("readonly-route-location")).toBeNull();
  });

  it("does not mutate browser history when a readonly run fork succeeds", async () => {
    setReadonlyFixtures();

    const { user } = renderReadonlySurfaceWithRouter();
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");
    replaceStateSpy.mockClear();

    await user.click(screen.getByRole("button", { name: "Fork" }));

    await waitFor(() => {
      expect(harness.createWorkflow).toHaveBeenCalledTimes(1);
    });

    await flushForkTransition();

    expect(replaceStateSpy).not.toHaveBeenCalled();
  });

  it("does not dispatch a synthetic popstate when a readonly run fork succeeds", async () => {
    setReadonlyFixtures();

    const { user } = renderReadonlySurfaceWithRouter();
    const dispatchEventSpy = vi.spyOn(window, "dispatchEvent");
    dispatchEventSpy.mockClear();

    await user.click(screen.getByRole("button", { name: "Fork" }));

    await waitFor(() => {
      expect(harness.createWorkflow).toHaveBeenCalledTimes(1);
    });

    await flushForkTransition();

    expect(
      dispatchEventSpy.mock.calls.some(([event]) => event instanceof PopStateEvent),
    ).toBe(false);
  });

  it("keeps edit mode off the readonly data path and hides readonly-only UI state", async () => {
    harness.workflow = buildSurfaceWorkflow();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="edit" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    const yamlEditor = await screen.findByTestId("yaml-editor");
    expect(yamlEditor.getAttribute("data-workflow-id")).toBe("wf_readonly_surface");
    expect(yamlEditor.getAttribute("data-read-only")).toBe("false");
    expect(harness.getGitFile).not.toHaveBeenCalled();
    expect(harness.runNodesCalls.every((runId) => runId === "")).toBe(true);
    expect(harness.runRegressionsCalls.every((runId) => runId === "")).toBe(true);
    expect(screen.queryByText("Read-only review")).toBeNull();
    expect(screen.queryByRole("button", { name: "Fork" })).toBeNull();
    expect(screen.queryByText(/regressions found/i)).toBeNull();
    expect(screen.getByTestId("workflow-run-button")).toBeTruthy();
  });

  it("lays out edit mode from YAML when canvas_state is missing", async () => {
    harness.workflow = buildSurfaceWorkflow({
      canvas_state: null,
      yaml: `
version: "1.0"
blocks:
  start_here:
    type: linear
    soul_ref: souls/researcher
  finish_here:
    type: linear
    soul_ref: souls/reviewer
workflow:
  name: Edit Layout Flow
  entry: start_here
  transitions:
    - from: start_here
      to: finish_here
`,
    });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="edit" workflowId="wf_readonly_surface" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(useCanvasStore.getState().nodes.map((node) => node.id)).toEqual([
        "start_here",
        "finish_here",
      ]);
      expect(useCanvasStore.getState().nodes[0]?.type).toBe("start");
      expect(useCanvasStore.getState().nodes[1]?.type).toBe("soul");
    });
  });
});
