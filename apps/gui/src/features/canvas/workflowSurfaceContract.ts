/**
 * WorkflowSurface mode model and UI contract (RUN-649).
 *
 * Defines the three surface modes (readonly, edit, sim)
 * and the per-panel UI rules for each mode. Pure data — no React, no rendering.
 */

// ---------------------------------------------------------------------------
// Mode type
// ---------------------------------------------------------------------------

export const WORKFLOW_SURFACE_MODES = [
  "readonly",
  "edit",
  "sim",
] as const;

export type WorkflowSurfaceMode = (typeof WORKFLOW_SURFACE_MODES)[number];

// ---------------------------------------------------------------------------
// Panel contract types
// ---------------------------------------------------------------------------

export interface TopbarContract {
  nameEditable: boolean;
  metricsVisible: boolean;
  metricsStyle: "live" | "static" | "none";
  saveButton: "dirty-dependent" | "disabled" | "hidden";
}

export interface PaletteContract {
  visible: boolean;
  dimmed: boolean;
  searchEditable: boolean;
}

export interface CanvasContract {
  draggable: boolean;
  connectionsAllowed: boolean;
  deletionAllowed: boolean;
  costBadgeStyle: "estimated" | "live" | "final";
}

export interface InspectorContract {
  trigger: "double-click" | "single-click";
  fieldsEditable: boolean;
}

export interface BottomPanelContract {
  defaultState: "collapsed" | "expanded";
}

export interface StatusBarContract {
  stepCountFormat: "steps-and-edges" | "progress";
  metricsVisibility: "hidden" | "elapsed-and-cost" | "duration-and-cost";
}

export interface PanelContract {
  topbar: TopbarContract;
  palette: PaletteContract;
  canvas: CanvasContract;
  inspector: InspectorContract;
  bottomPanel: BottomPanelContract;
  statusBar: StatusBarContract;
  inspectorVisible: boolean;
}

// ---------------------------------------------------------------------------
// Props interface
// ---------------------------------------------------------------------------

export interface WorkflowSurfaceProps {
  mode: WorkflowSurfaceMode;
  workflowId?: string;
  runId?: string;
}

// ---------------------------------------------------------------------------
// Per-mode contract definitions
// ---------------------------------------------------------------------------

const contracts: Record<WorkflowSurfaceMode, PanelContract> = {
  edit: {
    topbar: {
      nameEditable: true,
      metricsVisible: false,
      metricsStyle: "none",
      saveButton: "dirty-dependent",
    },
    palette: { visible: true, dimmed: false, searchEditable: true },
    canvas: {
      draggable: true,
      connectionsAllowed: true,
      deletionAllowed: true,
      costBadgeStyle: "estimated",
    },
    inspector: { trigger: "double-click", fieldsEditable: true },
    bottomPanel: { defaultState: "collapsed" },
    statusBar: { stepCountFormat: "steps-and-edges", metricsVisibility: "hidden" },
    inspectorVisible: false,
  },

  sim: {
    topbar: {
      nameEditable: false,
      metricsVisible: true,
      metricsStyle: "live",
      saveButton: "hidden",
    },
    palette: { visible: true, dimmed: false, searchEditable: true },
    canvas: {
      draggable: true,
      connectionsAllowed: true,
      deletionAllowed: true,
      costBadgeStyle: "live",
    },
    inspector: { trigger: "single-click", fieldsEditable: false },
    bottomPanel: { defaultState: "expanded" },
    statusBar: {
      stepCountFormat: "progress",
      metricsVisibility: "elapsed-and-cost",
    },
    inspectorVisible: true,
  },

  readonly: {
    topbar: {
      nameEditable: false,
      metricsVisible: true,
      metricsStyle: "static",
      saveButton: "hidden",
    },
    palette: { visible: false, dimmed: false, searchEditable: false },
    canvas: {
      draggable: false,
      connectionsAllowed: false,
      deletionAllowed: false,
      costBadgeStyle: "final",
    },
    inspector: { trigger: "single-click", fieldsEditable: false },
    bottomPanel: { defaultState: "expanded" },
    statusBar: {
      stepCountFormat: "progress",
      metricsVisibility: "duration-and-cost",
    },
    inspectorVisible: true,
  },
};

// ---------------------------------------------------------------------------
// Contract accessor
// ---------------------------------------------------------------------------

export function getContractForMode(mode: WorkflowSurfaceMode): PanelContract {
  const contract = contracts[mode];
  if (!contract) {
    throw new Error(`Unknown workflow surface mode: ${mode}`);
  }
  return contract;
}

// ---------------------------------------------------------------------------
// Helper functions that derive UI flags from mode
// ---------------------------------------------------------------------------

export function isEditable(mode: WorkflowSurfaceMode): boolean {
  return getContractForMode(mode).inspector.fieldsEditable || getContractForMode(mode).canvas.draggable;
}

export function isDraggable(mode: WorkflowSurfaceMode): boolean {
  return getContractForMode(mode).canvas.draggable;
}

export function canCreateConnections(mode: WorkflowSurfaceMode): boolean {
  return getContractForMode(mode).canvas.connectionsAllowed;
}

export function canDeleteNodes(mode: WorkflowSurfaceMode): boolean {
  return getContractForMode(mode).canvas.deletionAllowed;
}

const tabMap: Record<
  WorkflowSurfaceMode,
  { inspector: string[]; bottomPanel: string[] }
> = {
  edit: {
    inspector: ["Overview", "Prompt", "Conditions"],
    bottomPanel: ["Logs", "Runs"],
  },
  sim: {
    inspector: ["Overview", "Results", "Conditions"],
    bottomPanel: ["Logs", "Runs"],
  },
  readonly: {
    inspector: ["Overview", "Output", "Eval", "Error"],
    bottomPanel: ["Logs", "Runs", "Regressions"],
  },
};

export function getAvailableTabs(
  mode: WorkflowSurfaceMode,
  panel: "inspector" | "bottomPanel",
): string[] {
  return tabMap[mode][panel];
}

export function getInspectorTrigger(
  mode: WorkflowSurfaceMode,
): "double-click" | "single-click" {
  return getContractForMode(mode).inspector.trigger;
}

export function getBottomPanelDefault(
  mode: WorkflowSurfaceMode,
): "collapsed" | "expanded" {
  return getContractForMode(mode).bottomPanel.defaultState;
}

export function getActionButton(mode: WorkflowSurfaceMode): {
  label: string;
  variant: string;
} {
  switch (mode) {
    case "edit":
      return { label: "Save+Run", variant: "primary" };
    case "sim":
      return { label: "Cancel", variant: "danger" };
    case "readonly":
      return { label: "Fork", variant: "primary" };
  }
}

export function getSaveButtonState(
  mode: WorkflowSurfaceMode,
  isDirty: boolean,
): string {
  const button = getContractForMode(mode).topbar.saveButton;
  if (button === "dirty-dependent") {
    return isDirty ? "enabled" : "disabled";
  }
  return button;
}

export function getCostBadgeStyle(
  mode: WorkflowSurfaceMode,
): "estimated" | "live" | "final" {
  return getContractForMode(mode).canvas.costBadgeStyle;
}

export function getStepCountFormat(
  mode: WorkflowSurfaceMode,
): "steps-and-edges" | "progress" {
  return getContractForMode(mode).statusBar.stepCountFormat;
}

export function getMetricsVisibility(
  mode: WorkflowSurfaceMode,
): "hidden" | "elapsed-and-cost" | "duration-and-cost" {
  return getContractForMode(mode).statusBar.metricsVisibility;
}

export function getCanvasYamlToggleVisibility(mode: WorkflowSurfaceMode): {
  canvas: boolean;
  yaml: boolean;
} {
  switch (mode) {
    case "sim":
      return { canvas: true, yaml: false };
    case "readonly":
      return { canvas: false, yaml: false };
    case "edit":
      return { canvas: true, yaml: true };
  }
}
