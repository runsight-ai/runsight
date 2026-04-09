// @vitest-environment jsdom

import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

type RunRecord = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: "completed" | "failed" | "running" | "pending";
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

const harness = vi.hoisted(() => ({
  run: null as RunRecord | null,
  workflow: null as WorkflowRecord | null,
  workflowRegressions: { count: 1, issues: [] as Array<Record<string, unknown>> },
  runRegressions: { count: 3, issues: [] as Array<Record<string, unknown>> },
  workflowRegressionsCalls: [] as string[],
  runRegressionsCalls: [] as string[],
  queryClient: { invalidateQueries: vi.fn() },
  canvasStore: {
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
  },
  bottomPanelProps: [] as Array<Record<string, unknown>>,
}));

function installCanvasBottomPanelMock() {
  vi.doMock("@/queries/runs", () => ({
    useRuns: () => ({ data: { items: [] }, isLoading: false, isError: false }),
    useRun: (id: string) => ({
      data: id && harness.run?.id === id ? harness.run : undefined,
      isLoading: false,
      isError: false,
    }),
    useCreateRun: () => ({ mutate: vi.fn(), isPending: false }),
    useCancelRun: () => ({ mutate: vi.fn(), isPending: false }),
    useRunNodes: () => ({ data: [], isLoading: false, isError: false, error: null, refetch: vi.fn() }),
    useRunLogs: () => ({ data: { items: [] }, isLoading: false, isError: false }),
    useRunRegressions: (runId: string) => {
      harness.runRegressionsCalls.push(runId);
      return { data: harness.runRegressions, isLoading: false, isError: false };
    },
  }));

  vi.doMock("@/queries/workflows", () => ({
    useWorkflow: (workflowId: string) => ({
      data: workflowId && harness.workflow?.id === workflowId ? harness.workflow : undefined,
      isLoading: false,
      isError: false,
    }),
    useWorkflowRegressions: (workflowId: string) => {
      harness.workflowRegressionsCalls.push(workflowId);
      return { data: harness.workflowRegressions, isLoading: false, isError: false };
    },
    useUpdateWorkflow: () => ({ mutate: vi.fn() }),
  }));

  vi.doMock("@tanstack/react-query", () => ({
    useQueryClient: () => harness.queryClient,
    useQuery: () => ({ data: undefined, isLoading: false, isError: false }),
  }));

  vi.doMock("@/store/canvas", () => ({
    useCanvasStore: Object.assign(
      (selector?: (state: typeof harness.canvasStore) => unknown) =>
        typeof selector === "function" ? selector(harness.canvasStore) : harness.canvasStore,
      {
        getState: () => harness.canvasStore,
      },
    ),
  }));

  vi.doMock("@/api/git", () => ({
    gitApi: {
      getGitFile: vi.fn().mockResolvedValue({ content: "workflow:\n  name: Demo\n" }),
    },
  }));

  vi.doMock("../CanvasBottomPanel", () => ({
    CanvasBottomPanel: (props: {
      executionSummary?: { tone: "success" | "danger"; text: string };
    }) => {
      const [activeTab, setActiveTab] = React.useState<"logs" | "runs" | "regressions">("logs");

      harness.bottomPanelProps.push(props);

      const bannerToneClass =
        props.executionSummary?.tone === "success"
          ? "bg-success-3 border-success-7 text-success-11"
          : props.executionSummary?.tone === "danger"
            ? "bg-danger-3 border-danger-7 text-danger-11"
            : "";

      return (
        <div data-testid="canvas-bottom-panel">
          <div role="tablist">
            <button data-testid="workflow-logs-tab" role="tab" onClick={() => setActiveTab("logs")}>
              Logs
            </button>
            <button data-testid="workflow-runs-tab" role="tab" onClick={() => setActiveTab("runs")}>
              Runs
            </button>
            <button
              data-testid="workflow-regressions-tab"
              role="tab"
              onClick={() => setActiveTab("regressions")}
            >
              Regressions
            </button>
          </div>
          {activeTab === "logs" ? (
            <div data-testid="workflow-logs-panel">
              {props.executionSummary ? (
                <div
                  data-testid="execution-summary-banner"
                  role="status"
                  data-tone={props.executionSummary.tone}
                  className={bannerToneClass}
                >
                  {props.executionSummary.text}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      );
    },
  }));

  vi.doMock("../CanvasTopbar", () => ({
    CanvasTopbar: () => <div data-testid="canvas-topbar" />,
  }));

  vi.doMock("../YamlEditor", () => ({
    YamlEditor: () => <div data-testid="yaml-editor" />,
  }));

  vi.doMock("../CanvasStatusBar", () => ({
    CanvasStatusBar: () => <div data-testid="status-bar" />,
  }));

  vi.doMock("../WorkflowCanvas", () => ({
    WorkflowCanvas: () => <div data-testid="workflow-canvas" />,
  }));

  vi.doMock("@/components/provider/ProviderModal", () => ({
    ProviderModal: () => null,
  }));

  vi.doMock("@/features/git/CommitDialog", () => ({
    CommitDialog: () => null,
  }));

  vi.doMock("../SurfaceInspectorPanel", () => ({
    SurfaceInspectorPanel: () => null,
  }));

  vi.doMock("../useSurfaceReadonlyHeaderSlots", () => ({
    useSurfaceReadonlyHeaderSlots: () => ({}),
  }));

  vi.doMock("@/components/shared", () => ({
    PriorityBanner: () => null,
  }));
}

async function loadWorkflowSurface() {
  vi.resetModules();
  installCanvasBottomPanelMock();
  return import("../WorkflowSurface");
}

async function loadCanvasBottomPanel() {
  vi.resetModules();
  vi.doUnmock("../CanvasBottomPanel");

  vi.doMock("@tanstack/react-query", () => ({
    useQueryClient: () => harness.queryClient,
    useQuery: () => ({ data: undefined, isLoading: false, isError: false }),
  }));

  vi.doMock("@/queries/runs", () => ({
    useRuns: () => ({ data: { items: [] }, isLoading: false, isError: false }),
    useRunLogs: () => ({ data: { items: [] }, isLoading: false, isError: false }),
    useRunRegressions: (runId: string) => {
      harness.runRegressionsCalls.push(runId);
      return { data: harness.runRegressions, isLoading: false, isError: false };
    },
  }));

  vi.doMock("@/queries/workflows", () => ({
    useWorkflowRegressions: (workflowId: string) => {
      harness.workflowRegressionsCalls.push(workflowId);
      return { data: harness.workflowRegressions, isLoading: false, isError: false };
    },
  }));

  vi.doMock("@/store/canvas", () => ({
    useCanvasStore: Object.assign(
      (selector?: (state: typeof harness.canvasStore) => unknown) =>
        typeof selector === "function" ? selector(harness.canvasStore) : harness.canvasStore,
      {
        getState: () => harness.canvasStore,
      },
    ),
  }));

  vi.doMock("../../runs/RunsTable", () => ({
    RunsTable: () => <div data-testid="runs-table" />,
  }));

  vi.doMock("../../workflows/regressionBadge.utils", () => ({
    formatRegressionTooltip: () => ({
      header: "header",
      lines: ["line"],
    }),
  }));

  vi.doMock("@/components/shared/RegressionTooltipBody", () => ({
    RegressionTooltipBody: () => <div data-testid="regression-tooltip" />,
  }));

  const mod = await import("../CanvasBottomPanel");
  return mod.CanvasBottomPanel;
}

function setReadonlyRun(status: RunRecord["status"]): void {
  harness.run = {
    id: "run_780",
    workflow_id: "wf_780",
    workflow_name: "Bottom Panel Workflow",
    status,
    commit_sha: "commit_780",
    duration_seconds: 75,
    total_tokens: 1234,
    total_cost_usd: 4.2,
    source: "manual",
    error: status === "failed" ? "boom" : null,
  };

  harness.workflow = {
    id: "wf_780",
    name: "Bottom Panel Workflow",
    yaml: "workflow:\n  name: Bottom Panel Workflow\n",
    canvas_state: null,
    commit_sha: "workflow_780",
  };
}

beforeEach(() => {
  cleanup();
  harness.run = null;
  harness.workflow = null;
  harness.workflowRegressions = { count: 1, issues: [] };
  harness.runRegressions = { count: 3, issues: [] };
  harness.workflowRegressionsCalls = [];
  harness.runRegressionsCalls = [];
  harness.bottomPanelProps = [];
  harness.queryClient.invalidateQueries.mockReset();
  harness.canvasStore.setYamlContent.mockReset();
  harness.canvasStore.hydrateFromPersisted.mockReset();
  harness.canvasStore.setNodeStatus.mockReset();
  harness.canvasStore.setActiveRunId.mockReset();
  harness.canvasStore.setRunCost.mockReset();
  harness.canvasStore.selectNode.mockReset();
  harness.canvasStore.reset.mockReset();
  class EventSourceMock {
    addEventListener() {
      return undefined;
    }

    close() {
      return undefined;
    }
  }
  (globalThis as { EventSource?: typeof EventSource }).EventSource = EventSourceMock as unknown as typeof EventSource;
});

describe("WorkflowSurface bottom panel consolidation (RUN-780)", () => {
  it("passes a green completed summary into the shared bottom panel for readonly runs", async () => {
    const user = userEvent.setup();
    setReadonlyRun("completed");
    const { WorkflowSurface } = await loadWorkflowSurface();

  render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_780" workflowId="wf_780" />
      </MemoryRouter>,
    );

    const bottomPanel = screen.getByTestId("canvas-bottom-panel");
    await user.click(within(bottomPanel).getByTestId("workflow-logs-tab"));

    const banner = within(bottomPanel).getByTestId("execution-summary-banner");
    expect(banner.getAttribute("data-tone")).toBe("success");
    expect(banner.textContent).toContain("Run completed in 75s");
    expect(banner.className).toContain("bg-success-3");
  });

  it("passes a red failed summary into the shared bottom panel for readonly runs", async () => {
    const user = userEvent.setup();
    setReadonlyRun("failed");
    const { WorkflowSurface } = await loadWorkflowSurface();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="readonly" runId="run_780" workflowId="wf_780" />
      </MemoryRouter>,
    );

    const bottomPanel = screen.getByTestId("canvas-bottom-panel");
    await user.click(within(bottomPanel).getByTestId("workflow-logs-tab"));

    const banner = within(bottomPanel).getByTestId("execution-summary-banner");
    expect(banner.getAttribute("data-tone")).toBe("danger");
    expect(banner.textContent).toContain("Run failed");
    expect(banner.className).toContain("bg-danger-3");
  });

  it("does not render an execution summary banner in edit mode", async () => {
    setReadonlyRun("completed");
    const { WorkflowSurface } = await loadWorkflowSurface();

    render(
      <MemoryRouter>
        <WorkflowSurface mode="edit" workflowId="wf_780" />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("execution-summary")).toBeNull();
  });

  it("prefers per-run regressions when a runId is available", async () => {
    harness.workflowRegressions = {
      count: 1,
      issues: [{ node_name: "workflow-level regression" }],
    };
    harness.runRegressions = {
      count: 3,
      issues: [{ node_name: "run-level regression" }],
    };

    const CanvasBottomPanel = await loadCanvasBottomPanel();
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <CanvasBottomPanel runId="run_780" workflowId="wf_780" defaultState="expanded" />
      </MemoryRouter>,
    );

    await user.click(screen.getByTestId("workflow-regressions-tab"));

    expect(harness.runRegressionsCalls).toEqual(["run_780"]);
    expect(harness.workflowRegressionsCalls).toEqual([]);
    expect(within(screen.getByTestId("canvas-bottom-panel")).getByText("Regressions (3)")).toBeTruthy();
  });
});

describe("Shared bottom panel consolidation (RUN-780)", () => {
  it("keeps the shared surface free of legacy bottom-panel references", () => {
    const workflowSurface = readFileSync(resolve(__dirname, "../WorkflowSurface.tsx"), "utf-8");

    expect(workflowSurface).not.toMatch(/RunBottomPanel/);
  });
});
