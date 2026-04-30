import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const mocks = vi.hoisted(() => {
  const state = {
    activeRunId: null as string | null,
    setActiveRunId: vi.fn(),
    nodes: [
      {
        id: "draft-soul-node",
        type: "soul",
        position: { x: 10, y: 20 },
        data: { label: "Draft node" },
      },
    ],
    blockCount: 1,
    isDirty: false,
    yamlContent: "workflow:\n  name: Run Gate Flow\n",
  };

  const useCanvasStore = ((selector: (store: typeof state) => unknown) =>
    selector(state)) as {
    (selector: (store: typeof state) => unknown): unknown;
    getState: () => typeof state;
  };
  useCanvasStore.getState = () => state;

  return {
    buttonProps: [] as Array<{ onClick?: () => Promise<void> | void }>,
    getGitStatus: vi.fn(),
    createSimulationSnapshot: vi.fn(),
    createRunMutate: vi.fn(),
    cancelRunMutate: vi.fn(),
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
  XIcon: () => React.createElement("span", null, "x"),
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
    data: { items: [{ id: "active-provider", is_active: true }] },
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    getStatus: mocks.getGitStatus,
    createSimBranch: mocks.createSimulationSnapshot,
  },
}));

vi.mock("react-router", () => ({
  useNavigate: () => vi.fn(),
}));

import { RunButton } from "../../surface/RunButton";

function renderButton(
  workflowId = "run_gate_flow",
  extraProps: Record<string, unknown> = {},
) {
  mocks.buttonProps.length = 0;
  renderToStaticMarkup(
    React.createElement(RunButton as React.ComponentType<any>, {
      workflowId,
      ...extraProps,
    }),
  );
  const button = mocks.buttonProps.at(-1);
  expect(button?.onClick).toBeTypeOf("function");
  return button!.onClick!;
}

beforeEach(() => {
  mocks.buttonProps.length = 0;
  mocks.state.activeRunId = null;
  mocks.state.setActiveRunId.mockReset();
  mocks.state.nodes = [
    {
      id: "draft-soul-node",
      type: "soul",
      position: { x: 10, y: 20 },
      data: { label: "Draft node" },
    },
  ];
  mocks.state.blockCount = 1;
  mocks.state.isDirty = false;
  mocks.state.yamlContent = "workflow:\n  name: Run Gate Flow\n";
  mocks.getGitStatus.mockReset();
  mocks.getGitStatus.mockResolvedValue({
    branch: "main",
    is_clean: true,
    uncommitted_files: [],
  });
  mocks.createSimulationSnapshot.mockReset();
  mocks.createRunMutate.mockReset();
  mocks.cancelRunMutate.mockReset();
});

describe("Run gating and wiring", () => {
  it("uncommitted clean workflows still create a simulation branch instead of running on main", async () => {
    mocks.createSimulationSnapshot.mockResolvedValue({
      branch: "sim/run-gate-flow/20260403/abc12",
      commit_sha: "deadbeefcafebabe",
    });

    const click = renderButton("uncommitted_run_gate_flow", { isCommitted: false });

    await click();

    expect(mocks.createSimulationSnapshot).toHaveBeenCalledTimes(1);
    expect(mocks.createSimulationSnapshot).toHaveBeenCalledWith(
      "uncommitted_run_gate_flow",
      "workflow:\n  name: Run Gate Flow\n",
    );
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "uncommitted_run_gate_flow",
        inputs: {},
        source: "simulation",
        branch: "sim/run-gate-flow/20260403/abc12",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(mocks.createRunMutate.mock.calls[0]?.[0]?.branch).not.toBe("main");
  });

  it("committed dirty workflows still create a simulation branch instead of running on main", async () => {
    mocks.state.isDirty = true;
    mocks.createSimulationSnapshot.mockResolvedValue({
      branch: "sim/run-gate-flow/20260403/dirty-ab12",
      commit_sha: "deadbeefcafebabe",
    });

    const click = renderButton("committed_dirty_run_gate_flow", { isCommitted: true });

    await click();

    expect(mocks.createSimulationSnapshot).toHaveBeenCalledTimes(1);
    expect(mocks.createSimulationSnapshot).toHaveBeenCalledWith(
      "committed_dirty_run_gate_flow",
      "workflow:\n  name: Run Gate Flow\n",
    );
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "committed_dirty_run_gate_flow",
        inputs: {},
        source: "simulation",
        branch: "sim/run-gate-flow/20260403/dirty-ab12",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(mocks.createRunMutate.mock.calls[0]?.[0]?.source).toBe("simulation");
  });

  it("committed clean workflows run on main without creating a simulation branch", async () => {
    const click = renderButton("committed_clean_run_gate_flow", { isCommitted: true });

    await click();

    expect(mocks.createSimulationSnapshot).not.toHaveBeenCalled();
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "committed_clean_run_gate_flow",
        inputs: {},
        source: "manual",
        branch: "main",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });
});
