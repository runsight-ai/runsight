export const REVIEW_WORKFLOW_ID = "review_flow";
export const REVIEW_WORKFLOW_NAME = "Review Flow";
export const REVIEW_WORKFLOW_YAML = "workflow:\n  name: Review Flow\n";

export const WORKFLOW_SURFACE_EDIT_PROPS = {
  mode: "edit",
  workflowId: REVIEW_WORKFLOW_ID,
} as const;

export const REVIEW_WORKFLOW_QUERY_DATA = {
  name: REVIEW_WORKFLOW_NAME,
  commit_sha: null,
  yaml: REVIEW_WORKFLOW_YAML,
} as const;

export const CLEAN_GIT_STATUS_QUERY_DATA = {
  is_clean: true,
  uncommitted_files: [] as string[],
} as const;

export const YAML_TAB_STATE_INDEX = 4;

type UnknownFunction = (...args: unknown[]) => unknown;

export type ResettableMockFunction = UnknownFunction & {
  mockReset: () => ResettableMockFunction;
  mockReturnValue: (value: unknown) => ResettableMockFunction;
};

export type MockFactory = (implementation?: UnknownFunction) => ResettableMockFunction;

export type PersistedCanvasState = {
  nodes: unknown[];
  edges: unknown[];
  viewport: { x: number; y: number; zoom: number };
};

export type CanvasStoreFixture = {
  nodes: unknown[];
  edges: unknown[];
  blockCount: number;
  edgeCount: number;
  yamlContent: string;
  toPersistedState: ResettableMockFunction;
  markSaved: ResettableMockFunction;
  setYamlContent: ResettableMockFunction;
  hydrateFromPersisted: ResettableMockFunction;
  setNodes: ResettableMockFunction;
  setActiveRunId: ResettableMockFunction;
};

export type QueryClientFixture = {
  invalidateQueries: ResettableMockFunction;
};

export type StateHarness = {
  stateValues: unknown[];
  stateCursor: number;
};

export type SaveCommitsTopbarProps = {
  isDirty?: boolean;
  onSave?: () => void;
} & Record<string, unknown>;

export type SaveCommitsYamlEditorProps = {
  onDirtyChange?: (dirty: boolean) => void;
} & Record<string, unknown>;

export type SaveCommitsCommitDialogProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  files?: unknown[];
  workflowId?: string;
  draft?: unknown;
  onCommitSuccess?: () => void;
} & Record<string, unknown>;

export type CapturedSurfaceProps = {
  topbarProps: SaveCommitsTopbarProps[];
  yamlEditorProps: SaveCommitsYamlEditorProps[];
  commitDialogProps: SaveCommitsCommitDialogProps[];
};

export type SaveCommitsRenderResult = {
  topbar: SaveCommitsTopbarProps;
  yamlEditor: SaveCommitsYamlEditorProps;
  commitDialog: SaveCommitsCommitDialogProps;
};

export function createPersistedCanvasState(): PersistedCanvasState {
  return {
    nodes: [],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  };
}

export function createCanvasStoreFixture(makeMock: MockFactory): CanvasStoreFixture {
  return {
    nodes: [],
    edges: [],
    blockCount: 2,
    edgeCount: 1,
    yamlContent: REVIEW_WORKFLOW_YAML,
    toPersistedState: makeMock(() => createPersistedCanvasState()),
    markSaved: makeMock(),
    setYamlContent: makeMock(),
    hydrateFromPersisted: makeMock(),
    setNodes: makeMock(),
    setActiveRunId: makeMock(),
  };
}

export function createQueryClientFixture(makeMock: MockFactory): QueryClientFixture {
  return {
    invalidateQueries: makeMock(),
  };
}

export function createStateHarness(): StateHarness {
  return {
    stateValues: [],
    stateCursor: 0,
  };
}

export function createCapturedSurfaceProps(): CapturedSurfaceProps {
  return {
    topbarProps: [],
    yamlEditorProps: [],
    commitDialogProps: [],
  };
}

export function resetStateHarness(harness: StateHarness): void {
  harness.stateValues.length = 0;
  harness.stateCursor = 0;
}

export function resetCapturedSurfaceProps(captured: CapturedSurfaceProps): void {
  captured.topbarProps.length = 0;
  captured.yamlEditorProps.length = 0;
  captured.commitDialogProps.length = 0;
}

export function prepareSurfaceRenderHarness(
  harness: StateHarness & CapturedSurfaceProps,
): void {
  harness.stateCursor = 0;
  resetCapturedSurfaceProps(harness);
}

export function seedYamlTabState(harness: StateHarness): void {
  harness.stateValues[YAML_TAB_STATE_INDEX] = "yaml";
}

export function latestSurfaceRenderResult(
  captured: CapturedSurfaceProps,
): SaveCommitsRenderResult {
  return {
    topbar: captured.topbarProps.at(-1) as SaveCommitsTopbarProps,
    yamlEditor: captured.yamlEditorProps.at(-1) as SaveCommitsYamlEditorProps,
    commitDialog: captured.commitDialogProps.at(-1) as SaveCommitsCommitDialogProps,
  };
}

export function resetCanvasStoreFixture(canvasStoreData: CanvasStoreFixture): void {
  canvasStoreData.markSaved.mockReset();
  canvasStoreData.toPersistedState
    .mockReset()
    .mockReturnValue(createPersistedCanvasState());
}

export function resetSaveCommitsHarness(
  harness: StateHarness &
    CapturedSurfaceProps & {
      updateWorkflowMutateAsync: ResettableMockFunction;
      queryClient: QueryClientFixture;
      canvasStoreData: CanvasStoreFixture;
    },
): void {
  resetStateHarness(harness);
  resetCapturedSurfaceProps(harness);
  harness.updateWorkflowMutateAsync.mockReset();
  harness.queryClient.invalidateQueries.mockReset();
  resetCanvasStoreFixture(harness.canvasStoreData);
}
