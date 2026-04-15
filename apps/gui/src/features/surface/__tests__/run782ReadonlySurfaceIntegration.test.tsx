// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

import { useCanvasStore } from "@/store/canvas";

type RunStatus = "completed" | "failed" | "running" | "pending";

type RunRecord = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: RunStatus;
  commit_sha: string;
  duration_seconds: number;
  total_tokens: number;
  total_cost_usd: number;
  source: string;
  error: string | null;
  created_at?: number;
  started_at?: number;
};

type WorkflowRecord = {
  id: string;
  name: string;
  yaml: string;
  canvas_state?: {
    nodes?: Array<Record<string, unknown>>;
    edges?: Array<Record<string, unknown>>;
    viewport?: { x: number; y: number; zoom: number };
    selected_node_id?: string | null;
    canvas_mode?: "dag" | "state-machine";
  } | null;
  commit_sha: string;
};

type RunNodeRecord = {
  node_id: string;
  status: string;
  cost_usd?: number;
  duration_seconds?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
};

type EventSourceListener = (event: MessageEvent) => void;

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

const eventSources: MockEventSource[] = [];
const localStorageState = new Map<string, string>();

class MockEventSource {
  static instances = eventSources;

  public readonly url: string;
  public readonly close = vi.fn();
  private readonly listeners = new Map<string, EventSourceListener[]>();

  constructor(url: string) {
    this.url = url;
    eventSources.push(this);
  }

  addEventListener(type: string, listener: EventSourceListener) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  emit(type: string, payload: Record<string, unknown>) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data: JSON.stringify(payload) } as MessageEvent);
    }
  }
}

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

vi.mock("@/queries/runs", () => ({
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
}));

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

function buildWorkflow(overrides: Partial<WorkflowRecord> = {}): WorkflowRecord {
  return {
    id: "wf_782",
    name: "Readonly Surface Flow",
    yaml: "workflow:\n  name: Live Workflow\n  enabled: true\n",
    canvas_state: {
      nodes: [
        {
          id: "node_brain",
          type: "soul",
          position: { x: 120, y: 80 },
          data: {
            name: "Research Soul",
            soulRef: "souls/researcher",
            model: "gpt-5",
            status: "idle",
            executionCost: 0,
            duration: 0,
          },
        },
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    },
    commit_sha: "workflow_commit_782",
    ...overrides,
  };
}

function buildRun(overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    id: "run_782",
    workflow_id: "wf_782",
    workflow_name: "Readonly Surface Flow",
    status: "completed",
    commit_sha: "run_commit_782",
    duration_seconds: 88,
    total_tokens: 2112,
    total_cost_usd: 3.14,
    source: "manual",
    error: null,
    created_at: 100,
    started_at: 200,
    ...overrides,
  };
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
  canvasState = buildWorkflow().canvas_state,
}: {
  runStatus?: RunStatus;
  regressionCount?: number;
  runNodes?: RunNodeRecord[];
  canvasState?: WorkflowRecord["canvas_state"];
} = {}) {
  harness.run = buildRun({ status: runStatus });
  harness.workflow = buildWorkflow({ canvas_state: canvasState });
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
  harness.createWorkflow.mockResolvedValue({ id: "wf_forked_782" });
  harness.toastError.mockReset();
  harness.queryClient.invalidateQueries.mockReset();
  harness.cancelRun.mutate.mockReset();
  harness.cancelRun.isPending = false;
  harness.updateWorkflow.mutate.mockReset();
  eventSources.splice(0, eventSources.length);
  localStorageState.clear();
  window.history.replaceState(null, "", "/runs/run_782");
  useCanvasStore.getState().reset();
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
  vi.unstubAllGlobals();
});

describe("WorkflowSurface readonly integration (RUN-782)", () => {
  it("hydrates readonly nodes from persisted canvas state and overlays run execution data", async () => {
    const user = userEvent.setup();
    setReadonlyFixtures();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
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

  it("updates node status from SSE through the shared bottom panel path", async () => {
    setReadonlyFixtures({
      runStatus: "running",
      runNodes: [buildRunNode({ status: "running" })],
    });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(eventSources).toHaveLength(1);
      expect(eventSources[0]?.url).toBe("/api/runs/run_782/stream");
    });

    await waitFor(() => {
      expect(useCanvasStore.getState().nodes[0]?.data.status).toBe("running");
      expect(useCanvasStore.getState().activeRunId).toBe("run_782");
    });

    eventSources[0]?.emit("node_completed", {
      node_id: "node_brain",
      cost_usd: 2.5,
    });
    eventSources[0]?.emit("run_completed", {
      run_id: "run_782",
      total_cost_usd: 7.5,
    });

    await waitFor(() => {
      expect(useCanvasStore.getState().nodes[0]?.data.status).toBe("completed");
      expect(useCanvasStore.getState().runCost).toBe(7.5);
      expect(useCanvasStore.getState().activeRunId).toBeNull();
      expect(eventSources[0]?.close).toHaveBeenCalledTimes(1);
    });
  });

  it("shows historical YAML from the run commit and keeps it read-only", async () => {
    setReadonlyFixtures();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(harness.getGitFile).toHaveBeenCalledWith(
        "run_commit_782",
        "custom/workflows/wf_782.yaml",
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
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
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

  it("shows the readonly regressions banner only when regressions are present", async () => {
    setReadonlyFixtures({ regressionCount: 3 });

    const { rerender } = render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
      </MemoryRouter>,
    );

    expect(await screen.findByText("3 regressions found")).toBeTruthy();

    resetHarness();
    setReadonlyFixtures({ regressionCount: 0 });
    rerender(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
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
    harness.workflow = buildWorkflow({
      canvas_state: null,
      yaml: layoutYaml,
    });
    harness.getGitFile.mockResolvedValue({ content: layoutYaml });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
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

  it("forks a completed readonly run into edit mode", async () => {
    const user = userEvent.setup();
    setReadonlyFixtures();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_782" workflowId="wf_782" />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Fork" }));

    await waitFor(() => {
      expect(harness.createWorkflow).toHaveBeenCalledWith({
        name: expect.stringMatching(/^drft-readonly-surface-flow-/),
        yaml: expect.stringContaining("enabled: false"),
        commit: false,
      });
      expect(window.location.pathname).toBe("/workflows/wf_forked_782/edit");
    });
  });

  it("keeps edit mode off the readonly data path and hides readonly-only UI state", async () => {
    harness.workflow = buildWorkflow();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="edit" workflowId="wf_782" />
      </MemoryRouter>,
    );

    const yamlEditor = await screen.findByTestId("yaml-editor");
    expect(yamlEditor.getAttribute("data-workflow-id")).toBe("wf_782");
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
    harness.workflow = buildWorkflow({
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
        <WorkflowSurface mode="edit" workflowId="wf_782" />
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
