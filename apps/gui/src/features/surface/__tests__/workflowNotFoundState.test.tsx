// @vitest-environment jsdom

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

const harness = vi.hoisted(() => {
  const canvasState = {
    nodes: [],
    blockCount: 0,
    edgeCount: 0,
    yamlContent: "",
    setYamlContent: vi.fn(),
    hydrateFromPersisted: vi.fn(),
    setNodeStatus: vi.fn(),
    setActiveRunId: vi.fn(),
    setRunCost: vi.fn(),
    selectNode: vi.fn(),
    toPersistedState: vi.fn(() => ({ nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } })),
  };

  return {
    canvasState,
    queryClient: { invalidateQueries: vi.fn() },
  };
});

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => harness.queryClient,
}));

vi.mock("@/queries/runs", () => ({
  useRun: () => ({ data: undefined, isLoading: false, isError: false }),
  useRunNodes: () => ({ data: [], isError: false, error: null, refetch: vi.fn() }),
  useRunRegressions: () => ({ data: { count: 0, issues: [] } }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({ data: undefined, isError: true, isLoading: false }),
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

vi.mock("../SurfaceTopbar", () => ({
  SurfaceTopbar: () => null,
}));

vi.mock("../SurfaceShell", () => ({
  SurfaceShell: ({ center }: { center: React.ReactNode }) => <>{center}</>,
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => null,
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: () => null,
}));

import { WorkflowSurface } from "../WorkflowSurface";

afterEach(() => {
  cleanup();
});

describe("WorkflowSurface not-found state", () => {
  it("shows a workflow not-found message with a back link", () => {
    render(
      <MemoryRouter>
        <WorkflowSurface mode="edit" workflowId="missing_workflow" />
      </MemoryRouter>,
    );

    expect(screen.getByText("Workflow not found")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to workflows" }).getAttribute("href")).toBe(
      "/flows",
    );
  });
});
