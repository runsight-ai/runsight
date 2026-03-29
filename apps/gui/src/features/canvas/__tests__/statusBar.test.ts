/**
 * RED-TEAM tests for RUN-364: T10 — Status bar — connection, block count, view mode.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Height: var(--status-bar-height) = 22px
 * AC2: Connection status with dot indicator
 * AC3: Block and edge count (parsed from YAML)
 * AC4: Current view mode label
 *
 * Expected failures (current state):
 *   - No CanvasStatusBar component exists
 *   - CanvasPage does not render a status bar
 *   - No connection status, block/edge count, or view mode in status bar
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

const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const STATUS_BAR_PATH = "features/canvas/CanvasStatusBar.tsx";

// ===========================================================================
// 1. CanvasStatusBar component exists and is imported in CanvasPage
// ===========================================================================

describe("CanvasStatusBar component exists", () => {
  it("CanvasStatusBar.tsx file exists", () => {
    expect(
      fileExists(STATUS_BAR_PATH),
      "Expected features/canvas/CanvasStatusBar.tsx to exist",
    ).toBe(true);
  });

  it("CanvasStatusBar exports a named component", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+CanvasStatusBar/);
  });

  it("CanvasPage imports CanvasStatusBar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import.*CanvasStatusBar.*from/);
  });

  it("CanvasPage renders <CanvasStatusBar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<CanvasStatusBar/);
  });
});

// ===========================================================================
// 2. Height uses --status-bar-height token (AC1)
// ===========================================================================

describe("Status bar height uses --status-bar-height (AC1)", () => {
  it("CanvasStatusBar uses h-[var(--status-bar-height)]", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).toMatch(/h-\[var\(--status-bar-height\)\]/);
  });

  it("CanvasStatusBar does NOT use hardcoded height values", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).not.toMatch(/\bh-5\b/);
    expect(source).not.toMatch(/\bh-6\b/);
    expect(source).not.toMatch(/h-\[22px\]/);
  });
});

// ===========================================================================
// 3. Connection status with dot indicator (AC2)
// ===========================================================================

describe("Connection status with dot indicator (AC2)", () => {
  it("imports StatusDot component from component library", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).toMatch(/import.*StatusDot.*from.*(@runsight\/ui\/status-dot|components\/ui\/status-dot)/);
  });

  it("renders <StatusDot in the status bar", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).toMatch(/<StatusDot/);
  });

  it("imports useProviders hook for connection status", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).toMatch(/import.*useProviders.*from/);
  });

  it("displays provider name or connection info text", () => {
    const source = readSource(STATUS_BAR_PATH);
    // Should show some provider/connection info label
    const hasProviderLabel =
      /provider|connected|connection|status/i.test(source);
    expect(
      hasProviderLabel,
      "Expected provider name or connection status text near the dot",
    ).toBe(true);
  });

  it("uses StatusDot variant to indicate connection state (success/danger/neutral)", () => {
    const source = readSource(STATUS_BAR_PATH);
    // Should conditionally set variant based on provider status
    const hasVariantLogic =
      /variant\s*=\s*\{|variant=\{|variant:\s*["']success|variant:\s*["']danger/.test(source) ||
      /success|danger|active/.test(source);
    expect(
      hasVariantLogic,
      "Expected StatusDot variant to change based on connection state",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Block and edge count (AC3)
// ===========================================================================

describe("Block and edge count from YAML parse (AC3)", () => {
  it("displays a block count label", () => {
    const source = readSource(STATUS_BAR_PATH);
    // Should show something like "3 blocks" or "blocks: 3"
    const hasBlockCount =
      /block|Block/.test(source);
    expect(
      hasBlockCount,
      "Expected block count display in the status bar",
    ).toBe(true);
  });

  it("displays an edge count label", () => {
    const source = readSource(STATUS_BAR_PATH);
    // Should show something like "2 edges" or "edges: 2"
    const hasEdgeCount =
      /edge|Edge/.test(source);
    expect(
      hasEdgeCount,
      "Expected edge count display in the status bar",
    ).toBe(true);
  });

  it("receives or computes block/edge counts from parsed YAML data", () => {
    const source = readSource(STATUS_BAR_PATH);
    // Should either accept props for counts or import the parser
    const hasCountData =
      /blockCount|nodeCount|edgeCount|nodes\.length|edges\.length|parseWorkflow/.test(source);
    expect(
      hasCountData,
      "Expected block/edge count data from YAML parsing",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Current view mode label (AC4)
// ===========================================================================

describe("Current view mode label (AC4)", () => {
  it("displays the current view mode (Canvas or YAML)", () => {
    const source = readSource(STATUS_BAR_PATH);
    // Should show the current mode label
    const hasViewMode =
      /Canvas|YAML|viewMode|activeTab|mode/i.test(source);
    expect(
      hasViewMode,
      "Expected current view mode label in the status bar",
    ).toBe(true);
  });

  it("accepts activeTab or viewMode as a prop", () => {
    const source = readSource(STATUS_BAR_PATH);
    // The component should receive the current view mode
    const hasModeProp =
      /activeTab|viewMode|mode\s*[?:]/i.test(source);
    expect(
      hasModeProp,
      "Expected activeTab or viewMode prop on CanvasStatusBar",
    ).toBe(true);
  });

  it("CanvasPage passes activeTab to CanvasStatusBar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should pass the tab state to the status bar
    expect(source).toMatch(/CanvasStatusBar.*activeTab|CanvasStatusBar.*viewMode/s);
  });
});

// ===========================================================================
// 6. Design system compliance
// ===========================================================================

describe("Status bar design system compliance", () => {
  it("uses flexbox layout with items-center", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).toMatch(/flex/);
    expect(source).toMatch(/items-center/);
  });

  it("does NOT use hardcoded hex or rgba colors", () => {
    const source = readSource(STATUS_BAR_PATH);
    const hexMatches = source.match(/#[0-9a-fA-F]{3,8}\b/g);
    expect(hexMatches).toBeNull();
    expect(source).not.toMatch(/rgba?\s*\(\s*\d+/);
  });

  it("uses border token for top border separation", () => {
    const source = readSource(STATUS_BAR_PATH);
    // Status bar sits at bottom, should have a top border
    const hasBorderToken =
      /border-t|border-border/.test(source);
    expect(
      hasBorderToken,
      "Expected top border using design system tokens",
    ).toBe(true);
  });

  it("uses text-xs or text-[11px] for small status bar text", () => {
    const source = readSource(STATUS_BAR_PATH);
    const hasSmallText = /text-xs|text-\[11px\]|text-\[10px\]/.test(source);
    expect(
      hasSmallText,
      "Expected small text size (text-xs or similar) for status bar",
    ).toBe(true);
  });
});
