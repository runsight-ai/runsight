/**
 * RED-TEAM tests for RUN-361: T6 — Palette sidebar — block types + souls list, collapsible.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Palette shows block types (Linear, Gate, Code, FileWriter) + souls
 * AC2: Collapsible 240px <-> 48px via notch button
 * AC3: Icons visible in collapsed state (icon rail at 48px)
 * AC4: Souls loaded from API via useSouls hook
 * AC5: Hover tooltips in collapsed state
 *
 * Expected failures (current state):
 *   - No PaletteSidebar component exists
 *   - CanvasPage does not render PaletteSidebar
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const PALETTE_SIDEBAR_PATH = "features/canvas/PaletteSidebar.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. PaletteSidebar component exists
// ===========================================================================

describe("PaletteSidebar component exists", () => {
  it("PaletteSidebar.tsx file exists", () => {
    expect(
      fileExists(PALETTE_SIDEBAR_PATH),
      "Expected features/canvas/PaletteSidebar.tsx to exist",
    ).toBe(true);
  });

  it("PaletteSidebar exports a named component", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+PaletteSidebar/);
  });
});

// ===========================================================================
// 2. CanvasPage — PaletteSidebar hidden (canvas coming soon)
// ===========================================================================

describe("CanvasPage hides PaletteSidebar (canvas coming soon)", () => {
  it("CanvasPage does NOT render <PaletteSidebar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).not.toMatch(/<PaletteSidebar/);
  });

  it("PaletteSidebar component file still exists (not deleted)", () => {
    expect(
      fileExists(PALETTE_SIDEBAR_PATH),
      "PaletteSidebar.tsx should still exist — hidden, not deleted",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Block types section — Linear, Gate, Code, FileWriter (AC1)
// ===========================================================================

describe("Block types listed in palette (AC1)", () => {
  it("palette contains Linear block type", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/Linear/);
  });

  it("palette contains Gate block type", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/Gate/);
  });

  it("palette contains Code block type", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/Code/);
  });

  it("palette contains FileWriter block type", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/FileWriter/);
  });

  it("block types have icons", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Each block type should have an associated icon (lucide or custom)
    // Expect at least 4 icon imports or icon references
    const iconImports = source.match(/from\s+["']lucide-react["']/g);
    expect(
      iconImports && iconImports.length >= 1,
      "Expected lucide-react icon imports for block types",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Souls section — loaded from API (AC4)
// ===========================================================================

describe("Souls loaded from API (AC4)", () => {
  it("PaletteSidebar imports useSouls hook", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/import.*useSouls.*from/);
  });

  it("PaletteSidebar calls useSouls()", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/useSouls\s*\(/);
  });

  it("PaletteSidebar has a Souls section heading or label", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/Souls/);
  });
});

// ===========================================================================
// 5. Collapsible 240px <-> 48px via notch button (AC2)
// ===========================================================================

describe("Collapsible sidebar 240px <-> 48px (AC2)", () => {
  it("has a collapsed/expanded state variable", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasCollapseState =
      /isCollapsed|collapsed|setCollapsed|setIsCollapsed|expanded|isExpanded/.test(source);
    expect(
      hasCollapseState,
      "Expected a collapse state variable (isCollapsed/collapsed/expanded)",
    ).toBe(true);
  });

  it("references expanded width of 240px", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/240/);
  });

  it("references collapsed width of 48px", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/48/);
  });

  it("has a toggle/notch button for collapse", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Should have a button element that toggles collapse state
    const hasToggle = /<button|Button/.test(source) &&
      /toggle|collapse|expand|notch|chevron/i.test(source);
    expect(
      hasToggle,
      "Expected a toggle/notch button for collapsing the sidebar",
    ).toBe(true);
  });

  it("uses a chevron icon for the notch button", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Notch button should use a chevron icon that rotates on collapse
    expect(source).toMatch(/Chevron|ChevronLeft|ChevronRight|PanelLeft/i);
  });
});

// ===========================================================================
// 6. Icons visible in collapsed state — icon rail (AC3)
// ===========================================================================

describe("Icons visible in collapsed state (AC3)", () => {
  it("block type icons render regardless of collapse state", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Icons should always be rendered; only labels are hidden when collapsed
    // The icon should not be conditionally rendered based on collapse state
    // Look for a pattern where icon is always shown, label is conditionally hidden
    const hasConditionalLabel =
      /collapsed.*hidden|isCollapsed.*hidden|!collapsed.*label|!isCollapsed.*label|collapsed\s*\?|isCollapsed\s*\?/.test(source);
    expect(
      hasConditionalLabel,
      "Expected labels to be conditionally hidden when collapsed while icons remain visible",
    ).toBe(true);
  });

  it("sidebar renders as an aside or nav element", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasSemantic = /<aside|<nav|role=["']navigation["']/.test(source);
    expect(
      hasSemantic,
      "Expected semantic aside or nav element for the sidebar",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. Hover tooltips in collapsed state (AC5)
// ===========================================================================

describe("Hover tooltips in collapsed state (AC5)", () => {
  it("imports Tooltip components", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).toMatch(/import.*Tooltip.*from.*(@runsight\/ui\/tooltip|components\/ui\/tooltip)/);
  });

  it("wraps items with Tooltip for collapsed state", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Tooltips should wrap sidebar items, shown when collapsed
    expect(source).toMatch(/<Tooltip/);
    expect(source).toMatch(/<TooltipTrigger/);
    expect(source).toMatch(/<TooltipContent/);
  });

  it("tooltip visibility is tied to collapsed state", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Tooltips should only appear (or be relevant) when sidebar is collapsed
    const hasConditionalTooltip =
      /collapsed.*Tooltip|isCollapsed.*Tooltip|Tooltip.*collapsed/.test(source);
    expect(
      hasConditionalTooltip,
      "Expected tooltips to be conditional on collapsed state",
    ).toBe(true);
  });
});

// ===========================================================================
// 8. Design system compliance
// ===========================================================================

describe("PaletteSidebar uses design system tokens", () => {
  it("does NOT use hardcoded hex colors", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hexMatches = source.match(/#[0-9a-fA-F]{3,8}\b/g);
    expect(hexMatches).toBeNull();
  });

  it("does NOT use hardcoded rgba colors", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    expect(source).not.toMatch(/rgba?\s*\(\s*\d+/);
  });

  it("uses border token for section dividers", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasBorderToken = /border-border|border-\(--/.test(source);
    expect(
      hasBorderToken,
      "Expected border using design system tokens for section dividers",
    ).toBe(true);
  });
});
