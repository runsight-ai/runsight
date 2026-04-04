/**
 * RED-TEAM tests for RUN-365: T8 — Bottom panel — Logs tab wired to runs API.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Bottom panel renders in canvas page
 * AC2: Logs tab shows execution logs
 * AC3: Auto-scrolls on new entries
 * AC4: Collapsible via tab bar click
 * AC5: SSE events appear in real-time during execution
 *
 * Expected failures (current state):
 *   - No CanvasBottomPanel.tsx component exists in canvas feature
 *   - CanvasPage.tsx does not import or render a bottom panel
 *   - No auto-scroll ref in canvas bottom panel
 *   - No SSE log wiring in canvas feature
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
const CANVAS_BOTTOM_PANEL_PATH = "features/canvas/CanvasBottomPanel.tsx";

// ===========================================================================
// 1. CanvasBottomPanel component exists (AC1)
// ===========================================================================

describe("CanvasBottomPanel component exists (AC1)", () => {
  it("CanvasBottomPanel.tsx file exists in canvas feature", () => {
    expect(
      fileExists(CANVAS_BOTTOM_PANEL_PATH),
      "Expected features/canvas/CanvasBottomPanel.tsx to exist",
    ).toBe(true);
  });

  it("CanvasBottomPanel exports a named component", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+CanvasBottomPanel/);
  });
});

// ===========================================================================
// 2. CanvasPage imports and renders CanvasBottomPanel (AC1)
// ===========================================================================

describe("CanvasPage renders bottom panel (AC1)", () => {
  it("CanvasPage imports CanvasBottomPanel", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import.*CanvasBottomPanel.*from/);
  });

  it("CanvasPage renders <CanvasBottomPanel", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<CanvasBottomPanel/);
  });
});

// ===========================================================================
// 3. Logs tab shows execution logs (AC2)
// ===========================================================================

describe("Logs tab shows execution logs (AC2)", () => {
  it("CanvasBottomPanel imports useRunLogs hook", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/import.*useRunLogs.*from/);
  });

  it("CanvasBottomPanel calls useRunLogs", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/useRunLogs\s*\(/);
  });

  it("renders a Logs tab button or trigger", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should have a tab labeled "Logs"
    expect(source).toMatch(/Logs/);
  });

  it("renders log entries with timestamp", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Log entries should display timestamp field
    expect(source).toMatch(/timestamp/);
  });

  it("renders log entries with level", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Log entries should display the log level
    expect(source).toMatch(/\.level/);
  });

  it("renders log entries with message", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Log entries should display the message
    expect(source).toMatch(/\.message/);
  });
});

// ===========================================================================
// 4. Auto-scroll on new entries (AC3)
// ===========================================================================

describe("Auto-scrolls on new entries (AC3)", () => {
  it("has a scrollable container ref for auto-scroll", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should have a useRef for the scroll container
    const hasScrollRef = /useRef|scrollRef|logsRef|scrollContainerRef/.test(source);
    expect(
      hasScrollRef,
      "Expected a ref for auto-scroll container",
    ).toBe(true);
  });

  it("uses useEffect to scroll to bottom when logs change", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should have scrollIntoView or scrollTop logic in an effect
    const hasAutoScroll = /scrollIntoView|scrollTop|scrollTo/.test(source);
    expect(
      hasAutoScroll,
      "Expected auto-scroll logic (scrollIntoView or scrollTop)",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Collapsible via tab bar click (AC4)
// ===========================================================================

describe("Collapsible via tab bar click (AC4)", () => {
  it("has a 36px tab bar height when collapsed", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Collapsed state should be ~36px (h-9 = 36px or h-[36px])
    const hasCollapsedHeight = /h-9|h-\[36px\]/.test(source);
    expect(
      hasCollapsedHeight,
      "Expected 36px (h-9 or h-[36px]) height for collapsed state",
    ).toBe(true);
  });

  it("expands to ~200px when open", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Expanded state should be ~200px
    const hasExpandedHeight = /h-\[200px\]|h-\[12\.5rem\]|200/.test(source);
    expect(
      hasExpandedHeight,
      "Expected ~200px height for expanded state",
    ).toBe(true);
  });

  it("has a collapse/expand toggle button", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should have a toggle button with aria-label for collapse/expand
    const hasToggle = /Collapse|Expand|isExpanded|setIsExpanded|collapsed|setCollapsed/.test(source);
    expect(
      hasToggle,
      "Expected collapse/expand toggle state and button",
    ).toBe(true);
  });

  it("toggle button has accessible aria-label", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/aria-label.*[Cc]ollapse|aria-label.*[Ee]xpand/);
  });
});

// ===========================================================================
// 6. SSE events appear in real-time (AC5)
// ===========================================================================

describe("SSE events appear in real-time during execution (AC5)", () => {
  it("CanvasBottomPanel uses EventSource or SSE hook for live logs", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should connect to SSE for real-time log updates
    const hasSSE = /EventSource|useRunStream|useSSE|stream|sse/.test(source);
    expect(
      hasSSE,
      "Expected SSE integration (EventSource, useRunStream, or similar)",
    ).toBe(true);
  });

  it("SSE connection targets the run stream endpoint", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should reference /api/runs/:id/stream or similar SSE endpoint
    const hasStreamEndpoint = /\/runs\/.*\/stream|\/api\/runs\/.*stream|log_entry/.test(source);
    expect(
      hasStreamEndpoint,
      "Expected SSE endpoint reference for run stream or log_entry event",
    ).toBe(true);
  });

  it("handles log_entry SSE events to append logs", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should handle log_entry events from SSE
    const handlesLogEvent = /log_entry|addEventListener.*log|onmessage/.test(source);
    expect(
      handlesLogEvent,
      "Expected log_entry SSE event handler",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. Bottom panel has data-testid for integration testing
// ===========================================================================

describe("Bottom panel testability", () => {
  it("has data-testid on the root element", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/data-testid\s*=\s*["']canvas-bottom-panel["']/);
  });

  it("has role=tablist on the tab bar", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/role\s*=\s*["']tablist["']/);
  });
});
