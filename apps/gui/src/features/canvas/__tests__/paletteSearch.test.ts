/**
 * RED-TEAM tests for RUN-362: T7 — Palette search + drag source.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Search filters palette items
 * AC2: Items have draggable attribute + data-transfer
 * AC3: Drag cursor shows on drag start
 * AC4: Search clears on collapse
 *
 * Expected failures (current state):
 *   - No search input exists in PaletteSidebar
 *   - No draggable attributes or onDragStart handlers exist
 *   - No data-transfer logic exists
 *   - No search-clear-on-collapse logic exists
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

const PALETTE_SIDEBAR_PATH = "features/canvas/PaletteSidebar.tsx";

// ===========================================================================
// 1. Search input exists in palette (AC1)
// ===========================================================================

describe("Palette search input (AC1)", () => {
  it("has a search input element", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasSearchInput =
      /<input.*type=["'](?:text|search)["']|<Input/.test(source);
    expect(
      hasSearchInput,
      "Expected a search/text input element in PaletteSidebar",
    ).toBe(true);
  });

  it("has a search state variable", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Must have a dedicated search/filter state, not just the existing isCollapsed
    const hasSearchSpecificState =
      /useState.*search|useState.*query|useState.*filter|search.*useState|query.*useState|filter.*useState/is.test(
        source,
      );
    expect(
      hasSearchSpecificState,
      "Expected a search/query/filter state variable via useState",
    ).toBe(true);
  });

  it("has a placeholder text for the search input", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasPlaceholder =
      /placeholder=["'][^"']*(?:search|filter|find)[^"']*["']/i.test(source);
    expect(
      hasPlaceholder,
      "Expected search input to have a placeholder like 'Search...' or 'Filter...'",
    ).toBe(true);
  });

  it("search input is hidden when sidebar is collapsed", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // The search input should not render when collapsed
    const hasConditionalSearch =
      /!isCollapsed.*(?:<input|<Input|search)|collapsed.*(?:<input|<Input|search)/is.test(
        source,
      );
    expect(
      hasConditionalSearch,
      "Expected search input to be conditionally hidden when collapsed",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. Search filters palette items (AC1)
// ===========================================================================

describe("Search filters palette items (AC1)", () => {
  it("block types are filtered by search query", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Should filter BLOCK_TYPES based on search input value
    const hasFilter =
      /BLOCK_TYPES\.filter|\.filter\(.*label.*search|\.filter\(.*search.*label|\.filter\(.*query|\.filter\(.*filter/i.test(
        source,
      );
    expect(
      hasFilter,
      "Expected BLOCK_TYPES to be filtered by search query",
    ).toBe(true);
  });

  it("souls are filtered by search query", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Souls list should also be filtered
    const hasSoulFilter =
      /souls.*\.filter|filteredSouls|matchingSouls/i.test(source);
    expect(
      hasSoulFilter,
      "Expected souls list to be filtered by search query",
    ).toBe(true);
  });

  it("filter is case-insensitive", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Should use toLowerCase() or toLocaleLowerCase() or a case-insensitive regex
    const hasCaseInsensitive =
      /toLowerCase|toLocaleLowerCase|RegExp.*["']i["']|new RegExp\(.*,\s*["']i["']\)/i.test(
        source,
      );
    expect(
      hasCaseInsensitive,
      "Expected case-insensitive filtering (toLowerCase or regex 'i' flag)",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Items have draggable attribute (AC2)
// ===========================================================================

describe("Palette items are draggable (AC2)", () => {
  it("block type items have draggable attribute", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasDraggable = /draggable/.test(source);
    expect(
      hasDraggable,
      "Expected palette items to have draggable attribute",
    ).toBe(true);
  });

  it("block type items have onDragStart handler", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasOnDragStart = /onDragStart/.test(source);
    expect(
      hasOnDragStart,
      "Expected palette items to have onDragStart handler",
    ).toBe(true);
  });

  it("soul items have draggable attribute", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Both block types AND souls should be draggable
    // Count occurrences of draggable — should appear at least twice (blocks + souls)
    const draggableMatches = source.match(/draggable/g);
    expect(
      draggableMatches && draggableMatches.length >= 2,
      "Expected draggable attribute on both block type and soul items",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Data transfer on drag (AC2)
// ===========================================================================

describe("Data transfer payload on drag (AC2)", () => {
  it("sets dataTransfer data on drag start", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    const hasSetData = /dataTransfer\.setData|event\.dataTransfer|e\.dataTransfer/.test(
      source,
    );
    expect(
      hasSetData,
      "Expected dataTransfer.setData call in onDragStart handler",
    ).toBe(true);
  });

  it("transfers item type information (block type or soul)", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Should transfer enough info to identify what was dragged
    // e.g., setData("application/runsight-block", ...) or setData("text/plain", ...)
    const hasTypePayload =
      /setData\s*\(\s*["'][^"']+["']\s*,/.test(source);
    expect(
      hasTypePayload,
      "Expected dataTransfer.setData with a MIME type and payload",
    ).toBe(true);
  });

  it("block items transfer their block type label", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // The transferred data should include the block type (e.g., "Linear", "Gate")
    const hasLabelInPayload =
      /setData.*label|setData.*type|JSON\.stringify.*label|JSON\.stringify.*type/i.test(
        source,
      );
    expect(
      hasLabelInPayload,
      "Expected block type label or type to be included in drag payload",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Drag cursor on drag start (AC3)
// ===========================================================================

describe("Drag cursor on drag start (AC3)", () => {
  it("sets effectAllowed on drag start", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Should set effectAllowed to control cursor appearance
    const hasEffectAllowed = /effectAllowed/.test(source);
    expect(
      hasEffectAllowed,
      "Expected dataTransfer.effectAllowed to be set (e.g., 'move' or 'copy')",
    ).toBe(true);
  });

  it("uses cursor-grab or cursor style for draggable items", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // Items should show grab cursor to indicate they are draggable
    const hasGrabCursor =
      /cursor-grab|cursor:\s*grab|cursor-move|cursor:\s*move|grab/.test(source);
    expect(
      hasGrabCursor,
      "Expected cursor-grab or cursor-move style on draggable palette items",
    ).toBe(true);
  });
});

// ===========================================================================
// 6. Search clears on collapse (AC4)
// ===========================================================================

describe("Search clears on collapse (AC4)", () => {
  it("collapse handler resets search state", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // When the sidebar collapses, the search query should be cleared
    // Look for search state being reset in or near the collapse toggle logic
    const hasClearOnCollapse =
      /setSearch\s*\(\s*["']["']\s*\)|setQuery\s*\(\s*["']["']\s*\)|setFilter\s*\(\s*["']["']\s*\)/i.test(
        source,
      );
    expect(
      hasClearOnCollapse,
      "Expected search state to be cleared (setSearch('') or similar) when collapsing",
    ).toBe(true);
  });

  it("clear logic is tied to collapse toggle, not just any action", () => {
    const source = readSource(PALETTE_SIDEBAR_PATH);
    // The clear should happen specifically when collapsing
    // Look for the pattern: setIsCollapsed + setSearch in close proximity (within a handler)
    const collapseAndClear =
      /setIsCollapsed[\s\S]{0,100}setSearch|setSearch[\s\S]{0,100}setIsCollapsed|setCollapsed[\s\S]{0,100}setSearch|setSearch[\s\S]{0,100}setCollapsed/i.test(
        source,
      );
    expect(
      collapseAndClear,
      "Expected search clear to be co-located with collapse toggle logic",
    ).toBe(true);
  });
});
