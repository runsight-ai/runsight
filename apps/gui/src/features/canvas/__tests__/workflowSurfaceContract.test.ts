/**
 * RED-TEAM tests for RUN-649: Collapse contract to 3-state model (readonly/edit/sim).
 *
 * The contract currently has 4 modes: workflow, execution, historical, fork-draft.
 * It must become exactly 3 modes: readonly, edit, sim.
 *
 * These tests verify:
 * 1. WORKFLOW_SURFACE_MODES has exactly 3 values: readonly, edit, sim
 * 2. Per-mode contract values match the 3-state specification
 * 3. All helper functions return correct values for the new mode names
 * 4. inspectorVisible field exists in the contract
 * 5. Old mode names (workflow, execution, historical, fork-draft) are gone
 * 6. Action buttons: Fork (readonly), Save+Run (edit), Cancel (sim)
 * 7. Tab configuration per mode
 * 8. getSaveButtonState works with new mode names
 *
 * Expected failures: the contract still has the old 4-mode model.
 */

import { describe, it, expect } from "vitest";

import {
  WORKFLOW_SURFACE_MODES,
  getContractForMode,
  isEditable,
  isDraggable,
  canCreateConnections,
  canDeleteNodes,
  getAvailableTabs,
  getActionButton,
  getSaveButtonState,
} from "../workflowSurfaceContract";

// ===========================================================================
// 1. WORKFLOW_SURFACE_MODES — exactly 3 modes
// ===========================================================================

describe("WORKFLOW_SURFACE_MODES has exactly 3 modes (RUN-649 AC5)", () => {
  it("is an array with exactly 3 modes", () => {
    expect(Array.isArray(WORKFLOW_SURFACE_MODES)).toBe(true);
    expect(WORKFLOW_SURFACE_MODES).toHaveLength(3);
  });

  it("includes 'edit' mode", () => {
    expect(WORKFLOW_SURFACE_MODES).toContain("edit");
  });

  it("includes 'sim' mode", () => {
    expect(WORKFLOW_SURFACE_MODES).toContain("sim");
  });

  it("includes 'readonly' mode", () => {
    expect(WORKFLOW_SURFACE_MODES).toContain("readonly");
  });

  it("does NOT include 'workflow' (old mode name)", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("workflow");
  });

  it("does NOT include 'execution' (old mode name)", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("execution");
  });

  it("does NOT include 'historical' (old mode name)", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("historical");
  });

  it("does NOT include 'fork-draft' (old mode name)", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("fork-draft");
  });

  it("contains no duplicate modes", () => {
    const unique = new Set(WORKFLOW_SURFACE_MODES);
    expect(unique.size).toBe(WORKFLOW_SURFACE_MODES.length);
  });
});

// ===========================================================================
// 2. edit mode — full contract
// ===========================================================================

describe("getContractForMode('edit') (RUN-649 AC1)", () => {
  it("returns a contract object with all required panels", () => {
    const contract = getContractForMode("edit" as any);
    expect(contract).toBeDefined();
    expect(contract).toHaveProperty("topbar");
    expect(contract).toHaveProperty("palette");
    expect(contract).toHaveProperty("canvas");
    expect(contract).toHaveProperty("inspector");
    expect(contract).toHaveProperty("bottomPanel");
    expect(contract).toHaveProperty("statusBar");
  });

  it("palette: visible and not dimmed", () => {
    const contract = getContractForMode("edit" as any);
    expect(contract.palette.visible).toBe(true);
    expect(contract.palette.dimmed).toBe(false);
  });

  it("canvas: draggable, connections allowed, deletion allowed", () => {
    const contract = getContractForMode("edit" as any);
    expect(contract.canvas.draggable).toBe(true);
    expect(contract.canvas.connectionsAllowed).toBe(true);
    expect(contract.canvas.deletionAllowed).toBe(true);
  });

  it("inspectorVisible is false (inspector hidden in edit mode)", () => {
    const contract = getContractForMode("edit" as any);
    expect(contract).toHaveProperty("inspectorVisible");
    expect((contract as any).inspectorVisible).toBe(false);
  });

  it("action button is Save+Run", () => {
    const result = getActionButton("edit" as any);
    expect(result.label).toBe("Save+Run");
  });
});

// ===========================================================================
// 3. sim mode — full contract
// ===========================================================================

describe("getContractForMode('sim') (RUN-649 AC2)", () => {
  it("returns a contract object with all required panels", () => {
    const contract = getContractForMode("sim" as any);
    expect(contract).toBeDefined();
    expect(contract).toHaveProperty("topbar");
    expect(contract).toHaveProperty("palette");
    expect(contract).toHaveProperty("canvas");
    expect(contract).toHaveProperty("inspector");
    expect(contract).toHaveProperty("bottomPanel");
    expect(contract).toHaveProperty("statusBar");
  });

  it("palette: visible and NOT dimmed (interactive)", () => {
    const contract = getContractForMode("sim" as any);
    expect(contract.palette.visible).toBe(true);
    expect(contract.palette.dimmed).toBe(false);
  });

  it("canvas: editable (draggable, connections allowed, deletion allowed)", () => {
    const contract = getContractForMode("sim" as any);
    expect(contract.canvas.draggable).toBe(true);
    expect(contract.canvas.connectionsAllowed).toBe(true);
    expect(contract.canvas.deletionAllowed).toBe(true);
  });

  it("inspectorVisible is true (inspector present in sim mode)", () => {
    const contract = getContractForMode("sim" as any);
    expect(contract).toHaveProperty("inspectorVisible");
    expect((contract as any).inspectorVisible).toBe(true);
  });

  it("inspector trigger is single-click", () => {
    const contract = getContractForMode("sim" as any);
    expect(contract.inspector.trigger).toBe("single-click");
  });

  it("action button is Cancel", () => {
    const result = getActionButton("sim" as any);
    expect(result.label).toBe("Cancel");
    expect(result.variant).toBe("danger");
  });
});

// ===========================================================================
// 4. readonly mode — full contract
// ===========================================================================

describe("getContractForMode('readonly') (RUN-649 AC3)", () => {
  it("returns a contract object with all required panels", () => {
    const contract = getContractForMode("readonly" as any);
    expect(contract).toBeDefined();
    expect(contract).toHaveProperty("topbar");
    expect(contract).toHaveProperty("palette");
    expect(contract).toHaveProperty("canvas");
    expect(contract).toHaveProperty("inspector");
    expect(contract).toHaveProperty("bottomPanel");
    expect(contract).toHaveProperty("statusBar");
  });

  it("palette: HIDDEN (visible is false)", () => {
    const contract = getContractForMode("readonly" as any);
    expect(contract.palette.visible).toBe(false);
  });

  it("canvas: read-only (not draggable, no connections, no deletion)", () => {
    const contract = getContractForMode("readonly" as any);
    expect(contract.canvas.draggable).toBe(false);
    expect(contract.canvas.connectionsAllowed).toBe(false);
    expect(contract.canvas.deletionAllowed).toBe(false);
  });

  it("inspectorVisible is true (inspector present in readonly mode)", () => {
    const contract = getContractForMode("readonly" as any);
    expect(contract).toHaveProperty("inspectorVisible");
    expect((contract as any).inspectorVisible).toBe(true);
  });

  it("inspector trigger is single-click", () => {
    const contract = getContractForMode("readonly" as any);
    expect(contract.inspector.trigger).toBe("single-click");
  });

  it("action button is Fork", () => {
    const result = getActionButton("readonly" as any);
    expect(result.label).toBe("Fork");
    expect(result.variant).toBe("primary");
  });
});

// ===========================================================================
// 5. Helper functions with new mode names
// ===========================================================================

describe("Helper functions updated for 3-state model (RUN-649 AC6)", () => {
  // isEditable
  it("isEditable('edit') returns true", () => {
    expect(isEditable("edit" as any)).toBe(true);
  });

  it("isEditable('sim') returns true (sim is editable)", () => {
    expect(isEditable("sim" as any)).toBe(true);
  });

  it("isEditable('readonly') returns false", () => {
    expect(isEditable("readonly" as any)).toBe(false);
  });

  // isDraggable
  it("isDraggable('edit') returns true", () => {
    expect(isDraggable("edit" as any)).toBe(true);
  });

  it("isDraggable('sim') returns true (sim canvas is editable)", () => {
    expect(isDraggable("sim" as any)).toBe(true);
  });

  it("isDraggable('readonly') returns false", () => {
    expect(isDraggable("readonly" as any)).toBe(false);
  });

  // canCreateConnections
  it("canCreateConnections('edit') returns true", () => {
    expect(canCreateConnections("edit" as any)).toBe(true);
  });

  it("canCreateConnections('sim') returns true", () => {
    expect(canCreateConnections("sim" as any)).toBe(true);
  });

  it("canCreateConnections('readonly') returns false", () => {
    expect(canCreateConnections("readonly" as any)).toBe(false);
  });

  // canDeleteNodes
  it("canDeleteNodes('edit') returns true", () => {
    expect(canDeleteNodes("edit" as any)).toBe(true);
  });

  it("canDeleteNodes('sim') returns true", () => {
    expect(canDeleteNodes("sim" as any)).toBe(true);
  });

  it("canDeleteNodes('readonly') returns false", () => {
    expect(canDeleteNodes("readonly" as any)).toBe(false);
  });
});

// ===========================================================================
// 6. Tab configuration per mode
// ===========================================================================

describe("getAvailableTabs per mode (RUN-649 AC6)", () => {
  it("edit: inspector tabs are Overview, Prompt, Conditions", () => {
    const tabs = getAvailableTabs("edit" as any, "inspector");
    expect(tabs).toEqual(["Overview", "Prompt", "Conditions"]);
  });

  it("edit: bottomPanel tabs are Logs, Runs", () => {
    const tabs = getAvailableTabs("edit" as any, "bottomPanel");
    expect(tabs).toEqual(["Logs", "Runs"]);
  });

  it("sim: inspector tabs are Overview, Results, Conditions", () => {
    const tabs = getAvailableTabs("sim" as any, "inspector");
    expect(tabs).toEqual(["Overview", "Results", "Conditions"]);
  });

  it("sim: bottomPanel tabs are Logs, Runs", () => {
    const tabs = getAvailableTabs("sim" as any, "bottomPanel");
    expect(tabs).toEqual(["Logs", "Runs"]);
  });

  it("readonly: inspector tabs are Overview, Output, Eval, Error", () => {
    const tabs = getAvailableTabs("readonly" as any, "inspector");
    expect(tabs).toEqual(["Overview", "Output", "Eval", "Error"]);
  });

  it("readonly: bottomPanel tabs are Logs, Runs, Regressions", () => {
    const tabs = getAvailableTabs("readonly" as any, "bottomPanel");
    expect(tabs).toEqual(["Logs", "Runs", "Regressions"]);
  });
});

// ===========================================================================
// 7. Action buttons
// ===========================================================================

describe("getActionButton for 3-state model (RUN-649 AC1-3)", () => {
  it("edit: returns Save+Run action", () => {
    const result = getActionButton("edit" as any);
    expect(result.label).toBe("Save+Run");
    expect(result.variant).toBe("primary");
  });

  it("sim: returns Cancel action with danger variant", () => {
    const result = getActionButton("sim" as any);
    expect(result.label).toBe("Cancel");
    expect(result.variant).toBe("danger");
  });

  it("readonly: returns Fork action with primary variant", () => {
    const result = getActionButton("readonly" as any);
    expect(result.label).toBe("Fork");
    expect(result.variant).toBe("primary");
  });
});

// ===========================================================================
// 8. getSaveButtonState with new mode names
// ===========================================================================

describe("getSaveButtonState with 3-state model (RUN-649)", () => {
  it("edit + dirty: returns enabled state", () => {
    expect(getSaveButtonState("edit" as any, true)).toBe("enabled");
  });

  it("edit + clean: returns disabled state", () => {
    expect(getSaveButtonState("edit" as any, false)).toBe("disabled");
  });

  it("readonly: returns hidden regardless of dirty flag", () => {
    expect(getSaveButtonState("readonly" as any, true)).toBe("hidden");
    expect(getSaveButtonState("readonly" as any, false)).toBe("hidden");
  });

  it("sim: returns hidden (no save during simulation)", () => {
    expect(getSaveButtonState("sim" as any, true)).toBe("hidden");
    expect(getSaveButtonState("sim" as any, false)).toBe("hidden");
  });
});

// ===========================================================================
// 9. inspectorVisible field on the contract
// ===========================================================================

describe("inspectorVisible field in PanelContract (RUN-649 AC1-3)", () => {
  it("edit mode: inspectorVisible is false", () => {
    const contract = getContractForMode("edit" as any);
    expect((contract as any).inspectorVisible).toBe(false);
  });

  it("sim mode: inspectorVisible is true", () => {
    const contract = getContractForMode("sim" as any);
    expect((contract as any).inspectorVisible).toBe(true);
  });

  it("readonly mode: inspectorVisible is true", () => {
    const contract = getContractForMode("readonly" as any);
    expect((contract as any).inspectorVisible).toBe(true);
  });
});

// ===========================================================================
// 10. Old mode names must not exist
// ===========================================================================

describe("Old mode names are removed (RUN-649 AC4)", () => {
  it("'fork-draft' is not in WORKFLOW_SURFACE_MODES", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("fork-draft");
  });

  it("'execution' is not in WORKFLOW_SURFACE_MODES", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("execution");
  });

  it("'historical' is not in WORKFLOW_SURFACE_MODES", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("historical");
  });

  it("'workflow' is not in WORKFLOW_SURFACE_MODES", () => {
    expect(WORKFLOW_SURFACE_MODES).not.toContain("workflow");
  });

  it("getContractForMode with old mode name 'workflow' throws or returns undefined", () => {
    expect(() => getContractForMode("workflow" as any)).toThrow();
  });

  it("getContractForMode with old mode name 'execution' throws or returns undefined", () => {
    expect(() => getContractForMode("execution" as any)).toThrow();
  });

  it("getContractForMode with old mode name 'historical' throws or returns undefined", () => {
    expect(() => getContractForMode("historical" as any)).toThrow();
  });

  it("getContractForMode with old mode name 'fork-draft' throws or returns undefined", () => {
    expect(() => getContractForMode("fork-draft" as any)).toThrow();
  });
});
