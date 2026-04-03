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
        branch: expect.stringMatching(/^sim\//),
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(mocks.createRunMutate.mock.calls[0]?.[0]?.branch).not.toBe("main");
  });

  it("RunButton accepts an isCommitted prop for the main-branch gate", () => {
    const source = readSource("features/canvas/RunButton.tsx");
    expect(source).toMatch(/isCommitted/);
  });

  it("RunButton gates execution on isDirty || !isCommitted", () => {
    const source = readSource("features/canvas/RunButton.tsx");
    expect(source).toMatch(/isDirty\s*\|\|\s*!isCommitted/);
  });

  it("CanvasTopbar passes workflow.commit_sha into RunButton as isCommitted", () => {
    const source = readSource("features/canvas/CanvasTopbar.tsx");
    expect(source).toMatch(/<RunButton[\s\S]*isCommitted\s*=\s*\{!!workflow\?\.commit_sha\}/);
  });

  it("CanvasPage reads workflow data and uses the same run gate", () => {
    const source = readSource("features/canvas/CanvasPage.tsx");
    expect(source).toMatch(/useWorkflow\(id!\)/);
    expect(source).toMatch(/isDirty\s*\|\|\s*!isCommitted/);
  });
});
