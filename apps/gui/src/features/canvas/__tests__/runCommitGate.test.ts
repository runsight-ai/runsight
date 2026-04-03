import React from "react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const mocks = vi.hoisted(() => {
  const state = {
    activeRunId: null as string | null,
    setActiveRunId: vi.fn(),
    nodes: [
      {
        id: "node-1",
        type: "task",
        position: { x: 10, y: 20 },
        data: { label: "Draft node" },
      },
    ],
    blockCount: 1,
    isDirty: false,
    yamlContent: "workflow:\n  name: Test Flow\n",
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
    data: { items: [{ id: "provider-1", is_active: true }] },
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

function renderButton(
  workflowId = "wf_1",
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
      id: "node-1",
      type: "task",
      position: { x: 10, y: 20 },
      data: { label: "Draft node" },
    },
  ];
  mocks.state.blockCount = 1;
  mocks.state.isDirty = false;
  mocks.state.yamlContent = "workflow:\n  name: Test Flow\n";
  mocks.createSimulationSnapshot.mockReset();
  mocks.createRunMutate.mockReset();
  mocks.cancelRunMutate.mockReset();
});

describe("Run gating and wiring for RUN-588", () => {
  it("uncommitted clean workflows still create a simulation branch instead of running on main", async () => {
    mocks.createSimulationSnapshot.mockResolvedValue({
      branch: "sim/test-flow/20260403/abc12",
      commit_sha: "deadbeefcafebabe",
    });

    const click = renderButton("wf_uncommitted", { isCommitted: false });

    await click();

    expect(mocks.createSimulationSnapshot).toHaveBeenCalledTimes(1);
    expect(mocks.createSimulationSnapshot).toHaveBeenCalledWith(
      "wf_uncommitted",
      "workflow:\n  name: Test Flow\n",
    );
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "wf_uncommitted",
        source: "simulation",
        branch: "sim/test-flow/20260403/abc12",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(mocks.createRunMutate.mock.calls[0]?.[0]?.branch).not.toBe("main");
  });

  it("committed dirty workflows still create a simulation branch instead of running on main", async () => {
    mocks.state.isDirty = true;
    mocks.createSimulationSnapshot.mockResolvedValue({
      branch: "sim/test-flow/20260403/dirty-ab12",
      commit_sha: "deadbeefcafebabe",
    });

    const click = renderButton("wf_committed_dirty", { isCommitted: true });

    await click();

    expect(mocks.createSimulationSnapshot).toHaveBeenCalledTimes(1);
    expect(mocks.createSimulationSnapshot).toHaveBeenCalledWith(
      "wf_committed_dirty",
      "workflow:\n  name: Test Flow\n",
    );
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "wf_committed_dirty",
        source: "simulation",
        branch: "sim/test-flow/20260403/dirty-ab12",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(mocks.createRunMutate.mock.calls[0]?.[0]?.source).toBe("simulation");
  });

  it("committed clean workflows run on main without creating a simulation branch", async () => {
    const click = renderButton("wf_committed_clean", { isCommitted: true });

    await click();

    expect(mocks.createSimulationSnapshot).not.toHaveBeenCalled();
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "wf_committed_clean",
        source: "manual",
        branch: "main",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("RunButton accepts an isCommitted prop for the main-branch gate", () => {
    const source = readSource("features/canvas/RunButton.tsx");
    expect(source).toMatch(/isCommitted/);
  });

  it("RunButton keeps committed-state gating logic in the component", () => {
    const source = readSource("features/canvas/RunButton.tsx");
    expect(source).toMatch(/isCommitted/);
    expect(source).toMatch(/createSimBranch|source:\s*["']simulation["']/);
    expect(source).toMatch(/source:\s*["']manual["']/);
  });

  it("CanvasTopbar passes committed workflow state into RunButton", () => {
    const source = readSource("features/canvas/CanvasTopbar.tsx");
    expect(source).toMatch(/<RunButton[\s\S]*isCommitted/);
    expect(source).toMatch(/workflow[\s\S]*commit_sha|commit_sha[\s\S]*workflow/);
  });
});
