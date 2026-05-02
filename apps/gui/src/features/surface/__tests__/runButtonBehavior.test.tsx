// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

type RunRecord = {
  id: string;
  status: "running" | "completed" | "failed" | "cancelled";
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
} as const;

const validationError = Object.assign(new Error("Workflow input validation failed"), {
  status: 422,
  code: "WORKFLOW_INPUT_VALIDATION_ERROR",
});

const harness = vi.hoisted(() => {
  const canvasState = {
    activeRunId: null as string | null,
    setActiveRunId: vi.fn((value: string | null) => {
      canvasState.activeRunId = value;
    }),
    nodes: [{ id: "runnable_node" }] as Array<Record<string, unknown>>,
    blockCount: 1,
    isDirty: false,
    yamlContent: "workflow:\n  name: Runnable\n",
  };

  return {
    canvasState,
    providers: [{ id: "active_provider", is_active: true }] as Array<Record<string, unknown>>,
    workflow: {
      id: "runnable_workflow",
      name: "Runnable",
      input_schema: null,
      commit_sha: "main_commit_sha",
    } as {
      id: string;
      name: string;
      input_schema: unknown;
      commit_sha: string;
    },
    activeRun: undefined as RunRecord | undefined,
    createRunMutate: vi.fn(),
    cancelRunMutate: vi.fn(),
    createSimBranch: vi.fn(),
    toastError: vi.fn(),
    modalProps: [] as Array<Record<string, unknown>>,
    navigate: vi.fn(),
    submitMode: "success" as "success" | "validation-error",
    nextRunId: "created_manual_run",
  };
});

harness.createRunMutate.mockImplementation((variables, options) => {
  if (harness.submitMode === "validation-error") {
    options?.onError?.(validationError, variables, undefined);
    return;
  }

  options?.onSuccess?.({ id: harness.nextRunId }, variables, undefined);
});

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    loading: _loading,
    ...props
  }: {
    children?: React.ReactNode;
    loading?: boolean;
    [key: string]: unknown;
  }) => <button type="button" {...props}>{children}</button>,
}));

vi.mock("@runsight/ui/tooltip", () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ render }: { render: React.ReactNode }) => <>{render}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock("lucide-react", () => ({
  Key: () => <span aria-hidden="true" />,
  Play: () => <span aria-hidden="true" />,
  X: () => <span aria-hidden="true" />,
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => ({
    data: { items: harness.providers, total: harness.providers.length },
  }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({ data: harness.workflow }),
}));

vi.mock("@/queries/runs", () => ({
  useCreateRun: () => ({
    mutate: harness.createRunMutate,
    isPending: false,
  }),
  useCancelRun: () => ({
    mutate: harness.cancelRunMutate,
    isPending: false,
  }),
  useRun: () => ({
    data: harness.activeRun,
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

vi.mock("@/api/git", () => ({
  gitApi: {
    createSimBranch: harness.createSimBranch,
  },
}));

vi.mock("sonner", () => ({
  toast: { error: harness.toastError },
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

    return (
      <div role="dialog" aria-label="Run inputs">
        <button
          type="button"
          onClick={async () => {
            try {
              await (props.onSubmit as (inputs: Record<string, unknown>) => Promise<void>)(
                submittedInputs,
              );
              (props.onOpenChange as (open: boolean) => void)(false);
            } catch {
              // Keep the dialog open so validation errors remain visible.
            }
          }}
        >
          Confirm run
        </button>
        <button
          type="button"
          onClick={() => (props.onOpenChange as (open: boolean) => void)(false)}
        >
          Cancel
        </button>
      </div>
    );
  },
}));

import { RunButton } from "../RunButton";

function renderRunButton(
  onAddApiKey = vi.fn(),
  props: Partial<React.ComponentProps<typeof RunButton>> = {},
) {
  render(
    <RunButton
      workflowId="runnable_workflow"
      isCommitted
      onAddApiKey={onAddApiKey}
      {...props}
    />,
  );
  return { onAddApiKey };
}

beforeEach(() => {
  harness.canvasState.activeRunId = null;
  harness.canvasState.nodes = [{ id: "runnable_node" }];
  harness.canvasState.blockCount = 1;
  harness.canvasState.isDirty = false;
  harness.canvasState.yamlContent = "workflow:\n  name: Runnable\n";
  harness.providers = [{ id: "active_provider", is_active: true }];
  harness.workflow = {
    id: "runnable_workflow",
    name: "Runnable",
    input_schema: null,
    commit_sha: "main_commit_sha",
  };
  harness.activeRun = undefined;
  harness.createRunMutate.mockClear();
  harness.cancelRunMutate.mockClear();
  harness.createSimBranch.mockReset();
  harness.createSimBranch.mockResolvedValue({
    branch: "sim/runnable-workflow/20260420/abc12",
    commit_sha: "simulation_commit_sha",
  });
  harness.toastError.mockReset();
  harness.modalProps.length = 0;
  harness.canvasState.setActiveRunId.mockClear();
  harness.navigate.mockReset();
  harness.submitMode = "success";
  harness.nextRunId = "created_manual_run";
});

afterEach(() => {
  cleanup();
});

describe("RunButton provider gating", () => {
  it("shows Add API Key and calls the add-key callback when no active providers exist", () => {
    harness.providers = [];
    const { onAddApiKey } = renderRunButton();

    fireEvent.click(screen.getByRole("button", { name: /add api key/i }));

    expect(onAddApiKey).toHaveBeenCalledTimes(1);
    expect(harness.createRunMutate).not.toHaveBeenCalled();
  });

  it("shows Run when providers exist", () => {
    renderRunButton();

    expect(screen.getByRole("button", { name: /^run$/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /add api key/i })).toBeNull();
  });
});

describe("RunButton run and cancel behavior", () => {
  it("creates a manual run with empty inputs for a committed workflow", async () => {
    renderRunButton();

    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    await waitFor(() => {
      expect(harness.createRunMutate).toHaveBeenCalledWith(
        {
          workflow_id: "runnable_workflow",
          inputs: {},
          source: "manual",
          branch: "main",
        },
        expect.objectContaining({ onSuccess: expect.any(Function) }),
      );
    });
    expect(harness.canvasState.setActiveRunId).toHaveBeenCalledWith("created_manual_run");
    expect(harness.navigate).toHaveBeenCalledWith("/runs/created_manual_run");
  });

  it("creates a simulation branch before running a dirty committed workflow", async () => {
    harness.canvasState.isDirty = true;
    harness.canvasState.yamlContent = "workflow:\n  name: Dirty Runnable\n";

    renderRunButton();
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    await waitFor(() => {
      expect(harness.createSimBranch).toHaveBeenCalledWith(
        "runnable_workflow",
        "workflow:\n  name: Dirty Runnable\n",
      );
      expect(harness.createRunMutate).toHaveBeenCalledWith(
        {
          workflow_id: "runnable_workflow",
          inputs: {},
          source: "simulation",
          branch: "sim/runnable-workflow/20260420/abc12",
        },
        expect.objectContaining({ onSuccess: expect.any(Function) }),
      );
    });
    expect(harness.createSimBranch.mock.invocationCallOrder[0]).toBeLessThan(
      harness.createRunMutate.mock.invocationCallOrder[0],
    );
  });

  it("creates a simulation branch before running an uncommitted workflow", async () => {
    renderRunButton(vi.fn(), { isCommitted: false });
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    await waitFor(() => {
      expect(harness.createSimBranch).toHaveBeenCalledWith(
        "runnable_workflow",
        "workflow:\n  name: Runnable\n",
      );
      expect(harness.createRunMutate.mock.calls[0]?.[0]).toEqual(
        expect.objectContaining({
          source: "simulation",
          branch: "sim/runnable-workflow/20260420/abc12",
        }),
      );
    });
  });

  it("opens the run inputs dialog and waits for submitted inputs", async () => {
    harness.workflow = {
      id: "runnable_workflow",
      name: "Runnable",
      input_schema: inputSchema,
      commit_sha: "main_commit_sha",
    };

    renderRunButton();
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    expect(screen.getByRole("dialog", { name: /run inputs/i })).toBeTruthy();
    expect(harness.createRunMutate).not.toHaveBeenCalled();
    expect(harness.modalProps.at(-1)).toEqual(
      expect.objectContaining({
        open: true,
        workflow: expect.objectContaining({
          id: "runnable_workflow",
          input_schema: inputSchema,
        }),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /confirm run/i }));

    await waitFor(() => {
      expect(harness.createRunMutate).toHaveBeenCalledWith(
        {
          workflow_id: "runnable_workflow",
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
  });

  it("keeps the run inputs dialog open when submitted inputs fail validation", async () => {
    harness.submitMode = "validation-error";
    harness.workflow = {
      id: "runnable_workflow",
      name: "Runnable",
      input_schema: inputSchema,
      commit_sha: "main_commit_sha",
    };

    renderRunButton();
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm run/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /run inputs/i })).not.toBeNull();
    });
    expect(harness.navigate).not.toHaveBeenCalled();
    expect(harness.canvasState.setActiveRunId).not.toHaveBeenCalled();
  });

  it("prepares simulation input schema before opening the inputs dialog", async () => {
    harness.canvasState.isDirty = true;
    harness.workflow = {
      id: "runnable_workflow",
      name: "Runnable",
      input_schema: null,
      commit_sha: "main_commit_sha",
    };
    harness.createSimBranch.mockResolvedValue({
      branch: "sim/runnable-workflow/20260420/with-inputs",
      commit_sha: "simulation_commit_with_inputs",
      input_schema: inputSchema,
    });

    renderRunButton();
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: /run inputs/i })).toBeTruthy();
    });
    expect(harness.createRunMutate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /confirm run/i }));

    await waitFor(() => {
      expect(harness.createRunMutate).toHaveBeenCalledWith(
        {
          workflow_id: "runnable_workflow",
          inputs: submittedInputs,
          source: "simulation",
          branch: "sim/runnable-workflow/20260420/with-inputs",
        },
        expect.objectContaining({ onSuccess: expect.any(Function) }),
      );
    });
  });

  it("blocks the run and shows an error when simulation preparation fails", async () => {
    harness.canvasState.isDirty = true;
    harness.createSimBranch.mockRejectedValue(new Error("Simulation snapshot failed"));

    renderRunButton();
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    await waitFor(() => {
      expect(harness.createRunMutate).not.toHaveBeenCalled();
      expect(harness.toastError).toHaveBeenCalledWith("Unable to start run", {
        description: "Simulation snapshot failed",
      });
    });
  });

  it("uses YAML content as runnable workflow content even when the canvas has no nodes", () => {
    harness.canvasState.nodes = [];
    harness.canvasState.blockCount = 0;
    harness.canvasState.yamlContent = "workflow:\n  name: Yaml Only\nblocks:\n  start:\n    type: linear\n";

    renderRunButton();

    expect(screen.getByRole<HTMLButtonElement>("button", { name: /^run$/i }).disabled).toBe(false);
  });

  it("disables run and shows the empty-workflow hint when there is no canvas or YAML content", () => {
    harness.canvasState.nodes = [];
    harness.canvasState.blockCount = 0;
    harness.canvasState.yamlContent = "";

    renderRunButton();

    expect(screen.getByRole<HTMLButtonElement>("button", { name: /^run$/i }).disabled).toBe(true);
    expect(screen.getByText("Add at least one block")).toBeTruthy();
  });

  it("cancels the active running run", () => {
    harness.canvasState.activeRunId = "run_active";
    harness.activeRun = { id: "run_active", status: "running" };

    renderRunButton();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(harness.cancelRunMutate).toHaveBeenCalledWith("run_active");
    expect(harness.createRunMutate).not.toHaveBeenCalled();
  });

  it("clears the active run after a terminal status", async () => {
    harness.canvasState.activeRunId = "run_done";
    harness.activeRun = { id: "run_done", status: "completed" };

    renderRunButton();

    await waitFor(() => {
      expect(harness.canvasState.setActiveRunId).toHaveBeenCalledWith(null);
    });
    expect(screen.getByRole("button", { name: /^run$/i })).toBeTruthy();
  });
});
