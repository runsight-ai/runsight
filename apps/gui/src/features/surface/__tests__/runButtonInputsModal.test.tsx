// @vitest-environment jsdom

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

type WorkflowInputSchemaItem = {
  type: "string" | "number" | "boolean" | "json" | "array";
  required?: boolean | null;
  default?: unknown;
  description?: string | null;
  sensitive?: boolean | null;
};

const submittedInputs = {
  query: "alpha query",
  config: { mode: "fast", retries: 2 },
};

const inputSchema = {
  query: {
    type: "string",
    required: true,
    default: null,
    description: "Search query",
    sensitive: false,
  },
  config: {
    type: "json",
    required: false,
    default: { mode: "fast", retries: 2 },
    description: "Structured run configuration",
    sensitive: false,
  },
} satisfies Record<string, WorkflowInputSchemaItem>;

const validationError = Object.assign(new Error("Workflow input validation failed"), {
  status: 422,
  code: "WORKFLOW_INPUT_VALIDATION_ERROR",
  details: {
    kind: "workflow_input_validation",
    workflow_id: "wf-committed-inputs",
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
  },
});

const harness = vi.hoisted(() => {
  const state = {
    activeRunId: null as string | null,
    setActiveRunId: vi.fn((value: string | null) => {
      state.activeRunId = value;
    }),
    nodes: [
      {
        id: "node-1",
        type: "soul",
        position: { x: 10, y: 20 },
        data: { label: "Draft node" },
      },
    ],
    blockCount: 1,
    isDirty: false,
    yamlContent: "workflow:\n  name: Input Modal Flow\n",
  };

  const useCanvasStore = ((selector: (store: typeof state) => unknown) =>
    selector(state)) as {
    (selector: (store: typeof state) => unknown): unknown;
    getState: () => typeof state;
  };
  useCanvasStore.getState = () => state;

  return {
    state,
    useCanvasStore,
    navigate: vi.fn(),
    createRunMutate: vi.fn(),
    createRunMutateAsync: vi.fn(),
    cancelRunMutate: vi.fn(),
    createSimBranch: vi.fn(),
    modalProps: [] as Array<Record<string, unknown>>,
    workflowById: {} as Record<string, { id: string; input_schema: unknown }>,
    submitMode: "success" as "success" | "validation-error",
    inModalSubmit: false,
    nextRunId: "run-inputs-success",
  };
});

harness.createRunMutate.mockImplementation((variables, options) => {
  if (harness.submitMode === "validation-error" && harness.inModalSubmit) {
    throw validationError;
  }

  const result = { id: harness.nextRunId };
  options?.onSuccess?.(result, variables, undefined as never);
  return result;
});

harness.createRunMutateAsync.mockImplementation(async () => {
  if (harness.submitMode === "validation-error" && harness.inModalSubmit) {
    throw validationError;
  }

  return { id: harness.nextRunId };
});

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    loading: _loading,
    ...props
  }: {
    children?: React.ReactNode;
    [key: string]: unknown;
  }) =>
    React.createElement(
      "button",
      { type: "button", ...props },
      children,
    ),
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
  Key: () => React.createElement("span", { "aria-hidden": "true" }),
  Play: () => React.createElement("span", { "aria-hidden": "true" }),
  X: () => React.createElement("span", { "aria-hidden": "true" }),
}));

vi.mock("@/queries/runs", () => ({
  useCreateRun: () => ({
    mutate: harness.createRunMutate,
    mutateAsync: harness.createRunMutateAsync,
    isPending: false,
  }),
  useCancelRun: () => ({
    mutate: harness.cancelRunMutate,
    isPending: false,
  }),
  useRun: () => ({ data: undefined }),
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => ({
    data: { items: [{ id: "active-provider", is_active: true }] },
  }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: (workflowId: string) => ({
    data: harness.workflowById[workflowId] ?? null,
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: harness.useCanvasStore,
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    createSimBranch: harness.createSimBranch,
  },
}));

vi.mock("react-router", () => ({
  useNavigate: () => harness.navigate,
}));

vi.mock("../RunInputsModal", () => ({
  RunInputsModal: (props: Record<string, unknown>) => {
    harness.modalProps.push(props);

    if (!props.open) {
      return null;
    }

    return React.createElement(
      "div",
      { role: "dialog", "aria-label": "Run inputs" },
      React.createElement(
        "button",
        {
          type: "button",
          onClick: async () => {
            try {
              harness.inModalSubmit = true;
              await props.onSubmit?.(submittedInputs);
              props.onOpenChange?.(false);
            } catch {
              // Keep the modal open on submit failure.
            } finally {
              harness.inModalSubmit = false;
            }
          },
        },
        "Confirm run",
      ),
      React.createElement(
        "button",
        {
          type: "button",
          onClick: () => props.onOpenChange?.(false),
        },
        "Cancel",
      ),
      React.createElement(
        "span",
        { "data-testid": "run-inputs-workflow-id" },
        String((props.workflow as { id?: string } | undefined)?.id ?? ""),
      ),
    );
  },
}));

const { RunButton } = await import("../RunButton");

function renderRunButton({
  workflowId = "wf-committed-clean",
  isCommitted = true,
}: {
  workflowId?: string;
  isCommitted?: boolean;
} = {}) {
  render(
    React.createElement(RunButton, {
      workflowId,
      isCommitted,
    }),
  );
}

function lastModalProps() {
  const props = harness.modalProps.at(-1);
  expect(props).toBeTruthy();
  return props as Record<string, unknown>;
}

beforeEach(() => {
  harness.state.activeRunId = null;
  harness.state.setActiveRunId.mockClear();
  harness.state.nodes = [
    {
      id: "node-1",
        type: "soul",
      position: { x: 10, y: 20 },
      data: { label: "Draft node" },
    },
  ];
  harness.state.blockCount = 1;
  harness.state.isDirty = false;
  harness.state.yamlContent = "workflow:\n  name: Input Modal Flow\n";
  harness.navigate.mockReset();
  harness.createRunMutate.mockClear();
  harness.createRunMutateAsync.mockClear();
  harness.cancelRunMutate.mockClear();
  harness.createSimBranch.mockClear();
  harness.modalProps.length = 0;
  harness.workflowById = {};
  harness.submitMode = "success";
  harness.inModalSubmit = false;
  harness.nextRunId = "run-inputs-success";
});

describe("RunButton input modal wiring", () => {
  it("runs immediately when the resolved workflow has no inputs", async () => {
    harness.workflowById.wf_committed_clean = {
      id: "wf_committed_clean",
      input_schema: null,
    };

    renderRunButton({ workflowId: "wf_committed_clean", isCommitted: true });
    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => {
      expect(harness.createRunMutate).toHaveBeenCalledWith(
        {
          workflow_id: "wf_committed_clean",
          inputs: {},
          source: "manual",
          branch: "main",
        },
        expect.objectContaining({ onSuccess: expect.any(Function) }),
      );
    });
    expect(screen.queryByRole("dialog", { name: /run inputs/i })).toBeNull();
    expect(harness.navigate).toHaveBeenCalledWith("/runs/run-inputs-success");
    expect(harness.state.setActiveRunId).toHaveBeenCalledWith("run-inputs-success");
  });

  it("opens the run inputs modal and waits for submit when the workflow has inputs", async () => {
    harness.workflowById.wf_committed_inputs = {
      id: "wf_committed_inputs",
      input_schema: inputSchema,
    };

    renderRunButton({ workflowId: "wf_committed_inputs", isCommitted: true });
    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    expect(lastModalProps()).toEqual(
      expect.objectContaining({
        open: true,
        workflow: expect.objectContaining({
          id: "wf_committed_inputs",
          input_schema: inputSchema,
        }),
      }),
    );
    expect(harness.createRunMutate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /confirm run/i }));

    await waitFor(() => {
      expect(harness.createRunMutate).toHaveBeenCalledWith(
        {
          workflow_id: "wf_committed_inputs",
          inputs: submittedInputs,
          source: "manual",
          branch: "main",
        },
        expect.objectContaining({ onSuccess: expect.any(Function) }),
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /run inputs/i })).toBeNull();
    });
    expect(harness.navigate).toHaveBeenCalledWith("/runs/run-inputs-success");
  });

  it("prepares a simulation branch before opening the inputs modal for dirty uncommitted workflows", async () => {
    const preparedBranch = "sim/wf_dirty_inputs/20260420/dirty-ab12";
    const preparedCommitSha = "feedfacefeedfacefeedfacefeedfacefeedface";

    harness.state.isDirty = true;
    harness.workflowById.wf_dirty_inputs = {
      id: "wf_dirty_inputs",
      input_schema: null,
    };
    harness.createSimBranch.mockResolvedValue({
      branch: preparedBranch,
      commit_sha: preparedCommitSha,
      input_schema: inputSchema,
    });

    renderRunButton({ workflowId: "wf_dirty_inputs", isCommitted: false });
    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => {
      expect(harness.createSimBranch).toHaveBeenCalledWith(
        "wf_dirty_inputs",
        "workflow:\n  name: Input Modal Flow\n",
      );
      expect(lastModalProps()).toEqual(
        expect.objectContaining({
          open: true,
          workflow: expect.objectContaining({
            id: "wf_dirty_inputs",
            input_schema: inputSchema,
            branch: preparedBranch,
            commit_sha: preparedCommitSha,
          }),
        }),
      );
    });
    expect(harness.createRunMutate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /confirm run/i }));

    await waitFor(() => {
      expect(harness.createRunMutate).toHaveBeenCalledWith(
        {
          workflow_id: "wf_dirty_inputs",
          inputs: submittedInputs,
          source: "simulation",
          branch: preparedBranch,
        },
        expect.objectContaining({ onSuccess: expect.any(Function) }),
      );
    });
    expect(harness.createSimBranch.mock.invocationCallOrder[0]).toBeLessThan(
      harness.createRunMutate.mock.invocationCallOrder[0],
    );
    expect(harness.navigate).toHaveBeenCalledWith("/runs/run-inputs-success");
    expect(screen.queryByRole("dialog", { name: /run inputs/i })).toBeNull();
  });

  it("keeps the modal open when createRun rejects workflow input validation", async () => {
    harness.submitMode = "validation-error";
    harness.workflowById.wf_committed_inputs = {
      id: "wf_committed_inputs",
      input_schema: inputSchema,
    };

    renderRunButton({ workflowId: "wf_committed_inputs", isCommitted: true });
    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    expect(lastModalProps()).toEqual(
      expect.objectContaining({
        open: true,
        workflow: expect.objectContaining({
          input_schema: inputSchema,
        }),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /confirm run/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /run inputs/i })).not.toBeNull();
    });
    expect(harness.navigate).not.toHaveBeenCalled();
    expect(harness.state.setActiveRunId).not.toHaveBeenCalled();
  });

  it("closes the modal without creating a run when cancel is clicked", async () => {
    harness.workflowById.wf_committed_inputs = {
      id: "wf_committed_inputs",
      input_schema: inputSchema,
    };

    renderRunButton({ workflowId: "wf_committed_inputs", isCommitted: true });
    fireEvent.click(screen.getByRole("button", { name: /run/i }));

    expect(lastModalProps()).toEqual(
      expect.objectContaining({
        open: true,
        workflow: expect.objectContaining({
          input_schema: inputSchema,
        }),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /run inputs/i })).toBeNull();
    });
    expect(harness.createRunMutate).not.toHaveBeenCalled();
    expect(harness.navigate).not.toHaveBeenCalled();
  });
});
