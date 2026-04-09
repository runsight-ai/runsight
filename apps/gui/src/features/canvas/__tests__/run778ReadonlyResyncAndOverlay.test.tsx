// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

type MockNode = {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
};

type MockRunNode = {
  node_id: string;
  status: string;
  cost_usd?: number;
  duration_seconds?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
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
  reset: ReturnType<typeof vi.fn>;
};

const mockState = {
  workflows: {} as Record<string, Record<string, unknown>>,
  runs: {} as Record<string, Record<string, unknown>>,
  runNodesByRunId: {} as Record<string, MockRunNode[]>,
  getGitFile: vi.fn(),
};

let canvasStoreState: CanvasStoreState;
const storeListeners = new Set<() => void>();

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
    setNodeStatus: vi.fn(
      (
        nodeId: string,
        status: string,
        runtime?: {
          executionCost?: number;
          duration?: number;
          tokens?: { input?: number; output?: number; total?: number };
          error?: string | null;
        },
      ) => {
        canvasStoreState.nodes = canvasStoreState.nodes.map((node) =>
          node.id === nodeId
            ? {
                ...node,
                data: {
                  ...node.data,
                  status,
                  ...(runtime ?? {}),
                },
              }
            : node,
        );
        emitStoreChange();
      },
    ),
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
    reset: vi.fn(() => {
      canvasStoreState.nodes = [];
      canvasStoreState.edges = [];
      canvasStoreState.selectedNodeId = null;
      canvasStoreState.yamlContent = "";
      canvasStoreState.activeRunId = null;
      canvasStoreState.runCost = 0;
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
  mockState.workflows = {};
  mockState.runs = {};
  mockState.runNodesByRunId = {};
  mockState.getGitFile.mockReset();
  mockState.getGitFile.mockResolvedValue({
    content: "workflow:\n  name: Shared Canvas Flow\n",
  });
  canvasStoreState = createCanvasStoreState();
  emitStoreChange();
}

function buildWorkflow(
  workflowId: string,
  nodeId: string,
  nodeName: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id: workflowId,
    name: nodeName,
    yaml: `workflow:\n  name: ${nodeName}\n`,
    canvas_state: {
      nodes: [
        {
          id: nodeId,
          type: "soul",
          position: { x: 320, y: 180 },
          data: {
            name: nodeName,
            soulRef: `souls/${nodeId}`,
            model: "gpt-4.1",
            status: "idle",
          },
        },
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    },
    commit_sha: `${workflowId}_sha`,
    ...overrides,
  };
}

function buildRun(
  runId: string,
  workflowId: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id: runId,
    workflow_id: workflowId,
    workflow_name: workflowId,
    status: "completed",
    commit_sha: `${runId}_sha`,
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
      data: runId ? mockState.runs[runId] : undefined,
      isLoading: false,
      isError: false,
    }),
    useRunNodes: (runId: string) => ({
      data: mockState.runNodesByRunId[runId] ?? [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    }),
  }));

  vi.doMock("@/queries/workflows", () => ({
    useWorkflow: (workflowId: string) => ({
      data: workflowId ? mockState.workflows[workflowId] : undefined,
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

  vi.doMock("../CanvasTopbar", () => ({
    CanvasTopbar: ({
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

  vi.doMock("../CanvasBottomPanel", () => ({
    CanvasBottomPanel: () =>
      React.createElement("div", { "data-testid": "canvas-bottom-panel" }, "bottom panel"),
  }));

  vi.doMock("../CanvasStatusBar", () => ({
    CanvasStatusBar: () =>
      React.createElement("div", { "data-testid": "canvas-status-bar" }, "status bar"),
  }));

  vi.doMock("../YamlEditor", () => ({
    YamlEditor: () =>
      React.createElement("div", { "data-testid": "yaml-editor" }, "yaml"),
  }));

  vi.doMock("@/components/provider/ProviderModal", () => ({
    ProviderModal: () => null,
  }));

  vi.doMock("@/features/git/CommitDialog", () => ({
    CommitDialog: () => null,
  }));

  vi.doMock("@runsight/ui/empty-state", () => ({
    EmptyState: ({ title }: { title: string }) =>
      React.createElement("div", { "data-testid": "empty-state" }, title),
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
      children,
    }: {
      nodes: MockNode[];
      nodeTypes: Record<string, React.ComponentType<Record<string, unknown>>>;
      onNodeClick?: (event: unknown, node: MockNode) => void;
      onPaneClick?: (event: unknown) => void;
      children?: React.ReactNode;
    }) =>
      React.createElement(
        "div",
        { "data-testid": "reactflow-host" },
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

beforeEach(() => {
  cleanup();
  resetHarness();
});

afterEach(() => {
  cleanup();
});

describe("RUN-778 readonly resync and execution overlay", () => {
  it("resyncs readonly route props and clears stale topology on rerender", async () => {
    const user = userEvent.setup();
    const WorkflowSurface = await loadWorkflowSurface();

    mockState.workflows.wf_a = buildWorkflow("wf_a", "node_alpha", "Alpha Soul");
    mockState.workflows.wf_b = buildWorkflow("wf_b", "node_beta", "Beta Soul");
    mockState.runs.run_a = buildRun("run_a", "wf_a");
    mockState.runs.run_b = buildRun("run_b", "wf_b");
    mockState.runNodesByRunId.run_a = [{ node_id: "node_alpha", status: "completed" }];
    mockState.runNodesByRunId.run_b = [{ node_id: "node_beta", status: "failed" }];

    const view = render(
      React.createElement(
        MemoryRouter,
        undefined,
        React.createElement(WorkflowSurface, { mode: "readonly", runId: "run_a" }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Canvas" }));
    expect(await screen.findByText("Alpha Soul")).not.toBeNull();

    await user.click(screen.getByText("Alpha Soul"));
    expect(screen.getByRole("tab", { name: "Execution" })).not.toBeNull();

    view.rerender(
      React.createElement(
        MemoryRouter,
        undefined,
        React.createElement(WorkflowSurface, { mode: "readonly", runId: "run_b" }),
      ),
    );

    expect(await screen.findByText("Beta Soul")).not.toBeNull();
    await waitFor(() => {
      expect(screen.queryByText("Alpha Soul")).toBeNull();
    });
    expect(screen.queryByRole("tab", { name: "Execution" })).toBeNull();
    expect(screen.getByText(/status:\s*failed/i)).not.toBeNull();
  });

  it("overlays execution data into the shared inspector", async () => {
    const user = userEvent.setup();
    const WorkflowSurface = await loadWorkflowSurface();

    mockState.workflows.wf_exec = buildWorkflow("wf_exec", "node_exec", "Execution Soul");
    mockState.runs.run_exec = buildRun("run_exec", "wf_exec");
    mockState.runNodesByRunId.run_exec = [
      {
        node_id: "node_exec",
        status: "failed",
        cost_usd: 0.456,
        duration_seconds: 32,
        tokens: { input: 100, output: 25, total: 125 },
        error: "node exploded",
      },
    ];

    render(
      React.createElement(
        MemoryRouter,
        undefined,
        React.createElement(WorkflowSurface, { mode: "readonly", runId: "run_exec" }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Canvas" }));
    expect(await screen.findByText("Execution Soul")).not.toBeNull();

    await user.click(screen.getByText("Execution Soul"));

    expect(screen.getByRole("tab", { name: "Execution" })).not.toBeNull();
    expect(screen.getByText("Duration: 32s")).not.toBeNull();
    expect(screen.getByText("$0.456")).not.toBeNull();
    expect(screen.getByText("125 tokens")).not.toBeNull();
    expect(screen.getByText("node exploded")).not.toBeNull();
  });
});
