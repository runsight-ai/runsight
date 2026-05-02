// @vitest-environment jsdom

import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  cancelRun: vi.fn(),
  updateWorkflow: vi.fn(),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: {
      id: "research_pipeline",
      name: "Research Pipeline",
      yaml: "workflow:\n  name: Research Pipeline\n",
      commit_sha: "abc123",
    },
  }),
  useUpdateWorkflow: () => ({
    mutate: mocks.updateWorkflow,
  }),
}));

vi.mock("@/queries/runs", () => ({
  useCancelRun: () => ({
    mutate: mocks.cancelRun,
    isPending: false,
  }),
  useRun: (id: string) => ({
    data: id === "run_live" ? { id, status: "running" } : undefined,
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      activeRunId: null,
      nodes: [],
      blockCount: 0,
      isDirty: false,
      yamlContent: "workflow:\n  name: Research Pipeline\n",
      setActiveRunId: vi.fn(),
    }),
}));

vi.mock("../RunButton", () => ({
  RunButton: () => React.createElement("button", { type: "button" }, "Run"),
}));

vi.mock("../ExecutionMetrics", () => ({
  ExecutionMetrics: () => React.createElement("div", null, "metrics"),
}));

vi.mock("../useForkWorkflow", () => ({
  useForkWorkflow: () => ({
    forkWorkflow: vi.fn(),
    isForking: false,
  }),
}));

import { SurfaceTopbar } from "../SurfaceTopbar";

beforeEach(() => {
  mocks.cancelRun.mockReset();
  mocks.updateWorkflow.mockReset();
});

describe("SurfaceTopbar run controls", () => {
  it("saves inline name edits without triggering the explicit save action", async () => {
    const onSave = vi.fn();

    render(
      <SurfaceTopbar
        workflowId="research_pipeline"
        activeTab="canvas"
        onValueChange={() => undefined}
        isDirty
        onSave={onSave}
      />,
    );

    fireEvent.click(screen.getByTestId("workflow-name-display"));
    fireEvent.change(screen.getByTestId("workflow-name-input"), {
      target: { value: "Renamed Workflow" },
    });
    fireEvent.blur(screen.getByTestId("workflow-name-input"));

    await waitFor(() => {
      expect(mocks.updateWorkflow).toHaveBeenCalledWith({
        id: "research_pipeline",
        data: {
          name: "Renamed Workflow",
          yaml: "workflow:\n  name: Research Pipeline\n",
        },
      });
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  it("cancels a live simulation run when the topbar cancel action is clicked", async () => {
    const user = userEvent.setup();

    render(
      <SurfaceTopbar
        workflowId="research_pipeline"
        runId="run_live"
        activeTab="canvas"
        onValueChange={() => undefined}
        nameEditable={false}
        saveButton="hidden"
        actionButton={{ label: "Cancel", variant: "danger" }}
        toggleVisibility={{ canvas: true, yaml: true }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(mocks.cancelRun).toHaveBeenCalledWith("run_live");
  });
});
