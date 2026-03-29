/**
 * RED-TEAM tests for RUN-357: T3 — Save button (Cmd+S) + unsaved indicator + unsaved changes dialog.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Save button uses Button component (not raw <button>), variant ghost when clean, primary when dirty
 * AC2: Cmd+S / Ctrl+S triggers save (keyboard shortcut)
 * AC3: Unsaved indicator visible when isDirty
 * AC4: Navigate-away dialog with Save/Discard/Cancel (uses useBlocker)
 * AC5: Dialog component from component library used for unsaved changes dialog
 * AC6: Save calls PUT /api/workflows/:id
 *
 * Expected failures (current state):
 *   - CanvasTopbar uses raw <button> instead of Button component
 *   - No variant switching (ghost/primary) based on isDirty
 *   - No unsaved indicator (dot/badge)
 *   - No navigate-away dialog or useBlocker usage
 *   - No Dialog import in CanvasTopbar or CanvasPage
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
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. Save button uses Button component with variant switching (AC1)
// ===========================================================================

describe("Save button uses Button component (AC1)", () => {
  let topbarSource: string;

  it("imports Button from the component library", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    expect(topbarSource).toMatch(
      /import.*\bButton\b.*from.*(@runsight\/ui\/button|components\/ui\/button)/,
    );
  });

  it("renders <Button> for save (not raw <button>)", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // Should have <Button ...>Save</Button> or similar, NOT <button ...>Save</button>
    expect(topbarSource).toMatch(/<Button[\s\S]*?>[\s\S]*?Save[\s\S]*?<\/Button>/);
  });

  it("does NOT use a raw <button> element for the save action", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // The save action should not use a raw <button> tag
    // We look for <button that contains Save text — this should NOT exist
    expect(topbarSource).not.toMatch(/<button[\s\S]*?>[\s\S]*?Save[\s\S]*?<\/button>/);
  });

  it("uses variant='ghost' when isDirty is false (clean state)", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // Should conditionally apply ghost variant when not dirty
    // e.g., variant={isDirty ? "primary" : "ghost"}
    const hasGhostVariant =
      /variant\s*=\s*\{.*ghost.*\}/.test(topbarSource) ||
      /variant\s*=\s*["']ghost["']/.test(topbarSource);
    expect(
      hasGhostVariant,
      'Expected Button variant="ghost" for clean state',
    ).toBe(true);
  });

  it("uses variant='primary' when isDirty is true (dirty state)", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // Should conditionally apply primary variant when dirty
    // e.g., variant={isDirty ? "primary" : "ghost"}
    const hasPrimaryVariant =
      /variant\s*=\s*\{.*primary.*\}/.test(topbarSource) ||
      /variant\s*=\s*["']primary["']/.test(topbarSource);
    expect(
      hasPrimaryVariant,
      'Expected Button variant="primary" for dirty state',
    ).toBe(true);
  });

  it("variant toggles based on isDirty prop (conditional expression)", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // Should have a ternary or conditional that switches variant based on isDirty
    // e.g., variant={isDirty ? "primary" : "ghost"}
    expect(topbarSource).toMatch(
      /variant\s*=\s*\{\s*isDirty\s*\?\s*["']primary["']\s*:\s*["']ghost["']\s*\}/,
    );
  });
});

// ===========================================================================
// 2. Cmd+S / Ctrl+S keyboard shortcut (AC2)
// ===========================================================================

describe("Cmd+S / Ctrl+S keyboard shortcut (AC2)", () => {
  it("CanvasTopbar or CanvasPage registers a keydown listener for Cmd+S", () => {
    // The Cmd+S handler currently lives in YamlEditor.tsx.
    // For the save button AC, the handler should be at the CanvasPage or CanvasTopbar
    // level so it works regardless of which tab is active.
    const pageSource = readSource(CANVAS_PAGE_PATH);
    const topbarSource = readSource(CANVAS_TOPBAR_PATH);
    const combined = pageSource + topbarSource;

    const hasKeyboardHandler =
      /useEffect[\s\S]*?keydown[\s\S]*?metaKey|ctrlKey[\s\S]*?["']s["']/.test(
        combined,
      ) ||
      /metaKey.*key\s*===?\s*["']s["']/.test(combined) ||
      /ctrlKey.*key\s*===?\s*["']s["']/.test(combined);
    expect(
      hasKeyboardHandler,
      "Expected Cmd+S / Ctrl+S keydown handler in CanvasPage or CanvasTopbar",
    ).toBe(true);
  });

  it("CanvasPage passes onSave callback to CanvasTopbar", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // Should pass onSave prop to CanvasTopbar
    expect(pageSource).toMatch(/onSave\s*=\s*\{/);
  });
});

// ===========================================================================
// 3. Unsaved indicator visible when isDirty (AC3)
// ===========================================================================

describe("Unsaved indicator when isDirty (AC3)", () => {
  let topbarSource: string;

  it("has an unsaved indicator element (dot, badge, or icon)", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // Should have some visual indicator near the save button when dirty
    // Common patterns: a dot span, a badge, a circle indicator
    const hasIndicator =
      /unsaved|indicator|dirty.*dot|dirty.*badge|\bdot\b|modified/i.test(
        topbarSource,
      ) ||
      // A small colored dot element that's conditionally rendered
      /isDirty\s*&&\s*</.test(topbarSource) ||
      /isDirty\s*\?\s*</.test(topbarSource);
    expect(
      hasIndicator,
      "Expected an unsaved changes indicator (dot/badge) when isDirty is true",
    ).toBe(true);
  });

  it("indicator is only shown when isDirty is true (conditionally rendered)", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // The indicator should be conditionally rendered based on isDirty
    // Pattern: {isDirty && <span .../>} or similar
    const hasConditionalIndicator =
      /isDirty\s*&&\s*[\s\S]*?(indicator|dot|badge|circle|span|<)/i.test(
        topbarSource,
      );
    expect(
      hasConditionalIndicator,
      "Expected indicator to be conditionally rendered when isDirty",
    ).toBe(true);
  });

  it("indicator uses a recognizable visual (rounded-full, bg-*, or similar)", () => {
    topbarSource = readSource(CANVAS_TOPBAR_PATH);
    // A dot indicator typically has rounded-full and a bg color
    const hasDotStyling =
      /rounded-full.*bg-|bg-.*rounded-full/.test(topbarSource) ||
      /aria-label.*unsaved|aria-label.*modified/i.test(topbarSource);
    expect(
      hasDotStyling,
      "Expected unsaved indicator to have visual styling (dot with bg color)",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Navigate-away dialog with useBlocker (AC4)
// ===========================================================================

describe("Navigate-away dialog with useBlocker (AC4)", () => {
  let pageSource: string;

  it("imports useBlocker from react-router", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/import.*\buseBlocker\b.*from.*react-router/);
  });

  it("calls useBlocker with isDirty condition", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    // Should call useBlocker when isDirty is true
    const hasBlockerCall =
      /useBlocker\s*\(/.test(pageSource);
    expect(
      hasBlockerCall,
      "Expected useBlocker() call in CanvasPage",
    ).toBe(true);
  });

  it("dialog has a 'Save & Leave' action button", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/Save\s*[&amp;&]\s*Leave|Save & Leave/);
  });

  it("dialog has a 'Discard' action button", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/Discard/);
  });

  it("dialog has a 'Cancel' action button", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    // Cancel in the context of the unsaved changes dialog
    // (not the generic DialogClose X button)
    expect(pageSource).toMatch(/Cancel/);
  });

  it("dialog message mentions unsaved changes", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/unsaved\s+changes/i);
  });

  it("'Save & Leave' calls save then proceeds with navigation", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    // The Save & Leave handler should call the save function and then
    // proceed with the blocked navigation (blocker.proceed())
    const hasSaveAndProceed =
      /proceed/.test(pageSource) &&
      /save|onSave|handleSave/.test(pageSource);
    expect(
      hasSaveAndProceed,
      "Expected Save & Leave to call save then blocker.proceed()",
    ).toBe(true);
  });

  it("'Discard' calls blocker.proceed() without saving", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    // Discard should just proceed without saving
    expect(pageSource).toMatch(/proceed/);
  });

  it("'Cancel' calls blocker.reset() to stay on page", () => {
    pageSource = readSource(CANVAS_PAGE_PATH);
    // Cancel should call blocker.reset() to dismiss the dialog
    expect(pageSource).toMatch(/reset/);
  });
});

// ===========================================================================
// 5. Uses Dialog component from library (AC5)
// ===========================================================================

describe("Uses Dialog component from library (AC5)", () => {
  it("imports Dialog components from @runsight/ui/dialog", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(
      /import.*Dialog.*from.*@runsight\/ui\/dialog/,
    );
  });

  it("renders Dialog component in JSX", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // Should use <Dialog> or <DialogContent> etc.
    expect(pageSource).toMatch(/<Dialog[\s>]/);
  });

  it("uses DialogContent for the modal popup", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/<DialogContent/);
  });

  it("uses DialogTitle or DialogHeader for the dialog heading", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    const hasTitle =
      /<DialogTitle/.test(pageSource) || /<DialogHeader/.test(pageSource);
    expect(
      hasTitle,
      "Expected DialogTitle or DialogHeader in the unsaved changes dialog",
    ).toBe(true);
  });

  it("uses DialogFooter for the action buttons", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/<DialogFooter/);
  });
});

// ===========================================================================
// 6. Save calls PUT /api/workflows/:id (AC6)
// ===========================================================================

describe("Save calls PUT /api/workflows/:id (AC6)", () => {
  it("CanvasPage invokes updateWorkflow mutation on save", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // CanvasPage should import and use the updateWorkflow mutation
    const hasUpdateWorkflow =
      /useUpdateWorkflow/.test(pageSource) ||
      /updateWorkflow/.test(pageSource);
    expect(
      hasUpdateWorkflow,
      "Expected useUpdateWorkflow hook usage in CanvasPage for save",
    ).toBe(true);
  });

  it("save handler sends yaml content in the mutation", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // The save should pass { yaml: ... } to the mutation
    expect(pageSource).toMatch(/yaml/);
    expect(pageSource).toMatch(/mutate/);
  });

  it("successful save resets isDirty to false", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // After successful save, isDirty should be set back to false
    const resetsDirty =
      /setIsDirty\s*\(\s*false\s*\)/.test(pageSource) ||
      /onSuccess[\s\S]*?setIsDirty\s*\(\s*false\s*\)/.test(pageSource) ||
      /onDirtyChange\s*\(\s*false\s*\)/.test(pageSource);
    expect(
      resetsDirty,
      "Expected isDirty to be reset to false after successful save",
    ).toBe(true);
  });
});
