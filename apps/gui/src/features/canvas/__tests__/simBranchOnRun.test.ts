import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const persistedCanvasState = {
    nodes: [
      {
        id: "node-1",
        type: "task",
        position: { x: 10, y: 20 },
        data: { label: "Draft node" },
      },
    ],
    edges: [],
    viewport: { x: 4, y: 8, zoom: 0.75 },
    selected_node_id: "node-1",
    canvas_mode: "dag" as const,
  };

  const state = {
    activeRunId: null as string | null,
    setActiveRunId: vi.fn(),
    nodes: persistedCanvasState.nodes,
    blockCount: 1,
    isDirty: false,
    yamlContent: "workflow:\n  name: Test Flow\n",
    toPersistedState: vi.fn(() => persistedCanvasState),
  };

  const useCanvasStore = ((selector: (store: typeof state) => unknown) =>
    selector(state)) as {
    (selector: (store: typeof state) => unknown): unknown;
    getState: () => typeof state;
  };
  useCanvasStore.getState = () => state;

  return {
    buttonProps: [] as Array<{ onClick?: () => Promise<void> | void }>,
    createSimulationSnapshot: vi.fn(),
    createRunMutate: vi.fn(),
    cancelRunMutate: vi.fn(),
    persistedCanvasState,
    state,
    useCanvasStore,
  };
});

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) => {
    mocks.buttonProps.push(props as { onClick?: () => Promise<void> | void });
    return React.createElement("button", { type: "button" }, props.children);
  },
}));

vi.mock("@runsight/ui/tooltip", () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  Tooltip: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  TooltipContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("span", null, children),
  TooltipTrigger: ({ render }: { render: React.ReactNode }) =>
    React.createElement(React.Fragment, null, render),
}));

vi.mock("lucide-react", () => ({
  Key: () => React.createElement("span", null, "key"),
  Play: () => React.createElement("span", null, "play"),
  X: () => React.createElement("span", null, "x"),
}));

vi.mock("@/queries/runs", () => ({
  useCreateRun: () => ({
    mutate: mocks.createRunMutate,
    isPending: false,
  }),
  useCancelRun: () => ({
    mutate: mocks.cancelRunMutate,
    isPending: false,
  }),
  useRun: () => ({ data: undefined }),
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => ({
    data: { items: [{ id: "provider-1" }] },
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    createSimBranch: mocks.createSimulationSnapshot,
  },
}));

import { RunButton } from "../RunButton";

function renderButton(workflowId = "wf_1") {
  mocks.buttonProps.length = 0;
  renderToStaticMarkup(React.createElement(RunButton, { workflowId }));
  const button = mocks.buttonProps.at(-1);
  expect(button?.onClick).toBeTypeOf("function");
  return button!.onClick!;
}

beforeEach(() => {
  mocks.buttonProps.length = 0;
  mocks.state.activeRunId = null;
  mocks.state.setActiveRunId.mockReset();
  mocks.state.nodes = mocks.persistedCanvasState.nodes;
  mocks.state.blockCount = 1;
  mocks.state.isDirty = false;
  mocks.state.yamlContent = "workflow:\n  name: Test Flow\n";
  mocks.state.toPersistedState.mockReset();
  mocks.state.toPersistedState.mockReturnValue(mocks.persistedCanvasState);
  mocks.createSimulationSnapshot.mockReset();
  mocks.createRunMutate.mockReset();
  mocks.cancelRunMutate.mockReset();
});

describe("RunButton simulation behavior (RUN-423)", () => {
  it("dirty canvas snapshots the in-memory workflow before starting a simulation run", async () => {
    const currentWorkflowId = "wf_live_42";
    const currentYaml = "workflow:\n  name: Live Flow\n  steps:\n    - id: latest-step\n";
    mocks.state.isDirty = true;
    mocks.state.yamlContent = currentYaml;
    mocks.createSimulationSnapshot.mockResolvedValue({
      branch: "sim/test-flow/20260330/abc12",
      commit_sha: "deadbeefcafebabe",
    });

    const click = renderButton(currentWorkflowId);
    await click();

    expect(mocks.createSimulationSnapshot).toHaveBeenCalledTimes(1);
    expect(mocks.createSimulationSnapshot).toHaveBeenCalledWith(
      currentWorkflowId,
      currentYaml,
    );
    expect(mocks.createSimulationSnapshot.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.createRunMutate.mock.invocationCallOrder[0],
    );
    expect(mocks.createRunMutate).toHaveBeenCalledTimes(1);
    expect(mocks.createRunMutate.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        workflow_id: "wf_1",
        source: "simulation",
        branch: "sim/test-flow/20260330/abc12",
      }),
    );
    expect(mocks.createRunMutate.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("clean canvas runs manually from main without creating a simulation snapshot", async () => {
    const click = renderButton();
    await click();

    expect(mocks.createSimulationSnapshot).not.toHaveBeenCalled();
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "wf_1",
        source: "manual",
        branch: "main",
      },
      { onSuccess: expect.any(Function) },
    );
  });
});
