import { describe, expect, it } from "vitest";

import {
  WORKFLOW_SURFACE_MODES,
  canCreateConnections,
  canDeleteNodes,
  getActionButton,
  getAvailableTabs,
  getCanvasYamlToggleVisibility,
  getContractForMode,
  getSaveButtonState,
  isDraggable,
  isEditable,
  type WorkflowSurfaceMode,
} from "../surfaceContract";

type ModeSmoke = {
  paletteVisible: boolean;
  inspectorVisible: boolean;
  draggable: boolean;
  action: { label: string; variant: string };
  inspectorTabs: string[];
  bottomPanelTabs: string[];
  dirtySaveState: string;
  cleanSaveState: string;
  yamlVisible: boolean;
};

const expectations: Record<WorkflowSurfaceMode, ModeSmoke> = {
  readonly: {
    paletteVisible: false,
    inspectorVisible: true,
    draggable: false,
    action: { label: "Fork", variant: "primary" },
    inspectorTabs: ["Overview", "Output", "Eval", "Error"],
    bottomPanelTabs: ["Logs", "Runs", "Regressions"],
    dirtySaveState: "hidden",
    cleanSaveState: "hidden",
    yamlVisible: true,
  },
  edit: {
    paletteVisible: true,
    inspectorVisible: false,
    draggable: true,
    action: { label: "Save+Run", variant: "primary" },
    inspectorTabs: ["Overview", "Prompt", "Conditions"],
    bottomPanelTabs: ["Logs", "Runs"],
    dirtySaveState: "enabled",
    cleanSaveState: "disabled",
    yamlVisible: true,
  },
  sim: {
    paletteVisible: true,
    inspectorVisible: true,
    draggable: true,
    action: { label: "Cancel", variant: "danger" },
    inspectorTabs: ["Overview", "Results", "Conditions"],
    bottomPanelTabs: ["Logs", "Runs"],
    dirtySaveState: "hidden",
    cleanSaveState: "hidden",
    yamlVisible: false,
  },
};

describe("workflow surface contract smoke", () => {
  it("exposes only the current public modes", () => {
    expect([...WORKFLOW_SURFACE_MODES].sort()).toEqual(["edit", "readonly", "sim"]);
  });

  it.each(Object.entries(expectations) as Array<[WorkflowSurfaceMode, ModeSmoke]>)(
    "%s keeps the core panel and helper contract",
    (mode, expected) => {
      const contract = getContractForMode(mode);

      expect({
        paletteVisible: contract.palette.visible,
        inspectorVisible: contract.inspectorVisible,
        draggable: isDraggable(mode),
        editable: isEditable(mode),
        connectionsAllowed: canCreateConnections(mode),
        deletionAllowed: canDeleteNodes(mode),
        action: getActionButton(mode),
        inspectorTabs: getAvailableTabs(mode, "inspector"),
        bottomPanelTabs: getAvailableTabs(mode, "bottomPanel"),
        dirtySaveState: getSaveButtonState(mode, true),
        cleanSaveState: getSaveButtonState(mode, false),
        yamlVisible: getCanvasYamlToggleVisibility(mode).yaml,
      }).toEqual({
        paletteVisible: expected.paletteVisible,
        inspectorVisible: expected.inspectorVisible,
        draggable: expected.draggable,
        editable: expected.draggable,
        connectionsAllowed: expected.draggable,
        deletionAllowed: expected.draggable,
        action: expected.action,
        inspectorTabs: expected.inspectorTabs,
        bottomPanelTabs: expected.bottomPanelTabs,
        dirtySaveState: expected.dirtySaveState,
        cleanSaveState: expected.cleanSaveState,
        yamlVisible: expected.yamlVisible,
      });
    },
  );

  it("rejects retired mode names", () => {
    for (const mode of ["workflow", "execution", "historical", "fork-draft"]) {
      expect(() => getContractForMode(mode as WorkflowSurfaceMode)).toThrow();
    }
  });
});
