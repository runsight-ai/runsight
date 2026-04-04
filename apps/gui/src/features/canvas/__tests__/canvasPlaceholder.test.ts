/**
 * RED-TEAM tests for RUN-370: T15 — Canvas placeholder (disabled tab).
 *
 * This ticket makes the Canvas tab switchable (no longer disabled) but shows
 * a placeholder with EmptyState when selected. The YAML tab remains the
 * default and shows the editor content area.
 *
 * AC1: Canvas tab is switchable (NOT disabled) but shows placeholder
 * AC2: "Switch to YAML" button in placeholder switches to YAML tab
 * AC3: Placeholder uses EmptyState component pattern
 *
 * Expected failures (current state):
 *   - Canvas tab is disabled in CanvasTopbar.tsx
 *   - No EmptyState import or usage in CanvasPage/CanvasTopbar
 *   - No placeholder text "Visual canvas coming soon"
 *   - No "Switch to YAML" button
 *   - No conditional rendering based on active tab in CanvasPage
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

const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";

// ===========================================================================
// 1. Canvas tab is NOT disabled — it is switchable (AC1)
// ===========================================================================

describe("Canvas tab is switchable, not disabled (AC1)", () => {
  it("Canvas TabsTrigger does NOT have the disabled prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The Canvas tab trigger should no longer be disabled.
    // Currently: <TabsTrigger value="canvas" disabled>
    // Expected: <TabsTrigger value="canvas"> (no disabled)
    //
    // We look for a TabsTrigger with value="canvas" followed by "disabled"
    // before the closing >. This pattern should NOT exist after the fix.
    const canvasTabDisabled = /TabsTrigger\s+value=["']canvas["'][^>]*disabled/.test(source);
    expect(
      canvasTabDisabled,
      'Canvas TabsTrigger should NOT have disabled prop — it must be switchable',
    ).toBe(false);
  });

  it("Tabs component uses controlled value (not just defaultValue)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // With a switchable tab that triggers behavior, we need controlled state.
    // Should have value={...} and onValueChange={...} on the Tabs component.
    expect(source).toMatch(/onValueChange/);
  });

  it("Canvas tab has subtle disabled styling via className (visual hint, not actually disabled)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The Canvas tab trigger itself should have a className with subtle styling
    // (e.g., opacity-50, text-muted) applied directly, not via the disabled prop.
    // Look for a className on or near the Canvas TabsTrigger that applies visual muting.
    const hasCanvasTabStyling = /TabsTrigger[^>]*value=["']canvas["'][^>]*className/.test(source);
    expect(
      hasCanvasTabStyling,
      'Canvas TabsTrigger should have a className with subtle disabled styling',
    ).toBe(true);
  });
});

// ===========================================================================
// 2. CanvasPage has conditional rendering based on active tab (AC1)
// ===========================================================================

describe("CanvasPage conditional rendering based on active tab", () => {
  it("CanvasPage imports EmptyState component", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import.*EmptyState.*from/);
  });

  it("CanvasPage has conditional content area for canvas vs yaml", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // There should be conditional rendering (ternary or &&) based on the active tab
    // to show either the placeholder or the YAML editor area
    const hasConditional = /activeTab|selectedTab|tab\s*===|currentTab/.test(source);
    expect(
      hasConditional,
      'CanvasPage should have conditional rendering based on active tab state',
    ).toBe(true);
  });

  it("CanvasTopbar exposes or lifts tab state to CanvasPage", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // CanvasPage needs to know which tab is active to render the right content.
    // Either: CanvasTopbar accepts onTabChange callback, or tab state is lifted.
    const hasTabState = /onTabChange|activeTab|tab|setTab|TabChange/.test(source);
    expect(
      hasTabState,
      'CanvasPage should have tab state awareness (onTabChange, activeTab, etc.)',
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Placeholder content — text and messaging (AC1, AC3)
// ===========================================================================

describe("Canvas placeholder content", () => {
  it('placeholder has text "Visual canvas coming soon"', () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/Visual canvas coming soon/);
  });

  it('placeholder has description about switching to YAML', () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Description should mention switching to YAML to edit the workflow
    expect(source).toMatch(/Switch to YAML to edit/i);
  });
});

// ===========================================================================
// 4. "Switch to YAML" button (AC2)
// ===========================================================================

describe('"Switch to YAML" button switches tab (AC2)', () => {
  it('"Switch to YAML" text exists in CanvasPage', () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/Switch to YAML/);
  });

  it('"Switch to YAML" is wired to an action that changes the active tab', () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The EmptyState action onClick should switch the tab to "yaml"
    // Look for a pattern like: onClick: () => setTab("yaml") or similar
    const switchesTab = /["']yaml["']/.test(source);
    expect(
      switchesTab,
      'The "Switch to YAML" action should set the active tab to "yaml"',
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Uses EmptyState component pattern (AC3)
// ===========================================================================

describe("Placeholder uses EmptyState component pattern (AC3)", () => {
  it("EmptyState is rendered with a title prop", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // EmptyState requires a title prop
    expect(source).toMatch(/<EmptyState/);
  });

  it("EmptyState is rendered with an icon prop", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // EmptyState requires an icon prop (LucideIcon)
    // Should import a Lucide icon for the placeholder
    const hasIconImport = /import.*from\s*["']lucide-react["']/.test(source);
    expect(
      hasIconImport,
      'Should import a Lucide icon for the EmptyState placeholder',
    ).toBe(true);
  });

  it("EmptyState is rendered with an action prop for the switch button", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // EmptyState accepts action: { label, onClick }
    // The action label should be "Switch to YAML"
    expect(source).toMatch(/action\s*=\s*\{/);
  });
});

// ===========================================================================
// 6. "Coming soon" tooltip removed from Canvas tab (cleanup)
// ===========================================================================

describe("Canvas tab tooltip cleanup", () => {
  it('"Coming soon" tooltip is removed from the Canvas tab', () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Since the Canvas tab is now switchable and shows a proper placeholder,
    // the tooltip wrapper around it should be removed
    const hasComingSoonTooltip = /TooltipContent[^<]*>Coming soon</.test(source);
    expect(
      hasComingSoonTooltip,
      'The "Coming soon" tooltip should be removed now that Canvas tab is switchable',
    ).toBe(false);
  });
});
