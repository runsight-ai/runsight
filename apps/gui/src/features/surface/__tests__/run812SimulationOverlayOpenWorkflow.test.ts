// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

const mocks = vi.hoisted(() => {
  const store = {
    nodes: [] as unknown[],
    edges: [] as unknown[],
    blockCount: 0,
    edgeCount: 0,
    yamlContent: "",
    toPersistedState: vi.fn(() => ({
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    })),
    setYamlContent: vi.fn(),
    hydrateFromPersisted: vi.fn(),
    setActiveRunId: vi.fn(),
  };

  const useCanvasStore = ((selector: (state: typeof store) => unknown) =>
    selector(store)) as {
    (selector: (state: typeof store) => unknown): unknown;
    getState: () => typeof store;
  };
  useCanvasStore.getState = () => store;

  return {
    getGitFile: vi.fn(),
    yamlEditorProps: [] as Array<Record<string, unknown>>,
    store,
    useCanvasStore,
  };
});

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useQuery: () => ({ data: undefined, isLoading: false, isError: false }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: {
      id: "wf_test",
      name: "Test Flow",
      yaml: "workflow:\n  name: Live Flow\n",
      canvas_state: null,
      commit_sha: "live_sha",
    },
    isError: false,
  }),
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    getGitFile: mocks.getGitFile,
  },
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
}));

vi.mock("../SurfaceTopbar", () => ({
  SurfaceTopbar: () => React.createElement("div", null, "topbar"),
}));

vi.mock("../SurfaceYamlEditor", () => ({
  SurfaceYamlEditor: (props: Record<string, unknown>) => {
    mocks.yamlEditorProps.push(props);
    return React.createElement("div", null, "yaml-editor");
  },
}));

vi.mock("../SurfaceBottomPanel", () => ({
  SurfaceBottomPanel: () => React.createElement("div", null, "bottom-panel"),
}));

vi.mock("../SurfaceStatusBar", () => ({
  SurfaceStatusBar: () => React.createElement("div", null, "status-bar"),
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => React.createElement("div", null, "provider-modal"),
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: () => React.createElement("div", null, "commit-dialog"),
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: () => React.createElement("div", null, "empty-state"),
}));

vi.mock("lucide-react", () => ({
  LayoutGrid: () => React.createElement("div", null, "layout-grid"),
}));

import { WorkflowSurface } from "../WorkflowSurface";

describe("WorkflowSurface simulation overlay recovery", () => {
  beforeEach(() => {
    mocks.getGitFile.mockReset();
    mocks.getGitFile.mockResolvedValue({
      content: "workflow:\n  name: Snapshot Flow\n",
    });
    mocks.yamlEditorProps.length = 0;
    mocks.store.toPersistedState.mockClear();
    mocks.store.setYamlContent.mockReset();
    mocks.store.hydrateFromPersisted.mockReset();
    window.history.pushState({}, "", "/workflows/wf_test/edit?overlayRef=sim_sha&overlaySource=simulation");
  });

  afterEach(() => {
    cleanup();
    window.history.pushState({}, "", "/");
  });

  it("loads workflow YAML from the simulation snapshot into the existing editor route", async () => {
    render(
      React.createElement(
        MemoryRouter,
        undefined,
        React.createElement(WorkflowSurface, { mode: "edit", workflowId: "wf_test" }),
      ),
    );

    await waitFor(() => {
      expect(mocks.getGitFile).toHaveBeenCalledWith("sim_sha", "custom/workflows/wf_test.yaml");
    });

    await waitFor(() => {
      expect(mocks.yamlEditorProps.at(-1)?.yaml).toBe("workflow:\n  name: Snapshot Flow\n");
    });
  });
});
