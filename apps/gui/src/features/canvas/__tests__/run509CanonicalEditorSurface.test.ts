// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => {
  const canvasStoreState = {
    setActiveRunId: vi.fn(),
    blockCount: 0,
    edgeCount: 0,
    yamlContent: "workflow:\n  name: Canonical editor\n",
    toPersistedState: undefined as (() => Record<string, unknown>) | undefined,
  };

  const useCanvasStore = ((selector: (store: typeof canvasStoreState) => unknown) =>
    selector(canvasStoreState)) as {
    (selector: (store: typeof canvasStoreState) => unknown): unknown;
    getState: () => typeof canvasStoreState;
  };

  useCanvasStore.getState = () => canvasStoreState;

  return {
    canvasStoreState,
    useCanvasStore,
    queryClient: {
      invalidateQueries: vi.fn(),
    },
    updateWorkflowMutate: vi.fn(),
    createRunMutate: vi.fn(),
  };
});

vi.mock("react-router", () => ({
  useParams: () => ({ id: "wf_research" }),
  useBlocker: () => ({ state: "unblocked", proceed: vi.fn(), reset: vi.fn() }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mocks.queryClient,
}));

vi.mock("../CanvasTopbar", () => ({
  CanvasTopbar: ({
    activeTab,
    onValueChange,
  }: {
    activeTab: string;
    onValueChange: (value: string) => void;
  }) =>
    React.createElement(
      "div",
      null,
      React.createElement("div", null, `active-tab:${activeTab}`),
      React.createElement(
        "button",
        {
          type: "button",
          onClick: () => onValueChange("canvas"),
        },
        "Canvas",
      ),
      React.createElement(
        "button",
        {
          type: "button",
          onClick: () => onValueChange("yaml"),
        },
        "YAML",
      ),
    ),
}));

vi.mock("../WorkflowCanvas", () => ({
  WorkflowCanvas: () => React.createElement("div", null, "workflow-canvas-surface"),
}));

vi.mock("../YamlEditor", () => ({
  YamlEditor: () => React.createElement("div", null, "yaml-editor-surface"),
}));

vi.mock("../UncommittedBanner", () => ({
  UncommittedBanner: () => null,
}));

vi.mock("../CanvasStatusBar", () => ({
  CanvasStatusBar: () => null,
}));

vi.mock("../CanvasBottomPanel", () => ({
  CanvasBottomPanel: () => null,
}));

vi.mock("../FirstTimeTooltip", () => ({
  FirstTimeTooltip: () => null,
}));

vi.mock("../PaletteSidebar", () => ({
  PaletteSidebar: () => React.createElement("aside", null, "palette-sidebar"),
}));

vi.mock("../ExploreBanner", () => ({
  ExploreBanner: () => null,
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => null,
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: () => null,
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  DialogContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogTitle: ({ children }: { children: React.ReactNode }) =>
    React.createElement("h2", null, children),
  DialogFooter: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) =>
    React.createElement(
      "button",
      {
        type: "button",
        onClick,
      },
      children,
    ),
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: ({
    title,
    description,
    action,
  }: {
    title: string;
    description?: string;
    action?: { label: string; onClick: () => void };
  }) =>
    React.createElement(
      "div",
      null,
      React.createElement("h1", null, title),
      description ? React.createElement("p", null, description) : null,
      action
        ? React.createElement(
            "button",
            { type: "button", onClick: action.onClick },
            action.label,
          )
        : null,
    ),
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    createSimBranch: vi.fn(),
  },
}));

vi.mock("@/queries/workflows", () => ({
  useUpdateWorkflow: () => ({
    mutate: mocks.updateWorkflowMutate,
  }),
}));

vi.mock("@/queries/runs", () => ({
  useCreateRun: () => ({
    mutate: mocks.createRunMutate,
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
}));

vi.mock("lucide-react", () => ({
  Layout: () => React.createElement("span", null, "layout"),
}));

async function renderCanvasPage() {
  const { Component: CanvasPage } = await import("../CanvasPage");
  const user = userEvent.setup();

  render(React.createElement(CanvasPage));

  return { user };
}

beforeEach(() => {
  mocks.queryClient.invalidateQueries.mockReset();
  mocks.updateWorkflowMutate.mockReset();
  mocks.createRunMutate.mockReset();
  mocks.canvasStoreState.setActiveRunId.mockReset();
  mocks.canvasStoreState.toPersistedState = undefined;
});

afterEach(() => {
  cleanup();
});

describe("RUN-509 canonical editor surface", () => {
  it("renders the live workflow canvas instead of the shipped placeholder when the canvas surface is opened", async () => {
    const { user } = await renderCanvasPage();

    await user.click(screen.getByRole("button", { name: "Canvas" }));

    expect(screen.getByText("workflow-canvas-surface")).toBeTruthy();
    expect(screen.queryByText("Visual canvas coming soon")).toBeNull();
  });

  it("still reaches the live editor surface when the workflow has no persisted canvas layout yet", async () => {
    mocks.canvasStoreState.toPersistedState = undefined;

    const { user } = await renderCanvasPage();

    await user.click(screen.getByRole("button", { name: "Canvas" }));

    expect(screen.getByText("workflow-canvas-surface")).toBeTruthy();
    expect(screen.queryByText("Visual canvas coming soon")).toBeNull();
  });
});
