// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => {
  const canvasStoreState = {
    activeRunId: null as string | null,
    setActiveRunId: vi.fn(),
    blockCount: 1,
    edgeCount: 0,
    yamlContent: "workflow:\n  name: Canvas flow\n",
    toPersistedState: () => ({
      nodes: [{ id: "node-1" }],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    }),
  };

  const useCanvasStore = ((selector: (store: typeof canvasStoreState) => unknown) =>
    selector(canvasStoreState)) as {
    (selector: (store: typeof canvasStoreState) => unknown): unknown;
    getState: () => typeof canvasStoreState;
  };
  useCanvasStore.getState = () => canvasStoreState;

  const workflowState = {
    data: {
      id: "wf_canvas",
      name: "Canvas flow",
      commit_sha: null as string | null,
    },
  };

  const queryClient = {
    invalidateQueries: vi.fn(),
  };

  return {
    canvasStoreState,
    useCanvasStore,
    workflowState,
    queryClient,
    createRunMutate: vi.fn(),
    createSimBranch: vi.fn(),
    dirtyApplied: false,
    canvasEditorDirty: false,
  };
});

vi.mock("react-router", () => ({
  useParams: () => ({ id: "wf_canvas" }),
  useBlocker: () => ({ state: "unblocked", proceed: vi.fn(), reset: vi.fn() }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mocks.queryClient,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => mocks.workflowState,
  useWorkflowRegressions: () => ({ data: { count: 0 } }),
  useUpdateWorkflow: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => ({ data: { items: [{ id: "provider-1", is_active: true }] } }),
}));

vi.mock("@/queries/git", () => ({
  useGitStatus: () => ({ data: { is_clean: true, uncommitted_files: [] } }),
}));

vi.mock("@/components/shared/PriorityBanner", () => ({
  PriorityBanner: () => null,
}));

vi.mock("@/queries/runs", () => ({
  useCreateRun: () => ({
    mutate: mocks.createRunMutate,
    isPending: false,
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    createSimBranch: mocks.createSimBranch,
  },
}));

vi.mock("../CanvasTopbar", () => ({
  CanvasTopbar: ({
    workflowId,
    onAddApiKey,
  }: {
    workflowId: string;
    onAddApiKey?: () => void;
  }) =>
    React.createElement(
      "div",
      null,
      React.createElement("span", null, workflowId),
      React.createElement(
        "button",
        { type: "button", onClick: onAddApiKey },
        "Open save-and-run modal",
      ),
    ),
}));

vi.mock("../WorkflowCanvas", () => ({
  WorkflowCanvas: () => React.createElement("div", null, "workflow-canvas"),
}));

vi.mock("../YamlEditor", () => ({
  YamlEditor: ({
    onDirtyChange,
  }: {
    onDirtyChange?: (dirty: boolean) => void;
  }) => {
    React.useEffect(() => {
      mocks.dirtyApplied = true;
      onDirtyChange?.(mocks.canvasEditorDirty);
    }, [onDirtyChange]);

    return React.createElement("div", null, "yaml-editor");
  },
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: ({
    open,
    onSaveSuccess,
  }: {
    open: boolean;
    onSaveSuccess?: (providerId: string) => void;
  }) =>
    open
      ? React.createElement(
          "button",
          {
            type: "button",
            onClick: () => onSaveSuccess?.("provider-1"),
          },
          "Save provider",
        )
      : null,
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: () => null,
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

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({
    open,
    children,
  }: {
    open: boolean;
    children: React.ReactNode;
  }) => (open ? React.createElement(React.Fragment, null, children) : null),
  DialogContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogTitle: ({ children }: { children: React.ReactNode }) =>
    React.createElement("h2", null, children),
  DialogFooter: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) =>
    React.createElement(
      "button",
      { type: "button", onClick },
      children,
    ),
}));

vi.mock("@runsight/ui/tabs", () => ({
  Tabs: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  TabsList: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  TabsTrigger: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: () => null,
}));

vi.mock("lucide-react", () => ({
  Save: () => React.createElement("span", null, "save"),
  Play: () => React.createElement("span", null, "play"),
  X: () => React.createElement("span", null, "x"),
  Key: () => React.createElement("span", null, "key"),
}));

import { Component as CanvasPage } from "../CanvasPage";

function renderCanvasPage() {
  const user = userEvent.setup();
  render(React.createElement(CanvasPage));
  return user;
}

async function runSaveAndRunFlow() {
  const user = renderCanvasPage();

  await waitFor(() => expect(mocks.dirtyApplied).toBe(true));
  await user.click(screen.getByRole("button", { name: "Open save-and-run modal" }));
  await user.click(await screen.findByRole("button", { name: "Save provider" }));
}

beforeEach(() => {
  mocks.createRunMutate.mockReset();
  mocks.createSimBranch.mockReset();
  mocks.queryClient.invalidateQueries.mockReset();
  mocks.canvasStoreState.setActiveRunId.mockReset();
  mocks.canvasStoreState.yamlContent = "workflow:\n  name: Canvas flow\n";
  mocks.canvasEditorDirty = false;
  mocks.dirtyApplied = false;
  mocks.workflowState.data.commit_sha = null;
});

afterEach(() => {
  cleanup();
});

describe("CanvasPage run gating (RUN-588)", () => {
  it("uncommitted clean workflows save-and-run through a simulation branch", async () => {
    mocks.workflowState.data.commit_sha = null;
    mocks.canvasEditorDirty = false;
    mocks.createSimBranch.mockResolvedValue({
      branch: "sim/wf_canvas",
      commit_sha: "sim-sha-123",
    });

    await runSaveAndRunFlow();

    expect(mocks.createSimBranch).toHaveBeenCalledTimes(1);
    expect(mocks.createSimBranch).toHaveBeenCalledWith(
      "wf_canvas",
      "workflow:\n  name: Canvas flow\n",
    );
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "wf_canvas",
        source: "simulation",
        branch: "sim/wf_canvas",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("committed clean workflows save-and-run on main", async () => {
    mocks.workflowState.data.commit_sha = "abc123def456";
    mocks.canvasEditorDirty = false;

    await runSaveAndRunFlow();

    expect(mocks.createSimBranch).not.toHaveBeenCalled();
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "wf_canvas",
        source: "manual",
        branch: "main",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("committed dirty workflows save-and-run through a simulation branch", async () => {
    mocks.workflowState.data.commit_sha = "abc123def456";
    mocks.canvasEditorDirty = true;
    mocks.createSimBranch.mockResolvedValue({
      branch: "sim/wf_canvas",
      commit_sha: "sim-sha-123",
    });

    await runSaveAndRunFlow();

    expect(mocks.createSimBranch).toHaveBeenCalledTimes(1);
    expect(mocks.createRunMutate).toHaveBeenCalledWith(
      {
        workflow_id: "wf_canvas",
        source: "simulation",
        branch: "sim/wf_canvas",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });
});
