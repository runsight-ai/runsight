// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

type RunRecord = {
  id: string;
  status: "running" | "completed" | "failed" | "cancelled";
};

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
    workflow: { id: "runnable_workflow", name: "Runnable", input_schema: null, commit_sha: "main_commit_sha" },
    activeRun: undefined as RunRecord | undefined,
    createRunMutate: vi.fn(),
    cancelRunMutate: vi.fn(),
    navigate: vi.fn(),
  };
});

harness.createRunMutate.mockImplementation((variables, options) => {
  options?.onSuccess?.({ id: "created_manual_run" }, variables, undefined);
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
    createSimBranch: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn() },
}));

vi.mock("react-router", () => ({
  useNavigate: () => harness.navigate,
}));

vi.mock("../RunInputsModal", () => ({
  RunInputsModal: () => null,
}));

import { RunButton } from "../RunButton";

function renderRunButton(onAddApiKey = vi.fn()) {
  render(<RunButton workflowId="runnable_workflow" isCommitted onAddApiKey={onAddApiKey} />);
  return { onAddApiKey };
}

beforeEach(() => {
  harness.canvasState.activeRunId = null;
  harness.canvasState.nodes = [{ id: "runnable_node" }];
  harness.canvasState.blockCount = 1;
  harness.canvasState.isDirty = false;
  harness.canvasState.yamlContent = "workflow:\n  name: Runnable\n";
  harness.providers = [{ id: "active_provider", is_active: true }];
  harness.activeRun = undefined;
  harness.createRunMutate.mockClear();
  harness.cancelRunMutate.mockClear();
  harness.canvasState.setActiveRunId.mockClear();
  harness.navigate.mockReset();
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
