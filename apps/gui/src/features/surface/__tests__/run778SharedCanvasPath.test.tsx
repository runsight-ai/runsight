// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

type MockNode = {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
};

type CanvasStoreState = {
  nodes: MockNode[];
  edges: Array<Record<string, unknown>>;
  selectedNodeId: string | null;
  blockCount: number;
  edgeCount: number;
  yamlContent: string;
  activeRunId: string | null;
  runCost: number;
  isDirty: boolean;
  onNodesChange: ReturnType<typeof vi.fn>;
  onEdgesChange: ReturnType<typeof vi.fn>;
  selectNode: ReturnType<typeof vi.fn>;
  setNodeStatus: ReturnType<typeof vi.fn>;
  setActiveRunId: ReturnType<typeof vi.fn>;
  setRunCost: ReturnType<typeof vi.fn>;
  setYamlContent: ReturnType<typeof vi.fn>;
  hydrateFromPersisted: ReturnType<typeof vi.fn>;
};

type WorkflowCanvasProps = {
  isDraggable?: boolean;
  connectionsAllowed?: boolean;
  deletionAllowed?: boolean;
  runId?: string;
  onNodeClick?: (nodeId: string) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
};

const mockState = {
  workflow: null as Record<string, unknown> | null,
  run: null as Record<string, unknown> | null,
  runNodes: [] as Array<Record<string, unknown>>,
  runNodesIsError: false,
  runNodesError: null as Error | null,
  refetchRunNodes: vi.fn(),
  getGitFile: vi.fn(),
};

let canvasStoreState: CanvasStoreState;
const storeListeners = new Set<() => void>();
const workflowCanvasRenderSpy = vi.fn();

function emitStoreChange() {
  for (const listener of storeListeners) {
    listener();
  }
}

function createCanvasStoreState(): CanvasStoreState {
  return {
    nodes: [],
    edges: [],
    selectedNodeId: null,
    blockCount: 0,
    edgeCount: 0,
    yamlContent: "",
    activeRunId: null,
    runCost: 0,
    isDirty: false,
    onNodesChange: vi.fn(),
    onEdgesChange: vi.fn(),
    selectNode: vi.fn((id: string | null) => {
      canvasStoreState.selectedNodeId = id;
      emitStoreChange();
    }),
    setNodeStatus: vi.fn((nodeId: string, status: string) => {
      canvasStoreState.nodes = canvasStoreState.nodes.map((node) =>
        node.id === nodeId
          ? {
              ...node,
              data: {
                ...node.data,
                status,
              },
            }
          : node,
      );
      emitStoreChange();
    }),
    setActiveRunId: vi.fn((runId: string | null) => {
      canvasStoreState.activeRunId = runId;
      emitStoreChange();
    }),
    setRunCost: vi.fn((cost: number) => {
      canvasStoreState.runCost = cost;
      emitStoreChange();
    }),
    setYamlContent: vi.fn((content: string) => {
      canvasStoreState.yamlContent = content;
      emitStoreChange();
    }),
    hydrateFromPersisted: vi.fn((persisted: {
      nodes?: MockNode[];
      edges?: Array<Record<string, unknown>>;
      selected_node_id?: string | null;
    } | null | undefined) => {
      canvasStoreState.nodes = persisted?.nodes ?? [];
      canvasStoreState.edges = persisted?.edges ?? [];
      canvasStoreState.selectedNodeId = persisted?.selected_node_id ?? null;
      emitStoreChange();
    }),
  };
}

canvasStoreState = createCanvasStoreState();

const useCanvasStore = ((selector?: (state: CanvasStoreState) => unknown) => {
  const snapshot = React.useSyncExternalStore(
    (listener) => {
      storeListeners.add(listener);
      return () => storeListeners.delete(listener);
    },
    () => canvasStoreState,
    () => canvasStoreState,
  );

  return typeof selector === "function" ? selector(snapshot) : snapshot;
}) as {
  <T>(selector: (state: CanvasStoreState) => T): T;
  (): CanvasStoreState;
  getState: () => CanvasStoreState;
};

useCanvasStore.getState = () => canvasStoreState;

function resetHarness() {
  mockState.workflow = null;
  mockState.run = null;
  mockState.runNodes = [];
  mockState.runNodesIsError = false;
  mockState.runNodesError = null;
  mockState.refetchRunNodes.mockReset();
  mockState.getGitFile.mockReset();
  workflowCanvasRenderSpy.mockReset();
  mockState.getGitFile.mockResolvedValue({
    content: "workflow:\n  name: Shared Canvas Flow\n",
  });
  canvasStoreState = createCanvasStoreState();
  emitStoreChange();
}

function buildWorkflow(overrides: Record<string, unknown> = {}) {
  return {
    id: "wf_shared_canvas",
    name: "Shared Canvas Flow",
    yaml: "workflow:\n  name: Shared Canvas Flow\n",
    canvas_state: {
      nodes: [
        {
          id: "node_soul",
          type: "soul",
          position: { x: 320, y: 180 },
          data: {
            name: "Research Soul",
            soulRef: "souls/researcher",
            model: "gpt-4.1",
            status: "idle",
            executionCost: 0.123,
            duration: 14,
          },
        },
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    },
    commit_sha: "workflow_sha_123",
    ...overrides,
  };
}

function buildRun(overrides: Record<string, unknown> = {}) {
  return {
    id: "run_778",
    workflow_id: "wf_shared_canvas",
    workflow_name: "Shared Canvas Flow",
    status: "completed",
    commit_sha: "run_sha_123",
    duration_seconds: 28,
    total_cost_usd: 0.123,
    total_tokens: 420,
    source: "manual",
    error: null,
    ...overrides,
  };
}

function installMocks() {
  vi.doMock("@tanstack/react-query", () => ({
    useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  }));

  vi.doMock("@/queries/runs", () => ({
    useRun: (runId: string) => ({
      data: runId === mockState.run?.id ? mockState.run : undefined,
      isLoading: false,
      isError: false,
    }),
    useRunNodes: () => ({
      data: mockState.runNodes,
      isLoading: false,
      isError: mockState.runNodesIsError,
      error: mockState.runNodesError,
      refetch: mockState.refetchRunNodes,
    }),
    useRunRegressions: () => ({
      data: undefined,
      isLoading: false,
      isError: false,
    }),
    useCancelRun: () => ({
      mutate: vi.fn(),
      isPending: false,
    }),
  }));

  vi.doMock("@/queries/workflows", () => ({
    useWorkflow: (workflowId: string) => ({
      data: workflowId ? mockState.workflow : undefined,
      isLoading: false,
      isError: false,
    }),
  }));

  vi.doMock("@/store/canvas", () => ({
    useCanvasStore,
  }));

  vi.doMock("@/api/git", () => ({
    gitApi: {
      getGitFile: mockState.getGitFile,
    },
  }));

  vi.doMock("../SurfaceCanvas", async () => {
    const actual = await vi.importActual<typeof import("../SurfaceCanvas")>(
      "../SurfaceCanvas",
    );

    return {
      ...actual,
      SurfaceCanvas: (props: WorkflowCanvasProps) => {
        workflowCanvasRenderSpy({
          isDraggable: props.isDraggable ?? true,
          connectionsAllowed: props.connectionsAllowed ?? true,
          deletionAllowed: props.deletionAllowed ?? true,
          runId: props.runId,
        });

        return React.createElement(
          "div",
          {
            "data-testid": "workflow-canvas-path",
            "data-draggable": String(props.isDraggable ?? true),
            "data-connectable": String(props.connectionsAllowed ?? true),
            "data-delete-key": String(
              (props.deletionAllowed ?? true) ? "Backspace" : null,
            ),
          },
          React.createElement(actual.SurfaceCanvas, props),
        );
      },
    };
  });

  vi.doMock("../SurfaceTopbar", () => ({
    SurfaceTopbar: ({
      onValueChange,
    }: {
      onValueChange: (value: string) => void;
    }) =>
      React.createElement(
        "div",
        { "data-testid": "canvas-topbar" },
        React.createElement(
          "button",
          { type: "button", onClick: () => onValueChange("canvas") },
          "Canvas",
        ),
        React.createElement(
          "button",
          { type: "button", onClick: () => onValueChange("yaml") },
          "YAML",
        ),
      ),
  }));

  vi.doMock("../SurfaceBottomPanel", () => ({
    SurfaceBottomPanel: () =>
      React.createElement("div", { "data-testid": "canvas-bottom-panel" }, "bottom panel"),
  }));

  vi.doMock("../SurfaceStatusBar", () => ({
    SurfaceStatusBar: () =>
      React.createElement("div", { "data-testid": "canvas-status-bar" }, "status bar"),
  }));

  vi.doMock("../SurfaceYamlEditor", () => ({
    SurfaceYamlEditor: () =>
      React.createElement("div", { "data-testid": "yaml-editor" }, "yaml"),
  }));

  vi.doMock("@/components/provider/ProviderModal", () => ({
    ProviderModal: () => null,
  }));

  vi.doMock("@/features/git/CommitDialog", () => ({
    CommitDialog: () => null,
  }));

  vi.doMock("@runsight/ui/empty-state", () => ({
    EmptyState: ({
      title,
      description,
    }: {
      title: string;
      description: string;
    }) =>
      React.createElement(
        "div",
        { "data-testid": "empty-state" },
        React.createElement("div", null, title),
        React.createElement("div", null, description),
      ),
  }));

  vi.doMock("@xyflow/react", () => {
    const Background = () => React.createElement("div", { "data-testid": "rf-background" });
    const Controls = () => React.createElement("div", { "data-testid": "rf-controls" });
    const MiniMap = () => React.createElement("div", { "data-testid": "rf-minimap" });
    const Handle = () => React.createElement("div", { "data-testid": "rf-handle" });

    const ReactFlow = ({
      nodes,
      nodeTypes,
      onNodeClick,
      onPaneClick,
      nodesDraggable,
      nodesConnectable,
      deleteKeyCode,
      children,
    }: {
      nodes: MockNode[];
      nodeTypes: Record<string, React.ComponentType<Record<string, unknown>>>;
      onNodeClick?: (event: unknown, node: MockNode) => void;
      onPaneClick?: (event: unknown) => void;
      nodesDraggable: boolean;
      nodesConnectable: boolean;
      deleteKeyCode: string | null;
      children?: React.ReactNode;
    }) =>
      React.createElement(
        "div",
        {
          "data-testid": "reactflow-host",
          "data-draggable": String(nodesDraggable),
          "data-connectable": String(nodesConnectable),
          "data-delete-key": String(deleteKeyCode),
        },
        React.createElement(
          "button",
          { type: "button", onClick: () => onPaneClick?.({}) },
          "Canvas Pane",
        ),
        ...nodes.map((node) => {
          const NodeComponent = nodeTypes[node.type];
          return React.createElement(
            "div",
            {
              key: node.id,
              "data-testid": `rf-node-${node.id}`,
              onClick: () => onNodeClick?.({}, node),
            },
            NodeComponent
              ? React.createElement(NodeComponent, {
                  id: node.id,
                  data: node.data,
                  selected: canvasStoreState.selectedNodeId === node.id,
                })
              : React.createElement("div", null, String(node.data.name ?? node.id)),
          );
        }),
        children,
      );

    return {
      ReactFlow,
      Background,
      Controls,
      MiniMap,
      Handle,
      BackgroundVariant: { Dots: "dots" },
      Position: { Top: "top", Bottom: "bottom" },
    };
  });
}

async function loadWorkflowSurface() {
  vi.resetModules();
  installMocks();
  const module = await import("../WorkflowSurface");
  return module.WorkflowSurface;
}

async function renderSurface(props: {
  mode: "readonly" | "edit";
  workflowId?: string;
  runId?: string;
}) {
  const WorkflowSurface = await loadWorkflowSurface();

  render(
    React.createElement(
      MemoryRouter,
      undefined,
      React.createElement(WorkflowSurface, props),
    ),
  );
}

async function showCanvasTab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Canvas" }));
}

beforeEach(() => {
  cleanup();
  resetHarness();
});

afterEach(() => {
  cleanup();
});

describe("RUN-778 shared canvas path", () => {
  it("renders readonly review through the WorkflowCanvas path and opens the shared inspector on node click", async () => {
    const user = userEvent.setup();
    mockState.workflow = buildWorkflow();
    mockState.run = buildRun();
    mockState.runNodes = [{ node_id: "node_soul", status: "completed" }];

    await renderSurface({
      mode: "readonly",
      runId: "run_778",
    });

    const center = screen.getByTestId("surface-center");
    await showCanvasTab(user);

    const canvasPath = await within(center).findByTestId("workflow-canvas-path");
    expect(screen.getAllByTestId("workflow-canvas-path")).toHaveLength(1);
    expect(workflowCanvasRenderSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        isDraggable: false,
        connectionsAllowed: false,
        deletionAllowed: false,
      }),
    );
    expect(within(canvasPath).getByTestId("reactflow-host")).not.toBeNull();
    expect(within(center).queryByTestId("yaml-editor")).toBeNull();
    expect(screen.getByText(/research soul/i)).not.toBeNull();
    expect(screen.getByText(/status:\s*completed/i)).not.toBeNull();

    await user.click(screen.getByText(/research soul/i));

    expect(screen.getByRole("tab", { name: "Execution" })).not.toBeNull();
    expect(screen.getByRole("tab", { name: "Overview" })).not.toBeNull();
  });

  it("closes the shared inspector when the pane is clicked", async () => {
    const user = userEvent.setup();
    mockState.workflow = buildWorkflow();
    mockState.run = buildRun();
    mockState.runNodes = [{ node_id: "node_soul", status: "completed" }];

    await renderSurface({
      mode: "readonly",
      runId: "run_778",
    });

    const center = screen.getByTestId("surface-center");
    await showCanvasTab(user);
    expect(await within(center).findByTestId("workflow-canvas-path")).not.toBeNull();
    expect(screen.getAllByTestId("workflow-canvas-path")).toHaveLength(1);

    await user.click(await screen.findByText(/research soul/i));
    expect(screen.getByRole("tab", { name: "Execution" })).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Canvas Pane" }));

    expect(screen.queryByRole("tab", { name: "Execution" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Overview" })).toBeNull();
  });

  it("renders the shared-path run-node error card with Retry", async () => {
    const user = userEvent.setup();
    mockState.workflow = buildWorkflow();
    mockState.run = buildRun();
    mockState.runNodes = [];
    mockState.runNodesIsError = true;
    mockState.runNodesError = new Error("run nodes exploded");

    await renderSurface({
      mode: "readonly",
      runId: "run_778",
    });

    const center = screen.getByTestId("surface-center");
    await showCanvasTab(user);

    expect(await within(center).findByText("Unable to load run graph")).not.toBeNull();
    expect(screen.queryByTestId("workflow-canvas-path")).toBeNull();
    expect(
      within(center).getByText(/could not read the node response for this run/i),
    ).not.toBeNull();
    fireEvent.click(within(center).getByRole("button", { name: "Retry" }));
    expect(mockState.refetchRunNodes).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("surface-bottom-panel")).not.toBeNull();
    expect(screen.getByTestId("surface-status-bar")).not.toBeNull();
  });

  it("renders the shared-path pre-execution failure card when the run has no nodes", async () => {
    const user = userEvent.setup();
    mockState.workflow = buildWorkflow();
    mockState.run = buildRun({
      status: "failed",
      error: "Provider configuration missing",
    });
    mockState.runNodes = [];

    await renderSurface({
      mode: "readonly",
      runId: "run_778",
    });

    const center = screen.getByTestId("surface-center");
    expect(screen.queryByText("Run failed before execution started")).toBeNull();

    await showCanvasTab(user);

    expect(
      await within(center).findByText("Run failed before execution started"),
    ).not.toBeNull();
    expect(screen.queryByTestId("workflow-canvas-path")).toBeNull();
    expect(
      within(center).getByText(/could not prepare this workflow for execution/i),
    ).not.toBeNull();
    expect(within(center).getByText("Provider configuration missing")).not.toBeNull();
    expect(screen.getByTestId("surface-topbar")).not.toBeNull();
    expect(screen.getByTestId("surface-bottom-panel")).not.toBeNull();
    expect(screen.getByTestId("surface-status-bar")).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "YAML" }));
    expect(await within(center).findByTestId("yaml-editor")).not.toBeNull();

    await showCanvasTab(user);
    expect(
      await within(center).findByText("Run failed before execution started"),
    ).not.toBeNull();
  });

  it("keeps edit and readonly on the same canonical WorkflowCanvas host with runtime interaction changes", async () => {
    const readonlyUser = userEvent.setup();
    mockState.workflow = buildWorkflow();
    mockState.run = buildRun();
    mockState.runNodes = [{ node_id: "node_soul", status: "completed" }];

    await renderSurface({
      mode: "readonly",
      runId: "run_778",
    });

    const readonlyCenter = screen.getByTestId("surface-center");
    await showCanvasTab(readonlyUser);

    const readonlyCanvasPath = await within(readonlyCenter).findByTestId(
      "workflow-canvas-path",
    );
    expect(screen.getAllByTestId("workflow-canvas-path")).toHaveLength(1);
    expect(workflowCanvasRenderSpy).toHaveBeenCalledTimes(1);
    expect(readonlyCanvasPath.getAttribute("data-draggable")).toBe("false");
    expect(readonlyCanvasPath.getAttribute("data-connectable")).toBe("false");
    expect(readonlyCanvasPath.getAttribute("data-delete-key")).toBe("null");
    expect(within(readonlyCanvasPath).getByTestId("reactflow-host")).not.toBeNull();
    expect(within(readonlyCanvasPath).getByTestId("rf-node-node_soul")).not.toBeNull();

    cleanup();
    resetHarness();
    mockState.workflow = buildWorkflow();
    const editUser = userEvent.setup();

    await renderSurface({
      mode: "edit",
      workflowId: "wf_shared_canvas",
    });

    const editCenter = screen.getByTestId("surface-center");
    await showCanvasTab(editUser);

    const editCanvasPath = await within(editCenter).findByTestId(
      "workflow-canvas-path",
    );
    expect(screen.getAllByTestId("workflow-canvas-path")).toHaveLength(1);
    expect(workflowCanvasRenderSpy).toHaveBeenCalledTimes(1);
    expect(editCanvasPath.getAttribute("data-draggable")).toBe("true");
    expect(editCanvasPath.getAttribute("data-connectable")).toBe("true");
    expect(editCanvasPath.getAttribute("data-delete-key")).toBe("Backspace");
    expect(within(editCanvasPath).getByTestId("reactflow-host")).not.toBeNull();
    expect(within(editCanvasPath).getByTestId("rf-node-node_soul")).not.toBeNull();
  });
});
