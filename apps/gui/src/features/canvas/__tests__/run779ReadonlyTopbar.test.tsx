// @vitest-environment jsdom

import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

type RunRecord = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: "completed" | "running" | "failed" | "pending";
  commit_sha: string;
  duration_seconds: number;
  total_tokens: number;
  total_cost_usd: number;
  source: string;
  error: string | null;
};

type WorkflowRecord = {
  id: string;
  name: string;
  yaml: string;
  canvas_state?: Record<string, unknown> | null;
  commit_sha: string;
};

const harness = vi.hoisted(() => {
  const canvasStore = {
    nodes: [],
    edges: [],
    blockCount: 0,
    edgeCount: 0,
    yamlContent: "",
    activeRunId: null as string | null,
    setYamlContent: vi.fn(),
    hydrateFromPersisted: vi.fn(),
    setNodeStatus: vi.fn(),
    setActiveRunId: vi.fn(),
    setRunCost: vi.fn(),
    selectNode: vi.fn(),
    reset: vi.fn(),
  };

  return {
    run: null as RunRecord | null,
    workflow: null as WorkflowRecord | null,
    regressionsCount: 0,
    runNodes: [] as Array<Record<string, unknown>>,
    getGitFile: vi.fn(),
    forkWorkflow: vi.fn(),
    forkInvocations: [] as Array<{
      commitSha: string;
      workflowPath: string;
      workflowName: string;
    }>,
    cancelRun: { mutate: vi.fn(), isPending: false },
    queryClient: { invalidateQueries: vi.fn() },
    canvasStore,
  };
});

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => harness.queryClient,
  useQuery: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/queries/runs", () => ({
  useRun: (runId: string) => ({
    data: runId && harness.run?.id === runId ? harness.run : undefined,
    isLoading: false,
    isError: false,
  }),
  useCreateRun: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useRunNodes: (runId: string) => ({
    data: runId && harness.run?.id === runId ? harness.runNodes : [],
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRunRegressions: (runId: string) => ({
    data: runId ? { count: harness.regressionsCount, issues: [] } : undefined,
    isLoading: false,
    isError: false,
  }),
  useCancelRun: () => harness.cancelRun,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: (workflowId: string) => ({
    data: workflowId && harness.workflow?.id === workflowId ? harness.workflow : undefined,
    isLoading: false,
    isError: false,
  }),
  useUpdateWorkflow: () => ({
    mutate: vi.fn(),
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: Object.assign(
    (selector?: (state: typeof harness.canvasStore) => unknown) =>
      typeof selector === "function" ? selector(harness.canvasStore) : harness.canvasStore,
    {
      getState: () => harness.canvasStore,
    },
  ),
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    getGitFile: harness.getGitFile,
  },
}));

vi.mock("../YamlEditor", () => ({
  YamlEditor: () => <div data-testid="yaml-editor" />,
}));

vi.mock("../CanvasBottomPanel", () => ({
  CanvasBottomPanel: () => <div data-testid="bottom-panel" />,
}));

vi.mock("../CanvasStatusBar", () => ({
  CanvasStatusBar: () => <div data-testid="status-bar" />,
}));

vi.mock("../WorkflowCanvas", () => ({
  WorkflowCanvas: () => <div data-testid="workflow-canvas" />,
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => null,
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: () => null,
}));

vi.mock("../SurfaceInspectorPanel", () => ({
  SurfaceInspectorPanel: () => null,
}));

vi.mock("../../runs/useForkWorkflow", () => ({
  useForkWorkflow: (options: {
    commitSha: string;
    workflowPath: string;
    workflowName: string;
    onTransition?: (id: string) => void;
  }) => {
    harness.forkWorkflow.mockImplementation(() => {
      harness.forkInvocations.push({
        commitSha: options.commitSha,
        workflowPath: options.workflowPath,
        workflowName: options.workflowName,
      });
      options.onTransition?.("wf_forked_779");
    });

    return {
      forkWorkflow: harness.forkWorkflow,
      isForking: false,
    };
  },
}));

import { WorkflowSurface } from "../WorkflowSurface";

function setReadonlyFixtures({
  runStatus,
  regressionsCount,
}: {
  runStatus: RunRecord["status"];
  regressionsCount: number;
}) {
  harness.regressionsCount = regressionsCount;
  harness.run = {
    id: "run_779",
    workflow_id: "wf_779",
    workflow_name: "Research Pipeline",
    status: runStatus,
    commit_sha: "commit_779",
    duration_seconds: 75,
    total_tokens: 1234,
    total_cost_usd: 4.2,
    source: "manual",
    error: null,
  };
  harness.workflow = {
    id: "wf_779",
    name: "Research Pipeline",
    yaml: "workflow:\n  name: Research Pipeline\n",
    canvas_state: null,
    commit_sha: "workflow_779",
  };
  harness.runNodes = [];
}

beforeEach(() => {
  harness.run = null;
  harness.workflow = null;
  harness.regressionsCount = 0;
  harness.runNodes = [];
  harness.getGitFile.mockResolvedValue({
    content: "workflow:\n  name: Research Pipeline\n",
  });
  harness.forkWorkflow.mockReset();
  harness.forkInvocations = [];
  harness.cancelRun.mutate.mockReset();
  harness.cancelRun.isPending = false;
  harness.queryClient.invalidateQueries.mockReset();
  harness.canvasStore.setYamlContent.mockReset();
  harness.canvasStore.hydrateFromPersisted.mockReset();
  harness.canvasStore.setNodeStatus.mockReset();
  harness.canvasStore.setActiveRunId.mockReset();
  harness.canvasStore.setRunCost.mockReset();
  harness.canvasStore.selectNode.mockReset();
  harness.canvasStore.reset.mockReset();
});

describe("WorkflowSurface readonly topbar wiring (RUN-779)", () => {
  it("shows completed readonly run metadata, review badge, and fork action", async () => {
    const user = userEvent.setup();
    setReadonlyFixtures({ runStatus: "completed", regressionsCount: 0 });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_779" workflowId="wf_779" />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Fork" }));

    expect(harness.forkWorkflow).toHaveBeenCalledTimes(1);
    expect(harness.forkInvocations[0]).toEqual({
      commitSha: "commit_779",
      workflowPath: "custom/workflows/wf_779.yaml",
      workflowName: "Research Pipeline",
    });
    expect(screen.getByTestId("workflow-save-button")).toBeTruthy();

    expect(screen.getByRole("link", { name: "Research Pipeline" }).getAttribute("href")).toBe(
      "/workflows/wf_779/edit",
    );
    expect(screen.getByText("Completed")).toBeTruthy();
    expect(screen.getByText("Read-only review")).toBeTruthy();
    expect(screen.getByText("1m 15s")).toBeTruthy();
    expect(screen.getByText("1.2k tok")).toBeTruthy();
    expect(screen.getByText("$4.200")).toBeTruthy();
  });

  it("shows the running-state cancel affordance and disables fork with a tooltip", () => {
    setReadonlyFixtures({ runStatus: "running", regressionsCount: 0 });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_779" workflowId="wf_779" />
      </MemoryRouter>,
    );

    expect(screen.getByText("Running")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Fork" }).disabled).toBe(true);
    expect(screen.getByText("Wait for the run to finish before forking")).toBeTruthy();
  });

  it("renders a PriorityBanner when readonly regressions are present", () => {
    setReadonlyFixtures({ runStatus: "completed", regressionsCount: 3 });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_779" workflowId="wf_779" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("status")).toBeTruthy();
    expect(screen.getByText("3 regressions found")).toBeTruthy();
  });

  it("keeps the surface clean when readonly regressions are absent", () => {
    setReadonlyFixtures({ runStatus: "completed", regressionsCount: 0 });

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_779" workflowId="wf_779" />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("status")).toBeNull();
  });
});
