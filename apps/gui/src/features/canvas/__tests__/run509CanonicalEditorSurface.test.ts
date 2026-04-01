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
    "aria-label": ariaLabel,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    "aria-label"?: string;
  }) =>
    React.createElement(
      "button",
      {
        type: "button",
        onClick,
        "aria-label": ariaLabel,
      },
      children,
    ),
}));

vi.mock("@runsight/ui/tabs", () => {
  const TabsContext = React.createContext<{
    onValueChange?: (value: string) => void;
  }>({});

  function Tabs({
    value,
    onValueChange,
    children,
  }: {
    value?: string;
    onValueChange?: (value: string) => void;
    children: React.ReactNode;
  }) {
    return React.createElement(
      TabsContext.Provider,
      { value: { onValueChange } },
      React.createElement(
        "div",
        {
          "data-active-tab": value,
          "data-on-value-change": onValueChange ? "present" : "missing",
        },
        children,
      ),
    );
  }

  function TabsList({ children }: { children: React.ReactNode }) {
    return React.createElement("div", null, children);
  }

  function TabsTrigger({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) {
    const { onValueChange } = React.useContext(TabsContext);

    return React.createElement(
      "button",
      {
        type: "button",
        onClick: () => onValueChange?.(value),
        "data-value": value,
      },
      children,
    );
  }

  return { Tabs, TabsList, TabsTrigger };
});

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
  useWorkflow: () => ({
    data: { name: "Canonical workflow" },
  }),
  useUpdateWorkflow: () => ({
    mutate: mocks.updateWorkflowMutate,
  }),
}));

vi.mock("@/queries/runs", () => ({
  useRun: () => ({
    data: undefined,
  }),
  useCreateRun: () => ({
    mutate: mocks.createRunMutate,
  }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
}));

vi.mock("lucide-react", () => ({
  Layout: () => React.createElement("span", null, "layout"),
  Save: () => React.createElement("span", null, "save"),
}));

vi.mock("../RunButton", () => ({
  RunButton: () => React.createElement("div", null, "Run workflow"),
}));

vi.mock("../ExecutionMetrics", () => ({
  ExecutionMetrics: () => React.createElement("div", null, "Execution metrics"),
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
  mocks.canvasStoreState.toPersistedState = () => ({
    nodes: [{ id: "start" }],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  });
});

afterEach(() => {
  cleanup();
});

describe("RUN-509 canonical editor surface", () => {
  it("keeps the canonical editor labels and save affordance while opening the live canvas surface", async () => {
    const { user } = await renderCanvasPage();

    expect(
      screen
        .getAllByRole("button")
        .some((button) => button.textContent?.includes("Save")),
    ).toBe(true);
    expect(screen.getByText("Canonical workflow")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Canvas" }));

    expect(screen.getByText("workflow-canvas-surface")).toBeTruthy();
    expect(screen.queryByText("Visual canvas coming soon")).toBeNull();
    expect(screen.queryByRole("button", { name: "Switch to YAML" })).toBeNull();
  });

  it("still reaches the live editor surface when the workflow has no persisted canvas layout yet", async () => {
    mocks.canvasStoreState.toPersistedState = undefined;

    const { user } = await renderCanvasPage();

    await user.click(screen.getByRole("button", { name: "Canvas" }));

    expect(screen.getByText("workflow-canvas-surface")).toBeTruthy();
    expect(screen.queryByText("Visual canvas coming soon")).toBeNull();
  });
});
