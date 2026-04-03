/**
 * RED-TEAM tests for RUN-591: Define WorkflowSurface mode model and UI contract.
 *
 * This ticket defines the single-surface state model for WorkflowSurface and
 * the UI contract for each mode: workflow, execution, historical, fork-draft.
 *
 * Tests verify:
 * 1. WorkflowSurfaceMode type covers all 4 modes
 * 2. A contract/config object maps each mode to per-panel UI rules
 * 3. Helper functions derive UI flags from mode
 * 4. Per-mode rules match the flow-spec tables (topbar, palette, canvas,
 *    inspector, bottom panel, status bar)
 * 5. Edge cases: no run overlay in workflow mode, historical disables editing,
 *    fork-draft inherits workflow editing rules
 *
 * Expected failures: the contract module does not exist yet.
 */

import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Imports from the contract module that SHOULD exist after implementation.
// These will fail at import time — that's the point.
// ---------------------------------------------------------------------------

import type {
  WorkflowSurfaceMode,
  WorkflowSurfaceProps,
  PanelContract,
  TopbarContract,
  PaletteContract,
  CanvasContract,
  InspectorContract,
  BottomPanelContract,
  StatusBarContract,
} from "../workflowSurfaceContract";

// Type-level usage: these variables exercise the type imports so that they serve
// a testable purpose (verifying the types exist and are exported correctly).
// At runtime they are no-ops — the real assertions are in the test blocks below.
const _mode: WorkflowSurfaceMode = "workflow" as WorkflowSurfaceMode;
const _props: WorkflowSurfaceProps = {} as WorkflowSurfaceProps;
const _panel: PanelContract = {} as PanelContract;
const _topbar: TopbarContract = {} as TopbarContract;
const _palette: PaletteContract = {} as PaletteContract;
const _canvas: CanvasContract = {} as CanvasContract;
const _inspector: InspectorContract = {} as InspectorContract;
const _bottomPanel: BottomPanelContract = {} as BottomPanelContract;
const _statusBar: StatusBarContract = {} as StatusBarContract;
void _mode; void _props; void _panel; void _topbar; void _palette;
void _canvas; void _inspector; void _bottomPanel; void _statusBar;

import {
  WORKFLOW_SURFACE_MODES,
  getContractForMode,
  isEditable,
  isDraggable,
  canCreateConnections,
  canDeleteNodes,
  getAvailableTabs,
  getInspectorTrigger,
  getBottomPanelDefault,
  getActionButton,
  getSaveButtonState,
  getCostBadgeStyle,
  getStepCountFormat,
  getMetricsVisibility,
  getCanvasYamlToggleVisibility,
} from "../workflowSurfaceContract";

// ===========================================================================
// 1. WorkflowSurfaceMode type and WORKFLOW_SURFACE_MODES constant
// ===========================================================================

describe("WorkflowSurfaceMode enum/constant (RUN-591 AC1)", () => {
  it("WORKFLOW_SURFACE_MODES is an array with exactly 4 modes", () => {
    expect(Array.isArray(WORKFLOW_SURFACE_MODES)).toBe(true);
    expect(WORKFLOW_SURFACE_MODES).toHaveLength(4);
  });

  it("includes 'workflow' mode", () => {
    expect(WORKFLOW_SURFACE_MODES).toContain("workflow");
  });

  it("includes 'execution' mode", () => {
    expect(WORKFLOW_SURFACE_MODES).toContain("execution");
  });

  it("includes 'historical' mode", () => {
    expect(WORKFLOW_SURFACE_MODES).toContain("historical");
  });

  it("includes 'fork-draft' mode", () => {
    expect(WORKFLOW_SURFACE_MODES).toContain("fork-draft");
  });

  it("contains no duplicate modes", () => {
    const unique = new Set(WORKFLOW_SURFACE_MODES);
    expect(unique.size).toBe(WORKFLOW_SURFACE_MODES.length);
  });
});

// ===========================================================================
// 2. getContractForMode returns a contract for each mode
// ===========================================================================

describe("getContractForMode returns per-mode contracts (RUN-591 AC2)", () => {
  it("is a function", () => {
    expect(getContractForMode).toBeTypeOf("function");
  });

  for (const mode of ["workflow", "execution", "historical", "fork-draft"] as const) {
    it(`returns a contract object for '${mode}'`, () => {
      const contract = getContractForMode(mode);
      expect(contract).toBeDefined();
      expect(contract).toHaveProperty("topbar");
      expect(contract).toHaveProperty("palette");
      expect(contract).toHaveProperty("canvas");
      expect(contract).toHaveProperty("inspector");
      expect(contract).toHaveProperty("bottomPanel");
      expect(contract).toHaveProperty("statusBar");
    });
  }
});

// ===========================================================================
// 3. Topbar contract per mode
// ===========================================================================

describe("Topbar contract rules (RUN-591)", () => {
  it("workflow: name is editable", () => {
    const contract = getContractForMode("workflow");
    expect(contract.topbar.nameEditable).toBe(true);
  });

  it("execution: name is NOT editable", () => {
    const contract = getContractForMode("execution");
    expect(contract.topbar.nameEditable).toBe(false);
  });

  it("historical: name is NOT editable", () => {
    const contract = getContractForMode("historical");
    expect(contract.topbar.nameEditable).toBe(false);
  });

  it("workflow: metrics are hidden", () => {
    const contract = getContractForMode("workflow");
    expect(contract.topbar.metricsVisible).toBe(false);
  });

  it("execution: metrics are visible (live)", () => {
    const contract = getContractForMode("execution");
    expect(contract.topbar.metricsVisible).toBe(true);
    expect(contract.topbar.metricsStyle).toBe("live");
  });

  it("historical: metrics are visible (static)", () => {
    const contract = getContractForMode("historical");
    expect(contract.topbar.metricsVisible).toBe(true);
    expect(contract.topbar.metricsStyle).toBe("static");
  });

  it("workflow: canvas/YAML toggle shows both options", () => {
    const result = getCanvasYamlToggleVisibility("workflow");
    expect(result).toEqual({ canvas: true, yaml: true });
  });

  it("execution: canvas only, no YAML swap", () => {
    const result = getCanvasYamlToggleVisibility("execution");
    expect(result).toEqual({ canvas: true, yaml: false });
  });

  it("historical: toggle is hidden entirely", () => {
    const result = getCanvasYamlToggleVisibility("historical");
    expect(result).toEqual({ canvas: false, yaml: false });
  });

  it("workflow: save button is ghost/primary (dirty-dependent)", () => {
    const contract = getContractForMode("workflow");
    expect(contract.topbar.saveButton).toBe("dirty-dependent");
  });

  it("execution: save button is disabled", () => {
    const contract = getContractForMode("execution");
    expect(contract.topbar.saveButton).toBe("disabled");
  });

  it("historical: save button is hidden", () => {
    const contract = getContractForMode("historical");
    expect(contract.topbar.saveButton).toBe("hidden");
  });

  it("workflow: action button is 'run'", () => {
    const result = getActionButton("workflow");
    expect(result.label).toBe("Run");
    expect(result.variant).toBe("primary");
  });

  it("execution: action button is 'cancel' with danger variant", () => {
    const result = getActionButton("execution");
    expect(result.label).toBe("Cancel");
    expect(result.variant).toBe("danger");
  });

  it("historical: action button is 'fork' with primary variant", () => {
    const result = getActionButton("historical");
    expect(result.label).toBe("Fork");
    expect(result.variant).toBe("primary");
  });
});

describe("getSaveButtonState helper (RUN-591)", () => {
  it("workflow + clean: returns ghost", () => {
    expect(getSaveButtonState("workflow", false)).toBe("ghost");
  });

  it("workflow + dirty: returns primary", () => {
    expect(getSaveButtonState("workflow", true)).toBe("primary");
  });

  it("execution: always returns disabled regardless of dirty", () => {
    expect(getSaveButtonState("execution", true)).toBe("disabled");
    expect(getSaveButtonState("execution", false)).toBe("disabled");
  });

  it("historical: always returns hidden", () => {
    expect(getSaveButtonState("historical", false)).toBe("hidden");
  });

  it("fork-draft + dirty: returns primary (same editing rules as workflow)", () => {
    expect(getSaveButtonState("fork-draft", true)).toBe("primary");
  });
});

// ===========================================================================
// 4. Palette contract per mode
// ===========================================================================

describe("Palette contract rules (RUN-591)", () => {
  it("workflow: palette is visible and active", () => {
    const contract = getContractForMode("workflow");
    expect(contract.palette.visible).toBe(true);
    expect(contract.palette.dimmed).toBe(false);
  });

  it("execution: palette is visible but dimmed", () => {
    const contract = getContractForMode("execution");
    expect(contract.palette.visible).toBe(true);
    expect(contract.palette.dimmed).toBe(true);
  });

  it("historical: palette is visible but dimmed", () => {
    const contract = getContractForMode("historical");
    expect(contract.palette.visible).toBe(true);
    expect(contract.palette.dimmed).toBe(true);
  });

  it("workflow: blocks are draggable", () => {
    expect(isDraggable("workflow")).toBe(true);
  });

  it("execution: blocks are NOT draggable", () => {
    expect(isDraggable("execution")).toBe(false);
  });

  it("historical: blocks are NOT draggable", () => {
    expect(isDraggable("historical")).toBe(false);
  });

  it("workflow: search is editable", () => {
    const contract = getContractForMode("workflow");
    expect(contract.palette.searchEditable).toBe(true);
  });

  it("execution: search is NOT editable", () => {
    const contract = getContractForMode("execution");
    expect(contract.palette.searchEditable).toBe(false);
  });

  it("historical: search is NOT editable", () => {
    const contract = getContractForMode("historical");
    expect(contract.palette.searchEditable).toBe(false);
  });
});

// ===========================================================================
// 5. Canvas contract per mode
// ===========================================================================

describe("Canvas contract rules (RUN-591)", () => {
  it("workflow: nodes are draggable", () => {
    expect(isDraggable("workflow")).toBe(true);
  });

  it("execution: nodes are NOT draggable", () => {
    expect(isDraggable("execution")).toBe(false);
  });

  it("historical: nodes are NOT draggable (read-only)", () => {
    expect(isDraggable("historical")).toBe(false);
  });

  it("workflow: connection creation allowed", () => {
    expect(canCreateConnections("workflow")).toBe(true);
  });

  it("execution: connection creation NOT allowed", () => {
    expect(canCreateConnections("execution")).toBe(false);
  });

  it("historical: connection creation NOT allowed", () => {
    expect(canCreateConnections("historical")).toBe(false);
  });

  it("workflow: node deletion allowed", () => {
    expect(canDeleteNodes("workflow")).toBe(true);
  });

  it("execution: node deletion NOT allowed", () => {
    expect(canDeleteNodes("execution")).toBe(false);
  });

  it("historical: node deletion NOT allowed", () => {
    expect(canDeleteNodes("historical")).toBe(false);
  });

  it("workflow: cost badges show estimated (~)", () => {
    const style = getCostBadgeStyle("workflow");
    expect(style).toBe("estimated");
  });

  it("execution: cost badges show live ($)", () => {
    const style = getCostBadgeStyle("execution");
    expect(style).toBe("live");
  });

  it("historical: cost badges show final ($)", () => {
    const style = getCostBadgeStyle("historical");
    expect(style).toBe("final");
  });
});

// ===========================================================================
// 6. Inspector contract per mode
// ===========================================================================

describe("Inspector contract rules (RUN-591)", () => {
  it("workflow: inspector opens on double-click", () => {
    const trigger = getInspectorTrigger("workflow");
    expect(trigger).toBe("double-click");
  });

  it("execution: inspector opens on single-click", () => {
    const trigger = getInspectorTrigger("execution");
    expect(trigger).toBe("single-click");
  });

  it("historical: inspector opens on single-click", () => {
    const trigger = getInspectorTrigger("historical");
    expect(trigger).toBe("single-click");
  });

  it("workflow: inspector fields are all editable", () => {
    const contract = getContractForMode("workflow");
    expect(contract.inspector.fieldsEditable).toBe(true);
  });

  it("execution: inspector fields are read-only", () => {
    const contract = getContractForMode("execution");
    expect(contract.inspector.fieldsEditable).toBe(false);
  });

  it("historical: inspector fields are read-only", () => {
    const contract = getContractForMode("historical");
    expect(contract.inspector.fieldsEditable).toBe(false);
  });

  it("workflow: inspector tabs are Overview, Prompt, Conditions", () => {
    const tabs = getAvailableTabs("workflow", "inspector");
    expect(tabs).toEqual(["Overview", "Prompt", "Conditions"]);
  });

  it("execution: inspector tabs are Overview, Results, Conditions", () => {
    const tabs = getAvailableTabs("execution", "inspector");
    expect(tabs).toEqual(["Overview", "Results", "Conditions"]);
  });

  it("historical: inspector tabs are Overview, Output, Eval, Error", () => {
    const tabs = getAvailableTabs("historical", "inspector");
    expect(tabs).toEqual(["Overview", "Output", "Eval", "Error"]);
  });
});

// ===========================================================================
// 7. Bottom panel contract per mode
// ===========================================================================

describe("Bottom panel contract rules (RUN-591)", () => {
  it("workflow: bottom panel defaults to collapsed", () => {
    const state = getBottomPanelDefault("workflow");
    expect(state).toBe("collapsed");
  });

  it("execution: bottom panel auto-expands", () => {
    const state = getBottomPanelDefault("execution");
    expect(state).toBe("expanded");
  });

  it("historical: bottom panel defaults to expanded", () => {
    const state = getBottomPanelDefault("historical");
    expect(state).toBe("expanded");
  });

  it("workflow: bottom panel tabs are Logs, Runs", () => {
    const tabs = getAvailableTabs("workflow", "bottomPanel");
    expect(tabs).toEqual(["Logs", "Runs"]);
  });

  it("execution: bottom panel tabs are Logs, Runs", () => {
    const tabs = getAvailableTabs("execution", "bottomPanel");
    expect(tabs).toEqual(["Logs", "Runs"]);
  });

  it("historical: bottom panel tabs are Logs, Runs, Regressions", () => {
    const tabs = getAvailableTabs("historical", "bottomPanel");
    expect(tabs).toEqual(["Logs", "Runs", "Regressions"]);
  });
});

// ===========================================================================
// 8. Status bar contract per mode
// ===========================================================================

describe("Status bar contract rules (RUN-591)", () => {
  it("workflow: step count format is 'N steps . M edges'", () => {
    const format = getStepCountFormat("workflow");
    expect(format).toBe("steps-and-edges");
  });

  it("execution: step count format is 'X/N steps' (progress)", () => {
    const format = getStepCountFormat("execution");
    expect(format).toBe("progress");
  });

  it("historical: step count format is 'X/N steps' (progress)", () => {
    const format = getStepCountFormat("historical");
    expect(format).toBe("progress");
  });

  it("workflow: status bar metrics are hidden", () => {
    const visibility = getMetricsVisibility("workflow");
    expect(visibility).toBe("hidden");
  });

  it("execution: status bar metrics show elapsed + cost", () => {
    const visibility = getMetricsVisibility("execution");
    expect(visibility).toBe("elapsed-and-cost");
  });

  it("historical: status bar metrics show duration + cost", () => {
    const visibility = getMetricsVisibility("historical");
    expect(visibility).toBe("duration-and-cost");
  });
});

// ===========================================================================
// 9. isEditable helper
// ===========================================================================

describe("isEditable helper (RUN-591)", () => {
  it("is a function", () => {
    expect(isEditable).toBeTypeOf("function");
  });

  it("workflow: editable", () => {
    expect(isEditable("workflow")).toBe(true);
  });

  it("execution: NOT editable", () => {
    expect(isEditable("execution")).toBe(false);
  });

  it("historical: NOT editable", () => {
    expect(isEditable("historical")).toBe(false);
  });

  it("fork-draft: editable (same as workflow)", () => {
    expect(isEditable("fork-draft")).toBe(true);
  });
});

// ===========================================================================
// 10. Edge cases (RUN-591 AC)
// ===========================================================================

describe("Edge cases (RUN-591)", () => {
  it("workflow mode contract has no run overlay data requirement", () => {
    const contract = getContractForMode("workflow");
    // Workflow mode should not require runId or run overlay
    expect(contract.topbar.metricsVisible).toBe(false);
    expect(contract.statusBar.metricsVisibility).toBe("hidden");
  });

  it("historical mode disables ALL editing capabilities", () => {
    expect(isEditable("historical")).toBe(false);
    expect(isDraggable("historical")).toBe(false);
    expect(canCreateConnections("historical")).toBe(false);
    expect(canDeleteNodes("historical")).toBe(false);

    const contract = getContractForMode("historical");
    expect(contract.topbar.nameEditable).toBe(false);
    expect(contract.topbar.saveButton).toBe("hidden");
    expect(contract.inspector.fieldsEditable).toBe(false);
    expect(contract.palette.searchEditable).toBe(false);
  });

  it("fork-draft shares workflow editing rules on the same surface", () => {
    expect(isEditable("fork-draft")).toBe(true);
    expect(isDraggable("fork-draft")).toBe(true);
    expect(canCreateConnections("fork-draft")).toBe(true);
    expect(canDeleteNodes("fork-draft")).toBe(true);

    const contract = getContractForMode("fork-draft");
    expect(contract.topbar.nameEditable).toBe(true);
    expect(contract.inspector.fieldsEditable).toBe(true);
    expect(contract.palette.searchEditable).toBe(true);
  });

  it("fork-draft is a mode transition, not a separate surface (same 4-mode set)", () => {
    // fork-draft must be in the same mode set, confirming it's a mode transition
    expect(WORKFLOW_SURFACE_MODES).toContain("fork-draft");
    expect(WORKFLOW_SURFACE_MODES).toContain("workflow");
    // They share the same surface — same array, same getContractForMode function
  });
});

// ===========================================================================
// 11. Contract reflects run = workflow snapshot + overlay (AC2)
// ===========================================================================

describe("Run is workflow snapshot + overlay (RUN-591 AC2)", () => {
  it("execution contract has all panels from workflow plus overlay-specific properties", () => {
    const wf = getContractForMode("workflow");
    const ex = getContractForMode("execution");

    // Both have the same panel keys (same surface, different mode)
    const wfKeys = Object.keys(wf).sort();
    const exKeys = Object.keys(ex).sort();
    expect(wfKeys).toEqual(exKeys);
  });

  it("execution mode enables metrics that workflow mode hides (overlay data)", () => {
    const wf = getContractForMode("workflow");
    const ex = getContractForMode("execution");

    expect(wf.topbar.metricsVisible).toBe(false);
    expect(ex.topbar.metricsVisible).toBe(true);
  });

  it("historical mode shows final run data (completed overlay)", () => {
    const hist = getContractForMode("historical");
    expect(hist.topbar.metricsVisible).toBe(true);
    expect(hist.topbar.metricsStyle).toBe("static");
    expect(getCostBadgeStyle("historical")).toBe("final");
  });
});
