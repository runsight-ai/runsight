/**
 * RED-TEAM tests for RUN-594: Unify topbar behavior across workflow,
 * execution, historical, and fork-draft states.
 *
 * This ticket requires ONE topbar implementation inside WorkflowSurface
 * that adapts per mode via the contract. Mode-driven: workflow shows
 * base editing controls, execution adds live run behavior, historical
 * shows snapshot/run metadata, fork-draft shows editable workflow behavior.
 *
 * Tests verify:
 * 1. Single topbar component — WorkflowSurface renders ONE topbar for
 *    all modes, not switching between CanvasTopbar and RunDetailHeader
 * 2. Mode-driven props — the topbar receives nameEditable, metrics
 *    visibility, toggle visibility, save button state, and action
 *    button type — all derived from the mode contract
 * 3. Action button per mode — Run in workflow/yaml, Cancel in execution,
 *    Fork in historical
 * 4. Metrics visibility — hidden in workflow, visible in execution/historical
 * 5. Name editability — editable in workflow/fork-draft, static in
 *    execution/historical
 * 6. No duplicate topbar implementations — WorkflowSurface does NOT
 *    conditionally switch between two different header components
 *
 * Expected failures: CanvasTopbar does not yet accept mode-driven
 * topbar contract props (metricsVisible, actionButton, etc.) and
 * RunDetailHeader functionality has not been merged into the unified
 * topbar.
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

const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";
const WORKFLOW_SURFACE_PATH = "features/canvas/WorkflowSurface.tsx";

// ===========================================================================
// 1. Single topbar component for all modes (AC3, DoD)
// ===========================================================================

describe("Single topbar component for all modes (RUN-594 AC3)", () => {
  it("WorkflowSurface renders exactly ONE topbar component in the topbar slot", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Extract what is rendered inside the surface-topbar div.
    // There should be exactly one top-level component, not a conditional
    // switching between CanvasTopbar and RunDetailHeader.
    const topbarSlot = source.match(
      /data-testid=["']surface-topbar["'][\s\S]*?<\/div>/,
    );
    expect(topbarSlot, "Expected surface-topbar slot to exist").not.toBeNull();

    // Count distinct top-level component JSX tags inside the topbar slot
    const componentTags = topbarSlot![0].match(/<[A-Z][A-Za-z]*(?:Topbar|Header)/g) || [];
    expect(
      componentTags.length,
      "Expected exactly ONE topbar/header component rendered in the topbar slot, not multiple",
    ).toBe(1);
  });

  it("WorkflowSurface does NOT import RunDetailHeader", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    expect(source).not.toMatch(/import.*RunDetailHeader.*from/);
  });

  it("WorkflowSurface does NOT conditionally render different topbar components by mode", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should not have mode === "historical" ? <RunDetailHeader : <CanvasTopbar patterns
    const conditionalTopbar =
      /mode\s*===\s*["']historical["'][\s\S]*?<[A-Z].*Header/.test(source) ||
      /mode\s*===\s*["']execution["'][\s\S]*?<[A-Z].*Header/.test(source);
    expect(
      conditionalTopbar,
      "Expected no conditional rendering of different header components by mode",
    ).toBe(false);
  });
});

// ===========================================================================
// 2. CanvasTopbar accepts mode-driven contract props (AC1, AC2, DoD)
// ===========================================================================

describe("CanvasTopbar accepts mode-driven contract props (RUN-594 AC1 + AC2)", () => {
  it("CanvasTopbar interface declares a metricsVisible prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/metricsVisible\s*[?:]?\s*:\s*boolean/);
  });

  it("CanvasTopbar interface declares a metricsStyle prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/metricsStyle\s*[?:]?\s*:\s*["']live["']\s*\|\s*["']static["']\s*\|\s*["']none["']/);
  });

  it("CanvasTopbar interface declares an actionButton prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // actionButton should describe label + variant for the primary action
    const hasActionButton =
      /actionButton\s*[?:]?\s*:\s*\{/.test(source) ||
      /actionButton\s*[?:]?\s*:.*label.*variant/.test(source);
    expect(
      hasActionButton,
      "Expected CanvasTopbar to declare an actionButton prop with label and variant",
    ).toBe(true);
  });

  it("CanvasTopbar interface declares a nameEditable prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/nameEditable\s*[?:]?\s*:\s*boolean/);
  });

  it("CanvasTopbar interface declares a saveButton state prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // saveButton should accept: "ghost" | "primary" | "disabled" | "hidden"
    const hasSaveButton =
      /saveButton\s*[?:]?\s*:\s*["']ghost["']/.test(source) ||
      /saveButton\s*[?:]?\s*:\s*string/.test(source);
    expect(
      hasSaveButton,
      "Expected CanvasTopbar to declare a saveButton state prop",
    ).toBe(true);
  });

  it("CanvasTopbar interface declares a toggleVisibility prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/toggleVisibility\s*[?:]?\s*:/);
  });
});

// ===========================================================================
// 3. Action button adapts per mode (AC2)
// ===========================================================================

describe("Action button adapts per mode (RUN-594 AC2)", () => {
  it("CanvasTopbar renders the action button using the actionButton prop, not hardcoded RunButton", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The topbar should render its primary action from the actionButton prop
    // rather than always rendering a hardcoded <RunButton>
    // It should use actionButton.label and actionButton.variant
    const usesActionButtonProp =
      /actionButton\.label/.test(source) ||
      /actionButton\.variant/.test(source);
    expect(
      usesActionButtonProp,
      "Expected CanvasTopbar to render action button from actionButton prop, not hardcoded",
    ).toBe(true);
  });

  it("WorkflowSurface passes actionButton derived from getActionButton to topbar", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should call getActionButton(mode) and pass result to the topbar component
    const passesActionButton =
      /getActionButton/.test(source) &&
      /actionButton/.test(source);
    expect(
      passesActionButton,
      "Expected WorkflowSurface to derive actionButton from getActionButton and pass to topbar",
    ).toBe(true);
  });

  it("CanvasTopbar does NOT hardcode RunButton as the sole primary action", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The topbar should render the action button dynamically from the
    // actionButton prop (label + variant), not hardcode a single <RunButton>.
    // "Cancel" and "Fork" are actionButton.label values passed by
    // WorkflowSurface, so they won't appear literally in the topbar source.
    // Instead, verify the topbar renders the actionButton prop dynamically.
    const rendersActionButtonDynamically =
      /actionButton\.label/.test(source) ||
      /\{actionButton\.label\}/.test(source) ||
      /actionButton\?\.label/.test(source);
    expect(
      rendersActionButtonDynamically,
      "Expected CanvasTopbar to render actionButton.label dynamically, not hardcode RunButton",
    ).toBe(true);
  });

  it("execution mode action button has danger variant for Cancel", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The topbar should render a danger-styled button when actionButton.variant is "danger"
    const supportsDangerVariant =
      /variant.*danger|danger.*variant/.test(source) ||
      /actionButton\.variant/.test(source);
    expect(
      supportsDangerVariant,
      "Expected CanvasTopbar to support danger variant for execution mode Cancel button",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Metrics visibility adapts per mode (AC1, AC2)
// ===========================================================================

describe("Metrics visibility adapts per mode (RUN-594 AC1 + AC2)", () => {
  it("CanvasTopbar conditionally renders metrics based on metricsVisible prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Metrics (cost, tokens, duration) should be gated by metricsVisible prop
    const gatedByProp =
      /metricsVisible/.test(source) &&
      (
        /metricsVisible\s*&&/.test(source) ||
        /metricsVisible\s*\?/.test(source) ||
        /!metricsVisible/.test(source)
      );
    expect(
      gatedByProp,
      "Expected metrics rendering to be gated by metricsVisible prop",
    ).toBe(true);
  });

  it("CanvasTopbar renders live metrics style distinct from static style", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // When metricsStyle is "live" vs "static", the rendering should differ
    // (e.g., live shows streaming updates, static shows final snapshot values)
    const differentiatesStyle =
      /metricsStyle\s*===\s*["']live["']/.test(source) ||
      /metricsStyle\s*===\s*["']static["']/.test(source);
    expect(
      differentiatesStyle,
      "Expected CanvasTopbar to differentiate between live and static metrics styles",
    ).toBe(true);
  });

  it("WorkflowSurface passes metricsVisible from topbar contract to the topbar", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // Should pass contract.topbar.metricsVisible or metricsVisible={topbar.metricsVisible}
    const passesMetrics =
      /metricsVisible={/.test(source) ||
      /metricsVisible=\{topbar\.metricsVisible/.test(source) ||
      /metricsVisible=\{contract\.topbar\.metricsVisible/.test(source);
    expect(
      passesMetrics,
      "Expected WorkflowSurface to pass metricsVisible to the topbar component",
    ).toBe(true);
  });

  it("WorkflowSurface passes metricsStyle from topbar contract to the topbar", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const passesStyle =
      /metricsStyle={/.test(source) ||
      /metricsStyle=\{topbar\.metricsStyle/.test(source);
    expect(
      passesStyle,
      "Expected WorkflowSurface to pass metricsStyle to the topbar component",
    ).toBe(true);
  });

  it("historical mode shows run metadata (cost, tokens, duration) in the topbar", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The topbar must show run metadata fields when metricsVisible is true
    // and metricsStyle is "static" — these are the fields from RunDetailHeader
    // (total_cost_usd, total_tokens, duration)
    const showsRunMetadata =
      /cost/.test(source) &&
      /token/i.test(source) &&
      /duration/i.test(source);
    expect(
      showsRunMetadata,
      "Expected unified topbar to show cost, tokens, and duration for historical mode",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Name editability adapts per mode (AC1, AC2)
// ===========================================================================

describe("Name editability adapts per mode (RUN-594 AC1 + AC2)", () => {
  it("CanvasTopbar uses nameEditable prop to gate inline name editing", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The name editing behavior (clicking to edit, input field) should be
    // gated by the nameEditable prop, not always enabled
    const gatedByProp =
      /nameEditable/.test(source) &&
      (
        /nameEditable\s*&&/.test(source) ||
        /nameEditable\s*\?/.test(source) ||
        /!nameEditable/.test(source) ||
        /nameEditable.*startEditing|nameEditable.*onClick/.test(source)
      );
    expect(
      gatedByProp,
      "Expected name editing to be gated by nameEditable prop",
    ).toBe(true);
  });

  it("CanvasTopbar renders static (non-editable) name when nameEditable is false", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // When nameEditable is false (execution/historical), the name should
    // render as static text without click-to-edit behavior
    const hasStaticNamePath =
      /nameEditable.*false|!nameEditable/.test(source) ||
      /nameEditable[\s\S]*?cursor-pointer|nameEditable[\s\S]*?onClick/.test(source);
    expect(
      hasStaticNamePath,
      "Expected CanvasTopbar to have a static name rendering path when nameEditable is false",
    ).toBe(true);
  });

  it("historical mode name links to the workflow instead of being editable", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // In historical mode, the name should link to the workflow (like RunDetailHeader does)
    // rather than being an editable inline input
    const hasWorkflowLink =
      /Link.*workflow|href.*workflow|navigate.*workflow/.test(source) ||
      /workflowLink|openWorkflow/.test(source);
    expect(
      hasWorkflowLink,
      "Expected historical mode name to link to the workflow, not be editable",
    ).toBe(true);
  });
});

// ===========================================================================
// 6. Save button adapts per mode (AC1, DoD)
// ===========================================================================

describe("Save button adapts per mode (RUN-594 AC1 + DoD)", () => {
  it("CanvasTopbar hides save button when saveButton state is 'hidden'", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The save button should not render at all when the state is "hidden"
    // (historical mode)
    const hidesOnHidden =
      /saveButton.*hidden|saveButton.*!==.*hidden/.test(source) ||
      /saveButton\s*!==\s*["']hidden["']/.test(source);
    expect(
      hidesOnHidden,
      "Expected save button to be hidden when saveButton state is 'hidden'",
    ).toBe(true);
  });

  it("CanvasTopbar disables save button when saveButton state is 'disabled'", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // In execution mode, save is "disabled" — visible but not clickable
    const disablesOnDisabled =
      /saveButton.*disabled|disabled.*saveButton/.test(source) ||
      /saveButton\s*===\s*["']disabled["']/.test(source);
    expect(
      disablesOnDisabled,
      "Expected save button to be disabled when saveButton state is 'disabled'",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. No duplicate topbar implementations remain active (Visual AC)
// ===========================================================================

describe("No duplicate topbar implementations (RUN-594 Visual AC)", () => {
  it("RunDetailHeader is NOT imported anywhere in the active run-viewing route", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // WorkflowSurface should NOT use RunDetailHeader — all its functionality
    // should be merged into the unified topbar
    expect(source).not.toMatch(/import.*RunDetailHeader/);
    expect(source).not.toMatch(/<RunDetailHeader/);
  });

  it("CanvasTopbar subsumes RunDetailHeader functionality (dynamic action button, status badge)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The unified topbar must include capabilities from RunDetailHeader:
    // - Dynamic action button rendering (fork is delivered via actionButton.label
    //   from WorkflowSurface, not hardcoded in the topbar)
    // - Status badge (for execution/historical)
    const rendersActionButtonDynamically =
      /actionButton\.label/.test(source) ||
      /actionButton\.variant/.test(source);
    const hasStatusBadge = /status.*badge|statusBadge|StatusBadge|run.*status/i.test(source);
    expect(
      rendersActionButtonDynamically,
      "Expected unified topbar to render actionButton dynamically (fork delivered via actionButton.label)",
    ).toBe(true);
    expect(
      hasStatusBadge,
      "Expected unified topbar to include run status badge from RunDetailHeader",
    ).toBe(true);
  });

  it("mode changes affect visibility and behavior within the same topbar component", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The topbar should reference mode-related props that control what is visible
    // rather than being a fixed layout. It should have conditional rendering
    // based on metricsVisible, actionButton, saveButton, nameEditable, etc.
    const modeProps = [
      /metricsVisible/,
      /actionButton/,
      /saveButton/,
      /nameEditable/,
    ];
    const modePropsPresent = modeProps.filter((r) => r.test(source)).length;
    expect(
      modePropsPresent,
      "Expected at least 4 mode-driven props used in CanvasTopbar for unified behavior",
    ).toBeGreaterThanOrEqual(4);
  });
});

// ===========================================================================
// 8. Edge cases (DoD)
// ===========================================================================

describe("Edge cases (RUN-594 DoD)", () => {
  it("execution mode transition back to workflow preserves the same topbar component", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);
    // When transitioning from execution to workflow (run terminal state),
    // the same topbar component should stay mounted — no unmount/remount.
    // This means the topbar is NOT conditionally rendered by mode type.
    // It should be the same JSX element receiving different props.
    const topbarSlot = source.match(
      /data-testid=["']surface-topbar["'][\s\S]*?<\/div>/,
    );
    expect(topbarSlot).not.toBeNull();
    // Should not have mode-based conditional rendering of different components
    const hasConditionalTopbar =
      /mode\s*===[\s\S]*?\?[\s\S]*?<[A-Z][\s\S]*?:[\s\S]*?<[A-Z]/.test(
        topbarSlot![0],
      );
    expect(
      hasConditionalTopbar,
      "Expected no conditional component switching in topbar slot — same component for all modes",
    ).toBe(false);
  });

  it("fork-draft mode shows editable name in the topbar", () => {
    // fork-draft mode should have nameEditable: true in the contract
    // and the topbar should receive it — verified by checking WorkflowSurface
    // passes nameEditable derived from contract
    const source = readSource(WORKFLOW_SURFACE_PATH);
    const passesNameEditable =
      /nameEditable=\{/.test(source) ||
      /nameEditable={nameEditable}/.test(source) ||
      /nameEditable={topbar\.nameEditable}/.test(source);
    expect(
      passesNameEditable,
      "Expected WorkflowSurface to pass nameEditable to topbar for fork-draft editability",
    ).toBe(true);
  });

  it("historical mode with unavailable snapshot shows appropriate state in topbar", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // When viewing a historical run whose snapshot is unavailable,
    // the Fork button should be disabled or show a tooltip
    const handlesUnavailableSnapshot =
      /snapshot.*unavailable|!.*snapshot|!.*commitSha|!.*commit_sha|forkDisabled/i.test(source);
    expect(
      handlesUnavailableSnapshot,
      "Expected topbar to handle unavailable snapshot state in historical mode",
    ).toBe(true);
  });
});
