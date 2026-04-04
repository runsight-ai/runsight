/**
 * RED-TEAM tests for RUN-593: Move workflow YAML, palette, and edit
 * capabilities into WorkflowSurface.
 *
 * RUN-593 wires workflow-only capabilities into the shared surface:
 * YAML editor, palette drag-drop, edit affordances, and mode-driven
 * capability toggling. This ticket does NOT create new components —
 * it wires existing ones into WorkflowSurface and makes them
 * respond to the mode contract.
 *
 * Tests verify:
 * 1. YamlEditor wired in center slot for yaml-capable modes
 * 2. Canvas/YAML tab toggle with mode-driven visibility
 * 3. Palette drag-drop wiring on the center slot
 * 4. Edit affordances (save, name editing, canvas editable) are
 *    mode-driven: enabled for workflow/fork-draft, disabled for
 *    execution/historical
 * 5. Fork-draft reuses the same editing path as workflow mode
 * 6. All capabilities live within WorkflowSurface — no new page
 *
 * Expected failures: WorkflowSurface.tsx currently only renders
 * WorkflowCanvas in center — no YamlEditor, no tab state, no drop
 * handlers, no mode-driven save button state.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const WORKFLOW_SURFACE_PATH = "features/canvas/WorkflowSurface.tsx";

// ===========================================================================
// 1. YamlEditor integration — center slot renders YamlEditor
// ===========================================================================

describe("YamlEditor wired into WorkflowSurface center slot (RUN-593 AC1)", () => {
  it("imports YamlEditor component", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/import.*YamlEditor.*from/);
  });

  it("renders <YamlEditor in JSX", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).toMatch(/<YamlEditor/);
  });

  it("passes workflowId to YamlEditor", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // YamlEditor requires workflowId prop
    expect(source).toMatch(/<YamlEditor[\s\S]*?workflowId/);
  });

  it("renders YamlEditor inside the surface-center slot", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The center slot (data-testid="surface-center") should contain YamlEditor
    // Extract the center slot content and verify YamlEditor is within it
    const centerMatch = source.match(
      /data-testid=["']surface-center["'][\s\S]*?<\/div>/,
    );
    expect(
      centerMatch,
      "Expected surface-center slot to exist",
    ).not.toBeNull();
    expect(
      centerMatch![0],
      "Expected YamlEditor to be rendered inside surface-center slot",
    ).toMatch(/YamlEditor/);
  });
});

// ===========================================================================
// 2. Canvas/YAML tab toggle — active tab state drives center content
// ===========================================================================

describe("Canvas/YAML tab toggle in center slot (RUN-593 AC1)", () => {
  it("manages an active tab state via useState (canvas vs yaml)", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should have useState for the active tab — not just a computed value
    const hasTabState = /useState.*["'](canvas|yaml)["']/.test(source);
    expect(
      hasTabState,
      "Expected useState-based active tab state management in WorkflowSurface",
    ).toBe(true);
  });

  it("conditionally renders WorkflowCanvas OR YamlEditor based on active tab", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should have conditional rendering: when tab is yaml, show YamlEditor;
    // when tab is canvas, show WorkflowCanvas
    // This means both components appear in the source with some conditional
    const hasConditionalRendering =
      (/<WorkflowCanvas/.test(source) && /<YamlEditor/.test(source)) &&
      // And there must be a conditional around at least one of them
      (/activeTab\s*===\s*["']yaml["']/.test(source) ||
       /activeTab\s*===\s*["']canvas["']/.test(source) ||
       /tab\s*===\s*["']yaml["']/.test(source) ||
       /tab\s*===\s*["']canvas["']/.test(source));
    expect(
      hasConditionalRendering,
      "Expected conditional rendering of WorkflowCanvas vs YamlEditor based on active tab",
    ).toBe(true);
  });

  it("hides the toggle in execution mode (canvas-only)", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The toggle visibility should be used to hide/show the tab toggle
    // In execution mode: canvas=true, yaml=false — toggle should be hidden
    // The component should reference toggleVisibility to control tab display
    const usesToggleVisibility =
      /toggleVisibility/.test(source) &&
      (
        /toggleVisibility\.yaml/.test(source) ||
        /toggleVisibility\.canvas/.test(source)
      );
    expect(
      usesToggleVisibility,
      "Expected toggleVisibility to control tab toggle display",
    ).toBe(true);
    // When yaml is not available, force canvas tab — no yaml option rendered
    // The tab state should be constrained by the mode contract
    const constrainsTab =
      /toggleVisibility\.yaml.*activeTab|!toggleVisibility\.yaml/.test(source) ||
      /yaml.*false|yaml.*hidden/.test(source);
    expect(
      constrainsTab,
      "Expected tab state to be constrained when yaml is unavailable",
    ).toBe(true);
  });

  it("passes toggle visibility as a prop to CanvasTopbar for historical mode hiding", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // In historical mode both canvas and yaml are false in toggle visibility —
    // the toggle UI should not render at all.
    // The surface should pass toggleVisibility (or equivalent) as a JSX prop
    // to CanvasTopbar so it can hide/show the toggle.
    // Look for toggleVisibility= or showToggle= directly on the CanvasTopbar JSX
    const passesToggleProp =
      /<CanvasTopbar[^/]*toggleVisibility=/.test(source) ||
      /<CanvasTopbar[^/]*showToggle=/.test(source) ||
      /<CanvasTopbar[^/]*hideToggle=/.test(source);
    expect(
      passesToggleProp,
      "Expected toggleVisibility passed as a JSX prop to CanvasTopbar",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Palette drag-drop wiring — center slot accepts drops
// ===========================================================================

describe("Palette drag-drop wired to center slot (RUN-593 AC3)", () => {
  it("center slot has an onDrop handler", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The surface-center div should have onDrop to accept palette drags
    const centerSlot = source.match(
      /data-testid=["']surface-center["'][^>]*/,
    );
    expect(
      centerSlot,
      "Expected surface-center slot to exist",
    ).not.toBeNull();
    // onDrop must be on the center slot or delegated to its children
    const hasDropHandler =
      /onDrop/.test(source) &&
      /surface-center/.test(source);
    expect(
      hasDropHandler,
      "Expected onDrop handler in the surface-center area",
    ).toBe(true);
  });

  it("center slot has an onDragOver handler to allow drops", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // onDragOver with preventDefault is required for HTML drop to work
    const hasDragOver = /onDragOver/.test(source);
    expect(
      hasDragOver,
      "Expected onDragOver handler for HTML5 drag-and-drop",
    ).toBe(true);
  });

  it("drop handler reads application/runsight-block data type", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const readsBlockData =
      /application\/runsight-block/.test(source) ||
      /runsight-block/.test(source);
    expect(
      readsBlockData,
      "Expected drop handler to read application/runsight-block data",
    ).toBe(true);
  });

  it("drop handler reads application/runsight-soul data type", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const readsSoulData =
      /application\/runsight-soul/.test(source) ||
      /runsight-soul/.test(source);
    expect(
      readsSoulData,
      "Expected drop handler to read application/runsight-soul data",
    ).toBe(true);
  });

  it("drop handler is disabled in read-only modes (execution/historical)", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The drop handler should be gated by the editable state from mode contract
    // When mode is execution or historical, drops should be ignored
    const gatedDrop =
      /isEditable.*onDrop|editable.*onDrop|!.*editable.*return|contract.*canvas.*draggable.*drop/.test(
        source,
      ) ||
      // Or the handler checks the mode before processing
      /mode.*===.*execution|mode.*===.*historical|!.*editable/.test(source);
    expect(
      gatedDrop,
      "Expected drop handler to be gated by editable/draggable mode flag",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Edit affordances are mode-driven
// ===========================================================================

describe("Edit affordances are mode-driven (RUN-593 AC2)", () => {
  it("save button state is derived from mode contract saveButton field", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The topbar save button should use contract.topbar.saveButton
    // or call getSaveButtonState to determine its visibility/variant
    const usesSaveContract =
      /getSaveButtonState/.test(source) ||
      /saveButton/.test(source) &&
        (
          /contract\.topbar\.saveButton/.test(source) ||
          /topbar\.saveButton/.test(source) ||
          /saveButton.*hidden|saveButton.*disabled/.test(source)
        );
    expect(
      usesSaveContract,
      "Expected save button to use mode contract saveButton state",
    ).toBe(true);
  });

  it("passes saveButton visibility state to CanvasTopbar", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // CanvasTopbar should receive the save button state from the mode contract
    const passesSaveToTopbar =
      /<CanvasTopbar[\s\S]*?saveButton|<CanvasTopbar[\s\S]*?saveVisible|<CanvasTopbar[\s\S]*?saveState/.test(
        source,
      );
    expect(
      passesSaveToTopbar,
      "Expected save button state to be passed to CanvasTopbar",
    ).toBe(true);
  });

  it("YamlEditor receives readOnly prop in non-editable modes", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // YamlEditor should get a readOnly flag when mode is execution/historical
    const hasReadOnly =
      /<YamlEditor[\s\S]*?readOnly/.test(source) ||
      // or the editor is simply not rendered in read-only modes
      // (which means there's a conditional on isEditable)
      /isEditable[\s\S]*?YamlEditor/.test(source);
    expect(
      hasReadOnly,
      "Expected YamlEditor to receive readOnly prop or be gated by isEditable",
    ).toBe(true);
  });

  it("canvas receives connectionsAllowed from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const passesConnections =
      /<WorkflowCanvas[\s\S]*?connectionsAllowed|<WorkflowCanvas[\s\S]*?canConnect/.test(
        source,
      ) ||
      /connectionsAllowed/.test(source);
    expect(
      passesConnections,
      "Expected canvas to receive connectionsAllowed from mode contract",
    ).toBe(true);
  });

  it("canvas receives deletionAllowed from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const passesDeletion =
      /<WorkflowCanvas[\s\S]*?deletionAllowed|<WorkflowCanvas[\s\S]*?canDelete/.test(
        source,
      ) ||
      /deletionAllowed/.test(source);
    expect(
      passesDeletion,
      "Expected canvas to receive deletionAllowed from mode contract",
    ).toBe(true);
  });

  it("palette sidebar receives dimmed AND interactive state from mode contract", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // PaletteSidebar should receive dimmed state AND drag-interactivity
    // Current code only applies opacity class — it also needs to disable drag
    const receivesDimmedAndDrag =
      /<PaletteSidebar[\s\S]*?dimmed|<PaletteSidebar[\s\S]*?disabled|<PaletteSidebar[\s\S]*?interactive/.test(
        source,
      );
    expect(
      receivesDimmedAndDrag,
      "Expected PaletteSidebar to receive dimmed/interactive props from mode contract",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Fork-draft reuses workflow editing capabilities
// ===========================================================================

describe("Fork-draft reuses workflow capabilities (RUN-593 AC1 + DoD)", () => {
  it("does NOT have separate fork-draft rendering logic", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // There should be no special-case "fork-draft" JSX branch or separate component
    // fork-draft should flow through the same contract-driven path as workflow
    const forkDraftSpecialCase =
      /mode\s*===\s*["']fork-draft["']\s*\?/.test(source) ||
      /mode\s*===\s*["']fork-draft["']\s*&&/.test(source);
    expect(
      forkDraftSpecialCase,
      "Expected no special-case fork-draft rendering — should use mode contract path",
    ).toBe(false);
  });

  it("fork-draft contract produces the same editing flags as workflow", () => {
    // This is a source-level test of the contract — verify it's consumed correctly
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The surface should use getContractForMode which returns identical editing
    // flags for both workflow and fork-draft. No mode-specific overrides in JSX.
    const usesContract = /getContractForMode\s*\(\s*mode\s*\)/.test(source);
    expect(
      usesContract,
      "Expected WorkflowSurface to use getContractForMode(mode) uniformly",
    ).toBe(true);
    // And there should be no hardcoded mode checks for editing features
    const hardcodedWorkflowCheck =
      /mode\s*===\s*["']workflow["']\s*[?&]/.test(source);
    expect(
      hardcodedWorkflowCheck,
      "Expected no hardcoded 'workflow' mode checks — use contract flags instead",
    ).toBe(false);
  });
});

// ===========================================================================
// 6. No new page-level surface — everything lives in WorkflowSurface
// ===========================================================================

describe("No new page-level workflow surface (RUN-593 AC3)", () => {
  it("does NOT create a WorkflowEditorPage or similar separate page", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Must not import or reference a separate editor page
    expect(source).not.toMatch(
      /import.*from.*WorkflowEditorPage|import.*from.*EditorPage/,
    );
  });

  it("YamlEditor is rendered inside WorkflowSurface, not in a separate route", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // YamlEditor appears in the same file as WorkflowSurface — not a separate page
    const hasYamlEditorInSurface =
      /<YamlEditor/.test(source) && /export\s+(function|const)\s+WorkflowSurface/.test(source);
    expect(
      hasYamlEditorInSurface,
      "Expected YamlEditor to be rendered within WorkflowSurface component",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. Edge cases
// ===========================================================================

describe("Edge cases (RUN-593)", () => {
  it("handles workflow with no blocks — center slot still renders", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // The center slot should render regardless of block count
    // WorkflowCanvas should be rendered even when nodes=[], not conditionally
    // hidden when empty
    const centerAlwaysRenders =
      /data-testid=["']surface-center["']/.test(source) &&
      !(/nodes\.length\s*[>!]=?\s*0[\s\S]*?WorkflowCanvas/.test(source));
    expect(
      centerAlwaysRenders,
      "Expected center slot to always render even with no blocks",
    ).toBe(true);
  });

  it("fork-draft mode allows YAML editing before any run exists", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // In fork-draft mode, the yaml tab should be available (same as workflow)
    // First: YamlEditor must be rendered at all
    expect(source).toMatch(/<YamlEditor/);
    // Second: YamlEditor should NOT require runId — fork-draft can edit before any run
    const yamlRequiresRunId = /<YamlEditor[\s\S]*?runId/.test(source);
    expect(
      yamlRequiresRunId,
      "Expected YamlEditor to NOT require runId — fork-draft can edit YAML without a run",
    ).toBe(false);
  });

  it("execution mode forces canvas tab even if user was on yaml", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // When toggle visibility says yaml=false (execution mode),
    // the active tab should be forced to 'canvas'
    const forcesCanvasTab =
      /toggleVisibility\.yaml\s*===\s*false.*canvas|!toggleVisibility\.yaml.*setActiveTab.*canvas|!toggleVisibility\.yaml.*["']canvas["']/.test(
        source,
      ) ||
      // Or uses an effect/memo to constrain tab to available options
      /useEffect[\s\S]*?toggleVisibility[\s\S]*?activeTab|useMemo[\s\S]*?toggleVisibility/.test(
        source,
      );
    expect(
      forcesCanvasTab,
      "Expected execution mode to force canvas tab when yaml is unavailable",
    ).toBe(true);
  });

  it("dirty state from YamlEditor propagates to save button", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // YamlEditor's onDirtyChange callback should update the surface's dirty state
    // which feeds into the save button via the mode contract
    const propagatesDirty =
      /onDirtyChange/.test(source) &&
      /isDirty|dirty/.test(source) &&
      /setIsDirty|setDirty/.test(source);
    expect(
      propagatesDirty,
      "Expected YamlEditor dirty state to propagate to save button via onDirtyChange",
    ).toBe(true);
  });
});
