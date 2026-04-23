// @vitest-environment jsdom

import React from "react";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RunResponse } from "@runsight/shared/zod";
import { ApiError } from "@/api/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

type WorkflowInputSchemaItem = {
  type: "string" | "number" | "boolean" | "json" | "array";
  required?: boolean | null;
  default?: unknown;
  description?: string | null;
  sensitive?: boolean | null;
};

type WorkflowSnapshotEntry = {
  type: string;
  sensitive: boolean;
  source: string;
  value?: unknown;
};

type WorkflowRecord = {
  id: string;
  name: string;
  input_schema: Record<string, WorkflowInputSchemaItem> | null;
  commit_sha?: string | null;
};

const harness = vi.hoisted(() => {
  const canvasState = {
    activeRunId: null as string | null,
    isDirty: false,
    yamlContent: "id: wf_run_925_current\nkind: workflow\nversion: '1.0'\n",
    setNodeStatus: vi.fn(),
    setActiveRunId: vi.fn(),
    setRunCost: vi.fn(),
  };

  const contextAuditState = {
    eventsByRun: {} as Record<string, unknown[]>,
    replaceRunEvents: vi.fn(),
  };

  return {
    runs: [] as RunResponse[],
    workflows: {} as Record<string, WorkflowRecord>,
    createRunRequest: vi.fn(),
    prepareSimulation: vi.fn(),
    toastError: vi.fn(),
    navigate: vi.fn(),
    canvasState,
    contextAuditState,
  };
});

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({
    open,
    onOpenChange,
    children,
  }: {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    children?: React.ReactNode;
  }) => {
    if (!open) {
      return null;
    }

    return React.createElement(
      React.Fragment,
      null,
      React.createElement(
        "div",
        {
          "data-testid": "dialog-shell",
          onKeyDown: (event: React.KeyboardEvent) => {
            if (event.key === "Escape") {
              onOpenChange?.(false);
            }
          },
        },
        children,
      ),
    );
  },
  DialogContent: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", { role: "dialog" }, children),
  DialogHeader: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogTitle: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("h2", null, children),
  DialogBody: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogFooter: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogOverlay: () => null,
  DialogPortal: ({ children }: { children?: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  DialogClose: ({
    render,
    children,
    ...props
  }: {
    render?: React.ReactElement;
    children?: React.ReactNode;
  }) => {
    const onClick = () => undefined;

    if (React.isValidElement(render)) {
      return React.cloneElement(
        render,
        {
          ...render.props,
          ...props,
          onClick,
        },
        children,
      );
    }

    return React.createElement("button", { type: "button", ...props, onClick }, children);
  },
  DialogTrigger: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("button", { type: "button" }, children),
}));

vi.mock("@/queries/runs", () => ({
  useRuns: () => ({
    data: { items: harness.runs },
    isLoading: false,
    isError: false,
  }),
  useRunLogs: () => ({
    data: { items: [] },
    isLoading: false,
    isError: false,
  }),
  useRunContextAuditStream: () => undefined,
  useRunContextAudit: () => ({
    fetchNextPage: vi.fn(),
    hasNextPage: false,
  }),
  useRunRegressions: () => ({
    data: { count: 0, issues: [] },
    isLoading: false,
    isError: false,
  }),
  useCreateRun: () => ({
    mutate: (variables: Record<string, unknown>, options?: {
      onSuccess?: (data: { id: string }, variables: Record<string, unknown>) => void;
      onError?: (error: unknown, variables: Record<string, unknown>) => void;
    }) => {
      const promise = Promise.resolve().then(() => harness.createRunRequest(variables));
      void promise.then(
        (data) => options?.onSuccess?.(data as { id: string }, variables),
        (error) => options?.onError?.(error, variables),
      );
      return promise;
    },
    mutateAsync: (variables: Record<string, unknown>) =>
      Promise.resolve().then(() => harness.createRunRequest(variables)),
    isPending: false,
  }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: (workflowId: string) => ({
    data: harness.workflows[workflowId] ?? null,
    isLoading: false,
    isError: false,
  }),
  useWorkflowRegressions: () => ({
    data: { count: 0, issues: [] },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: Object.assign(
    (selector?: (state: typeof harness.canvasState) => unknown) =>
      typeof selector === "function" ? selector(harness.canvasState) : harness.canvasState,
    {
      getState: () => harness.canvasState,
    },
  ),
}));

vi.mock("@/store/contextAudit", () => ({
  useContextAuditStore: Object.assign(
    (selector?: (state: typeof harness.contextAuditState) => unknown) =>
      typeof selector === "function" ? selector(harness.contextAuditState) : harness.contextAuditState,
    {
      getState: () => harness.contextAuditState,
    },
  ),
}));

vi.mock("react-router", () => ({
  useNavigate: () => harness.navigate,
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    createSimBranch: (...args: unknown[]) => harness.prepareSimulation(...args),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => harness.toastError(...args),
  },
}));

const { SurfaceBottomPanel } = await import("../SurfaceBottomPanel");

const CURRENT_WORKFLOW_ID = "wf_run_925_current";
const CURRENT_WORKFLOW: WorkflowRecord = {
  id: CURRENT_WORKFLOW_ID,
  name: "Rerun Input Workflow",
  commit_sha: "abcdef1234567890",
  input_schema: {
    query: {
      type: "string",
      required: true,
      default: null,
      description: "Search term",
      sensitive: false,
    },
    api_token: {
      type: "string",
      required: true,
      default: null,
      description: "Secret token",
      sensitive: true,
    },
  },
};

const SIMPLE_WORKFLOW: WorkflowRecord = {
  id: CURRENT_WORKFLOW_ID,
  name: "Rerun Input Workflow",
  commit_sha: "abcdef1234567890",
  input_schema: {
    query: {
      type: "string",
      required: true,
      default: null,
      description: "Search term",
      sensitive: false,
    },
  },
};

const EMPTY_WORKFLOW: WorkflowRecord = {
  id: CURRENT_WORKFLOW_ID,
  name: "Rerun Input Workflow",
  commit_sha: "abcdef1234567890",
  input_schema: null,
};

function makeRun(
  overrides: Partial<RunResponse> & {
    workflow_inputs?: Record<string, WorkflowSnapshotEntry> | null;
  } = {},
): RunResponse {
  return {
    id: "run_925",
    workflow_id: CURRENT_WORKFLOW_ID,
    workflow_name: "Rerun Input Workflow",
    status: "completed",
    started_at: 1_776_120_000,
    completed_at: 1_776_120_030,
    duration_seconds: 30,
    total_cost_usd: 0.01,
    total_tokens: 42,
    created_at: 1_776_119_999,
    branch: "main",
    source: "manual",
    commit_sha: "abcdef1234567890",
    run_number: 12,
    eval_pass_pct: 95,
    eval_score_avg: 0.95,
    regression_count: 0,
    warnings: [],
    workflow_inputs: null,
    workflow_input_schema: null,
    ...overrides,
  } as RunResponse;
}

function renderSurfaceBottomPanel() {
  render(
    <SurfaceBottomPanel
      workflowId={CURRENT_WORKFLOW_ID}
      defaultState="expanded"
    />,
  );
}

function getDataRow() {
  const rows = screen.getAllByRole("row");
  expect(rows).toHaveLength(2);
  return rows[1];
}

async function openRunsHistory(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("tab", { name: /runs/i }));
}

async function openRunInputsPanel(user: ReturnType<typeof userEvent.setup>) {
  const row = getDataRow();
  await user.click(within(row).getByRole("button", { name: /view inputs/i }));
}

function dialog() {
  return screen.getByRole("dialog");
}

function primaryAction() {
  return screen.getByRole("button", { name: /run|rerun|submit|launch/i });
}

beforeEach(() => {
  harness.runs = [];
  harness.workflows = {};
  harness.createRunRequest.mockReset();
  harness.createRunRequest.mockResolvedValue({ id: "run_925_new" });
  harness.prepareSimulation.mockReset();
  harness.prepareSimulation.mockResolvedValue({
    branch: "sim/wf_run_925_current/20260422/abc12",
    commit_sha: "simulated-commit-sha",
    input_schema: SIMPLE_WORKFLOW.input_schema,
  });
  harness.toastError.mockReset();
  harness.navigate.mockReset();
  harness.canvasState.activeRunId = null;
  harness.canvasState.isDirty = false;
  harness.canvasState.yamlContent = "id: wf_run_925_current\nkind: workflow\nversion: '1.0'\n";
  harness.canvasState.setNodeStatus.mockReset();
  harness.canvasState.setActiveRunId.mockReset();
  harness.canvasState.setRunCost.mockReset();
  harness.contextAuditState.eventsByRun = {};
  harness.contextAuditState.replaceRunEvents.mockReset();

  class EventSourceMock {
    addEventListener() {
      return undefined;
    }

    close() {
      return undefined;
    }
  }

  vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource);
});

describe("RUN-925 rerun workflow inputs from footer history", () => {
  it("prefills the rerun modal with the selected historical query and leaves sensitive inputs empty", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = CURRENT_WORKFLOW;
    harness.runs = [
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
          legacy_query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "should-not-migrate",
          },
          api_token: {
            type: "string",
            sensitive: true,
            source: "provided",
          },
        },
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    await openRunInputsPanel(user);

    expect(within(getDataRow()).getByText(/refunds/i)).toBeTruthy();
    expect(screen.getByText(/sensitive input omitted/i)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /rerun/i }));

    expect(dialog()).toBeTruthy();
    expect(screen.getByRole("textbox", { name: /query/i })).toHaveValue("refunds");
    expect(screen.queryByDisplayValue("[__HIDDEN__]")).toBeNull();

    const sensitiveField = screen.getByLabelText(/api token/i);
    expect(sensitiveField).toHaveAttribute("type", "password");
    expect(sensitiveField).toHaveValue("");
  });

  it("does not prefill a historical snapshot value marked sensitive even if the current field is public", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = SIMPLE_WORKFLOW;
    harness.runs = [
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: true,
            source: "provided",
            value: "historical secret",
          },
        },
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    await openRunInputsPanel(user);
    await user.click(screen.getByRole("button", { name: /rerun/i }));

    expect(screen.getByRole("textbox", { name: /query/i })).toHaveValue("");
    expect(screen.queryByDisplayValue("historical secret")).toBeNull();
  });

  it("submits edited rerun inputs under the current workflow field names and does not migrate legacy keys", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = SIMPLE_WORKFLOW;
    harness.runs = [
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
          legacy_query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "legacy refund term",
          },
        },
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    await openRunInputsPanel(user);
    await user.click(screen.getByRole("button", { name: /rerun/i }));

    const queryField = screen.getByRole("textbox", { name: /query/i });
    expect(queryField).toHaveValue("refunds");

    await user.clear(queryField);
    await user.type(queryField, "edited query");

    await user.click(primaryAction());

    await waitFor(() => expect(harness.createRunRequest).toHaveBeenCalledTimes(1));
    expect(harness.createRunRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_id: CURRENT_WORKFLOW_ID,
        inputs: {
          query: "edited query",
        },
      }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps the modal open and surfaces field-level validation errors when the current workflow rejects rerun inputs", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = SIMPLE_WORKFLOW;
    harness.createRunRequest.mockRejectedValueOnce(
      new ApiError(422, "WORKFLOW_INPUT_VALIDATION_ERROR", "Workflow input validation failed", {
        kind: "workflow_input_validation",
        workflow_id: CURRENT_WORKFLOW_ID,
        fields: [
          {
            field: "query",
            code: "required",
            message: "Input 'query' is required.",
            input_path: ["inputs", "query"],
            expected_type: "string",
            actual_type: null,
          },
        ],
      }),
    );
    harness.runs = [
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
        },
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    await openRunInputsPanel(user);
    await user.click(screen.getByRole("button", { name: /rerun/i }));
    await user.click(primaryAction());

    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
    expect(screen.getByRole("textbox", { name: /query/i })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Input 'query' is required.")).toBeTruthy();
  });

  it("starts the rerun immediately without opening the modal when the historical run has no inputs", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = EMPTY_WORKFLOW;
    harness.runs = [
      makeRun({
        workflow_inputs: null,
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    expect(screen.getByText(/no inputs/i)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /rerun/i }));

    await waitFor(() => expect(harness.createRunRequest).toHaveBeenCalledTimes(1));
    expect(harness.createRunRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_id: CURRENT_WORKFLOW_ID,
        inputs: {},
      }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("routes reruns through a simulation branch when the editable surface is dirty", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = SIMPLE_WORKFLOW;
    harness.canvasState.isDirty = true;
    harness.canvasState.yamlContent = "id: wf_run_925_current\nkind: workflow\nversion: '1.0'\n# dirty draft";
    harness.runs = [
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
        },
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    await openRunInputsPanel(user);
    await user.click(screen.getByRole("button", { name: /rerun/i }));
    await user.click(primaryAction());

    await waitFor(() => expect(harness.prepareSimulation).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(harness.createRunRequest).toHaveBeenCalledTimes(1));
    expect(harness.createRunRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_id: CURRENT_WORKFLOW_ID,
        source: "simulation",
        branch: "sim/wf_run_925_current/20260422/abc12",
        inputs: {
          query: "refunds",
        },
      }),
    );
  });

  it("shows a toast when simulation preparation throws unexpectedly during rerun", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = SIMPLE_WORKFLOW;
    harness.canvasState.isDirty = true;
    harness.prepareSimulation.mockRejectedValueOnce(new Error("git exploded"));
    harness.runs = [
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
        },
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    await openRunInputsPanel(user);
    await user.click(screen.getByRole("button", { name: /rerun/i }));

    await waitFor(() => expect(harness.prepareSimulation).toHaveBeenCalledTimes(1));
    expect(harness.createRunRequest).not.toHaveBeenCalled();
    expect(harness.toastError).toHaveBeenCalledWith("Unable to start run", {
      description: "git exploded",
    });
  });

  it("skips the rerun modal when the dirty simulation snapshot no longer has inputs", async () => {
    const user = userEvent.setup();
    harness.workflows[CURRENT_WORKFLOW_ID] = CURRENT_WORKFLOW;
    harness.canvasState.isDirty = true;
    harness.prepareSimulation.mockResolvedValueOnce({
      branch: "sim/wf_run_925_current/20260422/xyz99",
      commit_sha: "simulated-no-inputs",
      input_schema: null,
    });
    harness.runs = [
      makeRun({
        workflow_inputs: {
          query: {
            type: "string",
            sensitive: false,
            source: "provided",
            value: "refunds",
          },
        },
      }),
    ];

    renderSurfaceBottomPanel();
    await openRunsHistory(user);
    await openRunInputsPanel(user);
    await user.click(screen.getByRole("button", { name: /rerun/i }));

    await waitFor(() => expect(harness.prepareSimulation).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(harness.createRunRequest).toHaveBeenCalledTimes(1));
    expect(harness.createRunRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_id: CURRENT_WORKFLOW_ID,
        source: "simulation",
        branch: "sim/wf_run_925_current/20260422/xyz99",
        inputs: {},
      }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
