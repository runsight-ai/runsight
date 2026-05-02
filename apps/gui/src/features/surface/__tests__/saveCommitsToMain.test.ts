/**
 * WorkflowSurface save-to-commit-dialog coverage.
 *
 * Save opens the commit dialog with the current YAML draft instead of mutating
 * the workflow directly. A successful commit clears dirty state and closes the
 * dialog.
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CanvasStoreFixture } from "./helpers/saveCommitsToMainFixtures";

// ---------------------------------------------------------------------------
// Hoisted mocks (must be before any imports that touch the module graph)
// ---------------------------------------------------------------------------

const mocks = await vi.hoisted(async () => {
  const fixtures = await import("./helpers/saveCommitsToMainFixtures");
  const makeMock = (implementation?: (...args: unknown[]) => unknown) => vi.fn(implementation);
  const stateHarness = fixtures.createStateHarness();
  const capturedProps = fixtures.createCapturedSurfaceProps();
  const canvasStoreData = fixtures.createCanvasStoreFixture(makeMock);
  const queryClient = fixtures.createQueryClientFixture(makeMock);

  const useCanvasStore = ((selector: (store: CanvasStoreFixture) => unknown) =>
    selector(canvasStoreData)) as {
    (selector: (store: CanvasStoreFixture) => unknown): unknown;
    getState: () => CanvasStoreFixture;
  };
  useCanvasStore.getState = () => canvasStoreData;

  return {
    fixtures,
    ...stateHarness,
    ...capturedProps,
    canvasStoreData,
    useCanvasStore,
    updateWorkflowMutateAsync: vi.fn(),
    queryClient,
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
  useParams: () => ({ id: mocks.fixtures.REVIEW_WORKFLOW_ID }),
  useBlocker: () => ({ state: "unblocked", proceed: vi.fn(), reset: vi.fn() }),
  Link: ({ children }: { children: React.ReactNode }) => React.createElement("a", null, children),
  useInRouterContext: () => true,
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mocks.queryClient,
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: mocks.fixtures.REVIEW_WORKFLOW_QUERY_DATA,
  }),
  useUpdateWorkflow: () => ({
    mutateAsync: mocks.updateWorkflowMutateAsync,
    mutate: vi.fn(),
  }),
}));

vi.mock("@/queries/git", () => ({
  useGitStatus: () => ({ data: mocks.fixtures.CLEAN_GIT_STATUS_QUERY_DATA }),
  useCommitWorkflow: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@/queries/runs", () => ({
  useCreateRun: () => ({ mutate: vi.fn() }),
  useCancelRun: () => ({ mutate: vi.fn() }),
  useRun: () => ({ data: undefined }),
  useRunNodes: () => ({ data: [], isLoading: false, isError: false, error: null, refetch: vi.fn() }),
  useRunRegressions: () => ({ data: { count: 0, issues: [] }, isLoading: false, isError: false }),
  useRunLogs: () => ({ data: { items: [] }, isLoading: false, isError: false }),
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => ({ data: { items: [], total: 0 } }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: mocks.useCanvasStore,
}));

vi.mock("../SurfaceTopbar", () => ({
  SurfaceTopbar: (props: Record<string, unknown>) => {
    mocks.topbarProps.push(props);
    return React.createElement("canvas-topbar");
  },
}));

vi.mock("../SurfaceYamlEditor", () => ({
  SurfaceYamlEditor: (props: Record<string, unknown>) => {
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

vi.mock("../SurfaceCanvas", () => ({
  SurfaceCanvas: () => React.createElement("div", null, "Canvas"),
}));

vi.mock("../PaletteSidebar", () => ({
  PaletteSidebar: () => React.createElement("div", null, "Palette"),
}));

vi.mock("../SurfaceBottomPanel", () => ({
  SurfaceBottomPanel: () => React.createElement("div", null, "Bottom Panel"),
}));

vi.mock("../SurfaceStatusBar", () => ({
  SurfaceStatusBar: () => React.createElement("div", null, "Status Bar"),
}));

vi.mock("../SurfaceInspectorPanel", () => ({
  SurfaceInspectorPanel: () => React.createElement("div", null, "Inspector"),
}));

vi.mock("@/components/provider/ProviderModal", () => ({
  ProviderModal: () => React.createElement("div", null, "Provider Modal"),
}));

vi.mock("../surfaceContract", async () => {
  const actual = await vi.importActual<
    typeof import("../surfaceContract") // eslint-disable-line @typescript-eslint/consistent-type-imports
  >("../surfaceContract");
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
  mocks.fixtures.prepareSurfaceRenderHarness(mocks);

  renderToStaticMarkup(
    React.createElement(WorkflowSurface, mocks.fixtures.WORKFLOW_SURFACE_EDIT_PROPS),
  );

  return mocks.fixtures.latestSurfaceRenderResult(mocks);
}

// ---------------------------------------------------------------------------
// beforeEach reset
// ---------------------------------------------------------------------------

beforeEach(() => {
  mocks.fixtures.resetSaveCommitsHarness(mocks);
});

// ---------------------------------------------------------------------------
// 1. WorkflowSurface renders CommitDialog with the commit draft
// ---------------------------------------------------------------------------

describe("WorkflowSurface renders CommitDialog", () => {
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
    expect(commitDialog.workflowId).toBe("review_flow");
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
    expect(commitDialog.draft).toEqual(
      expect.objectContaining({
        yaml: "workflow:\n  name: Review Flow\n",
      }),
    );
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
// 2. Save opens CommitDialog instead of updating the workflow directly
// ---------------------------------------------------------------------------

describe("Save opens CommitDialog instead of calling updateWorkflow", () => {
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
// 3. onCommitSuccess clears dirty state
// ---------------------------------------------------------------------------

function renderSurfaceYamlTab() {
  mocks.fixtures.prepareSurfaceRenderHarness(mocks);
  mocks.fixtures.seedYamlTabState(mocks);

  renderToStaticMarkup(
    React.createElement(WorkflowSurface, mocks.fixtures.WORKFLOW_SURFACE_EDIT_PROPS),
  );

  return mocks.fixtures.latestSurfaceRenderResult(mocks);
}

describe("onCommitSuccess clears isDirty state", () => {
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

    // CommitDialog must exist before onCommitSuccess can clear isDirty.
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
