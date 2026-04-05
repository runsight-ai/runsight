// @vitest-environment jsdom

import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  cancelRun: vi.fn(),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: {
      id: "wf_1",
      name: "Research Pipeline",
      yaml: "workflow:\n  name: Research Pipeline\n",
      commit_sha: "abc123",
    },
  }),
  useUpdateWorkflow: () => ({
    mutate: vi.fn(),
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

vi.mock("../../runs/useForkWorkflow", () => ({
  useForkWorkflow: () => ({
    forkWorkflow: vi.fn(),
    isForking: false,
  }),
}));

import { CanvasTopbar } from "../CanvasTopbar";

beforeEach(() => {
  mocks.cancelRun.mockReset();
});

describe("CanvasTopbar run controls", () => {
  it("cancels a live simulation run when the topbar cancel action is clicked", async () => {
    const user = userEvent.setup();

    render(
      <CanvasTopbar
        workflowId="wf_1"
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
