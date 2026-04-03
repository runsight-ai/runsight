/**
 * WorkflowSurface mode model and UI contract (RUN-591).
 *
 * Defines the four surface modes (workflow, execution, historical, fork-draft)
 * and the per-panel UI rules for each mode. Pure data — no React, no rendering.
 */

// ---------------------------------------------------------------------------
// Mode type
// ---------------------------------------------------------------------------

export const WORKFLOW_SURFACE_MODES = [
  "workflow",
  "execution",
  "historical",
  "fork-draft",
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
}

// ---------------------------------------------------------------------------
// Props interface
// ---------------------------------------------------------------------------

export interface WorkflowSurfaceProps {
  mode: WorkflowSurfaceMode;
  workflowId: string;
  runId?: string;
}

// ---------------------------------------------------------------------------
// Per-mode contract definitions
// ---------------------------------------------------------------------------

const contracts: Record<WorkflowSurfaceMode, PanelContract> = {
  workflow: {
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
  },

  execution: {
    topbar: {
      nameEditable: false,
      metricsVisible: true,
      metricsStyle: "live",
      saveButton: "disabled",
    },
    palette: { visible: true, dimmed: true, searchEditable: false },
    canvas: {
      draggable: false,
      connectionsAllowed: false,
      deletionAllowed: false,
      costBadgeStyle: "live",
    },
    inspector: { trigger: "single-click", fieldsEditable: false },
    bottomPanel: { defaultState: "expanded" },
    statusBar: {
      stepCountFormat: "progress",
      metricsVisibility: "elapsed-and-cost",
    },
  },

  historical: {
    topbar: {
      nameEditable: false,
      metricsVisible: true,
      metricsStyle: "static",
      saveButton: "hidden",
    },
    palette: { visible: true, dimmed: true, searchEditable: false },
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
  },

  "fork-draft": {
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
  },
};

// ---------------------------------------------------------------------------
// Contract accessor
// ---------------------------------------------------------------------------

export function getContractForMode(mode: WorkflowSurfaceMode): PanelContract {
  return contracts[mode];
}

// ---------------------------------------------------------------------------
// Helper functions that derive UI flags from mode
// ---------------------------------------------------------------------------

export function isEditable(mode: WorkflowSurfaceMode): boolean {
  return contracts[mode].inspector.fieldsEditable;
}

export function isDraggable(mode: WorkflowSurfaceMode): boolean {
  return contracts[mode].canvas.draggable;
}

export function canCreateConnections(mode: WorkflowSurfaceMode): boolean {
  return contracts[mode].canvas.connectionsAllowed;
}

export function canDeleteNodes(mode: WorkflowSurfaceMode): boolean {
  return contracts[mode].canvas.deletionAllowed;
}

const tabMap: Record<
  WorkflowSurfaceMode,
  { inspector: string[]; bottomPanel: string[] }
> = {
  workflow: {
    inspector: ["Overview", "Prompt", "Conditions"],
    bottomPanel: ["Logs", "Runs"],
  },
  execution: {
    inspector: ["Overview", "Results", "Conditions"],
    bottomPanel: ["Logs", "Runs"],
  },
  historical: {
    inspector: ["Overview", "Output", "Eval", "Error"],
    bottomPanel: ["Logs", "Runs", "Regressions"],
  },
  "fork-draft": {
    inspector: ["Overview", "Prompt", "Conditions"],
    bottomPanel: ["Logs", "Runs"],
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
  return contracts[mode].inspector.trigger;
}

export function getBottomPanelDefault(
  mode: WorkflowSurfaceMode,
): "collapsed" | "expanded" {
  return contracts[mode].bottomPanel.defaultState;
}

export function getActionButton(mode: WorkflowSurfaceMode): {
  label: string;
  variant: string;
} {
  switch (mode) {
    case "execution":
      return { label: "Cancel", variant: "danger" };
    case "historical":
      return { label: "Fork", variant: "primary" };
    default:
      return { label: "Run", variant: "primary" };
  }
}

export function getSaveButtonState(
  mode: WorkflowSurfaceMode,
  isDirty: boolean,
): string {
  const button = contracts[mode].topbar.saveButton;
  if (button === "dirty-dependent") {
    return isDirty ? "primary" : "ghost";
  }
  return button;
}

export function getCostBadgeStyle(
  mode: WorkflowSurfaceMode,
): "estimated" | "live" | "final" {
  return contracts[mode].canvas.costBadgeStyle;
}

export function getStepCountFormat(
  mode: WorkflowSurfaceMode,
): "steps-and-edges" | "progress" {
  return contracts[mode].statusBar.stepCountFormat;
}

export function getMetricsVisibility(
  mode: WorkflowSurfaceMode,
): "hidden" | "elapsed-and-cost" | "duration-and-cost" {
  return contracts[mode].statusBar.metricsVisibility;
}

export function getCanvasYamlToggleVisibility(mode: WorkflowSurfaceMode): {
  canvas: boolean;
  yaml: boolean;
} {
  switch (mode) {
    case "execution":
      return { canvas: true, yaml: false };
    case "historical":
      return { canvas: false, yaml: false };
    default:
      return { canvas: true, yaml: true };
  }
}
