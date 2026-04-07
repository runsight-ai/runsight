/**
 * RED-TEAM tests for RUN-747: Save button does not commit to main.
 *
 * WorkflowSurface.handleSave currently calls updateWorkflow.mutateAsync (PUT /workflows/:id).
 * The correct behaviour is: Save → open CommitDialog → user enters message → commit to main.
 *
 * These tests will FAIL until WorkflowSurface is fixed to mirror the CanvasPage pattern.
 *
 * AC1: WorkflowSurface renders <CommitDialog> with correct props
 * AC2: Save opens CommitDialog instead of calling updateWorkflow
 * AC3: onCommitSuccess clears isDirty state
 * AC4: WorkflowSurface does NOT call updateWorkflow on save
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Hoisted mocks (must be before any imports that touch the module graph)
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
  const stateValues: unknown[] = [];

  const canvasStoreData = {
    nodes: [],
    edges: [],
    blockCount: 2,
    edgeCount: 1,
    yamlContent: "workflow:\n  name: Test\n",
    toPersistedState: vi.fn(() => ({ nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } })),
    markSaved: vi.fn(),
    setYamlContent: vi.fn(),
    hydrateFromPersisted: vi.fn(),
    setNodes: vi.fn(),
    setActiveRunId: vi.fn(),
  };

  const useCanvasStore = ((selector: (store: typeof canvasStoreData) => unknown) =>
    selector(canvasStoreData)) as {
    (selector: (store: typeof canvasStoreData) => unknown): unknown;
    getState: () => typeof canvasStoreData;
  };
  useCanvasStore.getState = () => canvasStoreData;

  return {
    stateValues,
    stateCursor: 0,
    topbarProps: [] as Array<Record<string, unknown>>,
    yamlEditorProps: [] as Array<Record<string, unknown>>,
    commitDialogProps: [] as Array<Record<string, unknown>>,
    canvasStoreData,
    useCanvasStore,
    updateWorkflowMutateAsync: vi.fn(),
    queryClient: { invalidateQueries: vi.fn() },
  };
});

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

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
      const setState = (value: T | ((prev: T) => T)) => {
        const prev = mocks.stateValues[index] as T;
        mocks.stateValues[index] =
          typeof value === "function" ? (value as (prev: T) => T)(prev) : value;
      };
      return [mocks.stateValues[index] as T, setState] as const;
    },
    useCallback: <T extends (...args: never[]) => unknown>(fn: T) => fn,
    useRef: <T,>(initial: T) => ({ current: initial }),
    useEffect: vi.fn(),
  };
});

vi.mock("react-router", () => ({
  useParams: () => ({ id: "wf_test" }),
  useBlocker: () => ({ state: "unblocked", proceed: vi.fn(), reset: vi.fn() }),
  Link: ({ children }: { children: React.ReactNode }) => React.createElement("a", null, children),
  useInRouterContext: () => true,
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mocks.queryClient,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: { name: "Test Flow", commit_sha: null, yaml: "workflow:\n  name: Test\n" },
  }),
  useUpdateWorkflow: () => ({
    mutateAsync: mocks.updateWorkflowMutateAsync,
    mutate: vi.fn(),
  }),
}));

vi.mock("@/queries/git", () => ({
  useGitStatus: () => ({ data: { is_clean: true, uncommitted_files: [] } }),
  useCommitWorkflow: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@/queries/runs", () => ({
  useCreateRun: () => ({ mutate: vi.fn() }),
  useCancelRun: () => ({ mutate: vi.fn() }),
  useRun: () => ({ data: undefined }),
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => ({ data: { items: [], total: 0 } }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
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

vi.mock("../WorkflowCanvas", () => ({
  WorkflowCanvas: () => React.createElement("div", null, "Canvas"),
}));

vi.mock("../PaletteSidebar", () => ({
  PaletteSidebar: () => React.createElement("div", null, "Palette"),
}));

vi.mock("../CanvasBottomPanel", () => ({
  CanvasBottomPanel: () => React.createElement("div", null, "Bottom Panel"),
}));

vi.mock("../CanvasStatusBar", () => ({
  CanvasStatusBar: () => React.createElement("div", null, "Status Bar"),
}));

vi.mock("../RunInspectorPanel", () => ({
  RunInspectorPanel: () => React.createElement("div", null, "Inspector"),
}));

vi.mock("../runs/RunInspectorPanel", () => ({
  RunInspectorPanel: () => React.createElement("div", null, "Inspector"),
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => React.createElement("div", null, "Provider Modal"),
}));

vi.mock("./workflowSurfaceContract", async () => {
  const actual = await vi.importActual<
    typeof import("../workflowSurfaceContract") // eslint-disable-line @typescript-eslint/consistent-type-imports
  >("../workflowSurfaceContract");
  return actual;
});

// ---------------------------------------------------------------------------
// Import the component under test AFTER all mocks are declared
// ---------------------------------------------------------------------------

const { WorkflowSurface } = await import("../WorkflowSurface");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderSurface() {
  mocks.stateCursor = 0;
  mocks.topbarProps.length = 0;
  mocks.yamlEditorProps.length = 0;
  mocks.commitDialogProps.length = 0;

  renderToStaticMarkup(
    React.createElement(WorkflowSurface, { mode: "edit", workflowId: "wf_test" }),
  );

  return {
    topbar: mocks.topbarProps.at(-1) as {
      isDirty?: boolean;
      onSave?: () => void;
    },
    yamlEditor: mocks.yamlEditorProps.at(-1) as {
      onDirtyChange?: (dirty: boolean) => void;
    },
    commitDialog: mocks.commitDialogProps.at(-1) as {
      open?: boolean;
      onOpenChange?: (open: boolean) => void;
      files?: unknown[];
      workflowId?: string;
      draft?: unknown;
      onCommitSuccess?: () => void;
    },
  };
}

// ---------------------------------------------------------------------------
// beforeEach reset
// ---------------------------------------------------------------------------

beforeEach(() => {
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.topbarProps.length = 0;
  mocks.yamlEditorProps.length = 0;
  mocks.commitDialogProps.length = 0;
  mocks.updateWorkflowMutateAsync.mockReset();
  mocks.queryClient.invalidateQueries.mockReset();
  mocks.canvasStoreData.markSaved.mockReset();
  mocks.canvasStoreData.toPersistedState.mockReset().mockReturnValue({
    nodes: [],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  });
});

// ---------------------------------------------------------------------------
// AC1: WorkflowSurface renders CommitDialog with correct props
// ---------------------------------------------------------------------------

describe("WorkflowSurface renders CommitDialog (AC1)", () => {
  it("renders CommitDialog at all", () => {
    renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render <CommitDialog>",
    ).toBeGreaterThan(0);
  });

  it("passes open prop to CommitDialog", () => {
    renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog before props can be checked",
    ).toBeGreaterThan(0);
    const commitDialog = mocks.commitDialogProps.at(-1) as Record<string, unknown>;
    expect(
      "open" in commitDialog,
      "CommitDialog must receive an 'open' prop",
    ).toBe(true);
  });

  it("CommitDialog starts closed (open=false)", () => {
    const { commitDialog } = renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog",
    ).toBeGreaterThan(0);
    expect(commitDialog.open).toBe(false);
  });

  it("passes onOpenChange prop to CommitDialog", () => {
    const { commitDialog } = renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog",
    ).toBeGreaterThan(0);
    expect(typeof commitDialog.onOpenChange).toBe("function");
  });

  it("passes files prop to CommitDialog", () => {
    const { commitDialog } = renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog",
    ).toBeGreaterThan(0);
    expect(Array.isArray(commitDialog.files)).toBe(true);
  });

  it("passes workflowId prop to CommitDialog", () => {
    const { commitDialog } = renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog",
    ).toBeGreaterThan(0);
    expect(commitDialog.workflowId).toBe("wf_test");
  });

  it("passes draft prop to CommitDialog", () => {
    const { commitDialog } = renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog",
    ).toBeGreaterThan(0);
    expect(commitDialog.draft).toBeDefined();
  });

  it("passes a YAML-only draft to CommitDialog", () => {
    const { commitDialog } = renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog",
    ).toBeGreaterThan(0);
    expect(commitDialog.draft).toEqual({
      yaml: "workflow:\n  name: Test\n",
    });
  });

  it("passes onCommitSuccess prop to CommitDialog", () => {
    const { commitDialog } = renderSurface();
    expect(
      mocks.commitDialogProps.length,
      "WorkflowSurface must render CommitDialog",
    ).toBeGreaterThan(0);
    expect(typeof commitDialog.onCommitSuccess).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// AC2: Save opens CommitDialog instead of calling updateWorkflow
// ---------------------------------------------------------------------------

describe("Save opens CommitDialog instead of calling updateWorkflow (AC2 + AC4)", () => {
  it("CommitDialog is closed before save is triggered", () => {
    const { commitDialog } = renderSurface();
    expect(commitDialog.open).toBe(false);
  });

  it("clicking save opens CommitDialog", () => {
    const firstRender = renderSurface();

    // Trigger save via the topbar onSave callback
    firstRender.topbar.onSave?.();

    const secondRender = renderSurface();
    expect(secondRender.commitDialog.open).toBe(true);
  });

  it("save does NOT call updateWorkflow.mutateAsync", () => {
    const firstRender = renderSurface();
    firstRender.topbar.onSave?.();

    expect(
      mocks.updateWorkflowMutateAsync,
      "updateWorkflow.mutateAsync must NOT be called when save is clicked — commit dialog should open instead",
    ).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// AC3: onCommitSuccess clears isDirty
//
// WorkflowSurface state indices (in order of useState calls):
//   0: mode, 1: workflowId, 2: activeRunId, 3: apiKeyModalOpen
//   4: activeTab, 5: isDirty, 6: selectedNode
//
// We seed activeTab = "yaml" so that YamlEditor renders and captures
// its onDirtyChange prop.
// ---------------------------------------------------------------------------

function renderSurfaceYamlTab() {
  mocks.stateCursor = 0;
  mocks.topbarProps.length = 0;
  mocks.yamlEditorProps.length = 0;
  mocks.commitDialogProps.length = 0;

  // Seed activeTab = "yaml" so YamlEditor is rendered
  mocks.stateValues[4] = "yaml";

  renderToStaticMarkup(
    React.createElement(WorkflowSurface, { mode: "edit", workflowId: "wf_test" }),
  );

  return {
    topbar: mocks.topbarProps.at(-1) as {
      isDirty?: boolean;
      onSave?: () => void;
    },
    yamlEditor: mocks.yamlEditorProps.at(-1) as {
      onDirtyChange?: (dirty: boolean) => void;
    },
    commitDialog: mocks.commitDialogProps.at(-1) as {
      open?: boolean;
      onOpenChange?: (open: boolean) => void;
      onCommitSuccess?: () => void;
    },
  };
}

describe("onCommitSuccess clears isDirty state (AC3)", () => {
  it("isDirty is true when yaml editor reports dirty", () => {
    const firstRender = renderSurfaceYamlTab();
    firstRender.yamlEditor.onDirtyChange?.(true);

    const dirtyRender = renderSurfaceYamlTab();
    expect(dirtyRender.topbar.isDirty).toBe(true);
  });

  it("isDirty is cleared after successful commit", () => {
    const firstRender = renderSurfaceYamlTab();
    firstRender.yamlEditor.onDirtyChange?.(true);

    const dirtyRender = renderSurfaceYamlTab();
    expect(dirtyRender.topbar.isDirty).toBe(true);

    // CommitDialog must exist for this to work — will fail if not yet rendered
    expect(
      dirtyRender.commitDialog,
      "WorkflowSurface must render CommitDialog so onCommitSuccess can clear isDirty",
    ).toBeDefined();

    dirtyRender.commitDialog.onCommitSuccess?.();

    const cleanRender = renderSurfaceYamlTab();
    expect(cleanRender.topbar.isDirty).toBe(false);
  });

  it("CommitDialog is closed after successful commit", () => {
    const firstRender = renderSurface();
    firstRender.topbar.onSave?.();

    const openRender = renderSurface();
    // CommitDialog must exist for open state to be readable
    expect(
      openRender.commitDialog,
      "WorkflowSurface must render CommitDialog — it was not found after save",
    ).toBeDefined();
    expect(openRender.commitDialog.open).toBe(true);

    openRender.commitDialog.onCommitSuccess?.();

    const afterCommit = renderSurface();
    expect(afterCommit.commitDialog.open).toBe(false);
  });
});
