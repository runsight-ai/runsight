import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const stateValues: unknown[] = [];
  const canvasStoreState = {
    setActiveRunId: vi.fn(),
    blockCount: 3,
    edgeCount: 2,
    yamlContent: "workflow:\n  name: Test Flow\n",
  };

  const useCanvasStore = ((selector: (store: typeof canvasStoreState) => unknown) =>
    selector(canvasStoreState)) as {
    (selector: (store: typeof canvasStoreState) => unknown): unknown;
    getState: () => typeof canvasStoreState;
  };

  useCanvasStore.getState = () => canvasStoreState;

  return {
    stateValues,
    stateCursor: 0,
    topbarProps: [] as Array<Record<string, unknown>>,
    yamlEditorProps: [] as Array<Record<string, unknown>>,
    commitDialogProps: [] as Array<Record<string, unknown>>,
    buttonProps: [] as Array<Record<string, unknown>>,
    blocker: {
      state: "unblocked",
      proceed: vi.fn(),
      reset: vi.fn(),
    },
    queryClient: {
      invalidateQueries: vi.fn(),
    },
    updateWorkflowMutate: vi.fn(),
    createRunMutate: vi.fn(),
    createSimBranch: vi.fn(),
    canvasStoreState,
    useCanvasStore,
  };
});

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof React>("react");

  return {
    ...actual,
    useState: <T,>(initial: T | (() => T)) => {
      const index = mocks.stateCursor++;

      if (!(index in mocks.stateValues)) {
        mocks.stateValues[index] =
          typeof initial === "function" ? (initial as () => T)() : initial;
      }

      const setState = (value: T | ((previous: T) => T)) => {
        const previous = mocks.stateValues[index] as T;
        mocks.stateValues[index] =
          typeof value === "function"
            ? (value as (previous: T) => T)(previous)
            : value;
      };

      return [mocks.stateValues[index] as T, setState] as const;
    },
    useCallback: <T extends (...args: never[]) => unknown>(fn: T) => fn,
    useRef: <T,>(initial: T) => ({ current: initial }),
  };
});

vi.mock("react-router", () => ({
  useParams: () => ({ id: "wf_1" }),
  useBlocker: () => mocks.blocker,
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mocks.queryClient,
}));

vi.mock("../CanvasTopbar", () => ({
  CanvasTopbar: (props: Record<string, unknown>) => {
    mocks.topbarProps.push(props);
    return React.createElement("canvas-topbar");
  },
}));

vi.mock("../YamlEditor", () => ({
  YamlEditor: (props: Record<string, unknown>) => {
    mocks.yamlEditorProps.push(props);
    return React.createElement("yaml-editor");
  },
}));

vi.mock("@/features/git/CommitDialog", () => ({
  CommitDialog: (props: Record<string, unknown>) => {
    mocks.commitDialogProps.push(props);
    return React.createElement("commit-dialog");
  },
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? React.createElement(React.Fragment, null, children) : null,
  DialogContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogTitle: ({ children }: { children: React.ReactNode }) =>
    React.createElement("h2", null, children),
  DialogFooter: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) => {
    mocks.buttonProps.push(props);
    return React.createElement("button", { type: "button" }, props.children);
  },
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: () => React.createElement("div", null, "Empty State"),
}));

vi.mock("../UncommittedBanner", () => ({
  UncommittedBanner: () => React.createElement("div", null, "Uncommitted"),
}));

vi.mock("../CanvasStatusBar", () => ({
  CanvasStatusBar: () => React.createElement("div", null, "Status"),
}));

vi.mock("../CanvasBottomPanel", () => ({
  CanvasBottomPanel: () => React.createElement("div", null, "Bottom Panel"),
}));

vi.mock("../FirstTimeTooltip", () => ({
  FirstTimeTooltip: () => React.createElement("div", null, "Tooltip"),
}));

vi.mock("../PaletteSidebar", () => ({
  PaletteSidebar: () => React.createElement("div", null, "Sidebar"),
}));

vi.mock("../ExploreBanner", () => ({
  ExploreBanner: () => React.createElement("div", null, "Explore"),
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => React.createElement("div", null, "Provider Modal"),
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    createSimBranch: mocks.createSimBranch,
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

const { Component: CanvasPage } = await import("../CanvasPage");

function renderPage() {
  mocks.stateCursor = 0;
  mocks.topbarProps.length = 0;
  mocks.yamlEditorProps.length = 0;
  mocks.commitDialogProps.length = 0;
  mocks.buttonProps.length = 0;

  renderToStaticMarkup(React.createElement(CanvasPage));

  return {
    topbar: mocks.topbarProps.at(-1) as { isDirty?: boolean; onSave?: () => void },
    yamlEditor: mocks.yamlEditorProps.at(-1) as {
      onDirtyChange?: (dirty: boolean) => void;
    },
    commitDialog: mocks.commitDialogProps.at(-1) as {
      open?: boolean;
      onCommitSuccess?: () => void;
    },
  };
}

function findButton(label: string) {
  return mocks.buttonProps.find((props) =>
    React.Children.toArray(props.children).some((child) => child === label),
  ) as { onClick?: () => void } | undefined;
}

beforeEach(() => {
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.topbarProps.length = 0;
  mocks.yamlEditorProps.length = 0;
  mocks.commitDialogProps.length = 0;
  mocks.buttonProps.length = 0;
  mocks.blocker.state = "unblocked";
  mocks.blocker.proceed.mockReset();
  mocks.blocker.reset.mockReset();
  mocks.queryClient.invalidateQueries.mockReset();
  mocks.updateWorkflowMutate.mockReset();
  mocks.createRunMutate.mockReset();
  mocks.createSimBranch.mockReset();
  mocks.canvasStoreState.setActiveRunId.mockReset();
});

describe("CanvasPage save flow (RUN-433)", () => {
  it("opens the commit dialog when the topbar save action runs", () => {
    const firstRender = renderPage();

    expect(firstRender.commitDialog.open).toBe(false);

    firstRender.topbar.onSave?.();

    const secondRender = renderPage();

    expect(secondRender.commitDialog.open).toBe(true);
    expect(mocks.updateWorkflowMutate).not.toHaveBeenCalled();
  });

  it("clears the dirty save cue after a successful commit", () => {
    const firstRender = renderPage();

    firstRender.yamlEditor.onDirtyChange?.(true);

    const dirtyRender = renderPage();
    expect(dirtyRender.topbar.isDirty).toBe(true);

    dirtyRender.commitDialog.onCommitSuccess?.();

    const cleanRender = renderPage();
    expect(cleanRender.topbar.isDirty).toBe(false);
  });

  it("uses the inline workflow save only for Save & Leave when navigation is blocked", () => {
    const firstRender = renderPage();
    firstRender.yamlEditor.onDirtyChange?.(true);
    renderPage();

    mocks.blocker.state = "blocked";
    renderPage();

    const saveAndLeaveButton = findButton("Save & Leave");

    expect(saveAndLeaveButton?.onClick).toBeTypeOf("function");

    saveAndLeaveButton?.onClick?.();

    expect(mocks.updateWorkflowMutate).toHaveBeenCalledWith(
      {
        id: "wf_1",
        data: { yaml: mocks.canvasStoreState.yamlContent },
      },
      { onSuccess: expect.any(Function) },
    );
    expect(mocks.blocker.proceed).toHaveBeenCalledTimes(1);
  });
});
