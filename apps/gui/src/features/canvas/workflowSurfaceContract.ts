export type WorkflowSurfaceMode = "workflow" | "execution" | "historical" | "fork-draft";

export interface WorkflowSurfaceProps {
  workflowId?: string;
  runId?: string;
  initialMode: WorkflowSurfaceMode;
  hasRunOverlay?: boolean;
  isEditable?: boolean;
}

export interface WorkflowSurfaceRegionConfig {
  visible: boolean;
  editable: boolean;
}

export interface WorkflowSurfaceModeConfig {
  regions: {
    topbar: WorkflowSurfaceRegionConfig;
    center: WorkflowSurfaceRegionConfig;
    palette: WorkflowSurfaceRegionConfig;
    yaml: WorkflowSurfaceRegionConfig;
    inspector: WorkflowSurfaceRegionConfig;
    footer: WorkflowSurfaceRegionConfig;
    statusBar: WorkflowSurfaceRegionConfig;
  };
  actions: {
    save: boolean;
    run: boolean;
    fork: boolean;
    openWorkflow: boolean;
  };
  capabilities: {
    readOnly: boolean;
    usesRunOverlay: boolean;
    supportsSameSurfaceTransition: boolean;
    routeChangeRequired: boolean;
  };
}

export const WORKFLOW_SURFACE_MODES: WorkflowSurfaceMode[] = [
  "workflow",
  "execution",
  "historical",
  "fork-draft",
];

export const WORKFLOW_SURFACE_MODE_CONFIG: Record<
  WorkflowSurfaceMode,
  WorkflowSurfaceModeConfig
> = {
  workflow: {
    regions: {
      topbar: { visible: true, editable: true },
      center: { visible: true, editable: true },
      palette: { visible: true, editable: true },
      yaml: { visible: true, editable: true },
      inspector: { visible: true, editable: true },
      footer: { visible: true, editable: true },
      statusBar: { visible: true, editable: true },
    },
    actions: {
      save: true,
      run: true,
      fork: false,
      openWorkflow: false,
    },
    capabilities: {
      readOnly: false,
      usesRunOverlay: false,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
  execution: {
    regions: {
      topbar: { visible: true, editable: false },
      center: { visible: true, editable: false },
      palette: { visible: true, editable: false },
      yaml: { visible: true, editable: false },
      inspector: { visible: true, editable: false },
      footer: { visible: true, editable: false },
      statusBar: { visible: true, editable: false },
    },
    actions: {
      save: false,
      run: false,
      fork: false,
      openWorkflow: false,
    },
    capabilities: {
      readOnly: true,
      usesRunOverlay: true,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
  historical: {
    regions: {
      topbar: { visible: true, editable: false },
      center: { visible: true, editable: false },
      palette: { visible: false, editable: false },
      yaml: { visible: false, editable: false },
      inspector: { visible: true, editable: false },
      footer: { visible: true, editable: false },
      statusBar: { visible: true, editable: false },
    },
    actions: {
      save: false,
      run: false,
      fork: true,
      openWorkflow: true,
    },
    capabilities: {
      readOnly: true,
      usesRunOverlay: true,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
  "fork-draft": {
    regions: {
      topbar: { visible: true, editable: true },
      center: { visible: true, editable: true },
      palette: { visible: true, editable: true },
      yaml: { visible: true, editable: true },
      inspector: { visible: true, editable: true },
      footer: { visible: true, editable: true },
      statusBar: { visible: true, editable: true },
    },
    actions: {
      save: true,
      run: true,
      fork: false,
      openWorkflow: false,
    },
    capabilities: {
      readOnly: false,
      usesRunOverlay: false,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
};

export function getWorkflowSurfaceModeConfig(mode: WorkflowSurfaceMode) {
  return WORKFLOW_SURFACE_MODE_CONFIG[mode];
}
