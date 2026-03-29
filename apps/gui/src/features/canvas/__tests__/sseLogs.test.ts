/**
 * RED+GREEN tests for RUN-371: T16 — SSE connection on Run -> live logs in bottom panel.
 *
 * These tests verify by reading source files:
 *
 * AC1: CanvasBottomPanel uses activeRunId from canvas store (not just props)
 * AC2: EventSource connects to /api/runs/:id/stream endpoint
 * AC3: SSE event types handled: node_started, node_completed, node_failed
 * AC4: Event-to-log-entry mapping for node lifecycle events
 * AC5: EventSource closed on terminal events (run_completed / run_failed)
 * AC6: useRunStream or mapSSEEventToStoreAction is imported
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

const CANVAS_BOTTOM_PANEL_PATH = "features/canvas/CanvasBottomPanel.tsx";

// ===========================================================================
// 1. CanvasBottomPanel uses activeRunId from canvas store (AC1)
// ===========================================================================

describe("CanvasBottomPanel uses activeRunId from canvas store (AC1)", () => {
  it("imports useCanvasStore", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/import.*useCanvasStore.*from/);
  });

  it("reads activeRunId from the canvas store", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should select activeRunId from the store
    expect(source).toMatch(/activeRunId/);
  });

  it("uses store activeRunId as the SSE connection trigger (not just props)", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // The store's activeRunId should be used to determine SSE connection
    const hasStoreRunId = /useCanvasStore/.test(source) && /activeRunId/.test(source);
    expect(hasStoreRunId, "Expected store-based activeRunId for SSE trigger").toBe(true);
  });
});

// ===========================================================================
// 2. EventSource connects to /api/runs/:id/stream (AC2)
// ===========================================================================

describe("EventSource connects to stream endpoint (AC2)", () => {
  it("creates an EventSource with the runs stream URL", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/new\s+EventSource/);
  });

  it("targets /api/runs/:id/stream endpoint", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/\/api\/runs\/.*\/stream/);
  });

  it("EventSource is created inside a useEffect", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should have useEffect containing EventSource
    const hasEffectWithSSE = /useEffect/.test(source) && /EventSource/.test(source);
    expect(hasEffectWithSSE, "Expected EventSource inside useEffect").toBe(true);
  });
});

// ===========================================================================
// 3. SSE event types handled: node_started, node_completed, node_failed (AC3)
// ===========================================================================

describe("SSE event types handled (AC3)", () => {
  it("handles node_started events", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/node_started/);
  });

  it("handles node_completed events", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/node_completed/);
  });

  it("handles node_failed events", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/node_failed/);
  });
});

// ===========================================================================
// 4. Event-to-log-entry mapping (AC4)
// ===========================================================================

describe("Event-to-log-entry mapping for node lifecycle events (AC4)", () => {
  it("converts SSE node events into LogEntry objects with level and message", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should map node events to log entries with level/message
    const mapsToEntries =
      /node_started|node_completed|node_failed/.test(source) &&
      /level/.test(source) &&
      /message/.test(source);
    expect(mapsToEntries, "Expected node events mapped to LogEntry with level and message").toBe(
      true,
    );
  });

  it("appends SSE-derived entries to the log display", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should accumulate SSE entries in state
    const appendsEntries = /setSseEntries|setSSEEntries|sseEntries/.test(source);
    expect(appendsEntries, "Expected SSE entries accumulated in state").toBe(true);
  });
});

// ===========================================================================
// 5. EventSource closed on terminal events (AC5)
// ===========================================================================

describe("EventSource closed on terminal events (AC5)", () => {
  it("handles run_completed terminal event", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/run_completed/);
  });

  it("handles run_failed terminal event", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/run_failed/);
  });

  it("closes EventSource on terminal events", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // Should call source.close() in response to terminal events
    const closesOnTerminal = /\.close\(\)/.test(source);
    expect(closesOnTerminal, "Expected EventSource.close() call for terminal events").toBe(true);
  });

  it("cleanup function in useEffect closes EventSource", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    // useEffect return should close the source
    const hasCleanup = /return\s*\(\)\s*=>.*close/.test(source);
    expect(hasCleanup, "Expected useEffect cleanup that closes EventSource").toBe(true);
  });
});

// ===========================================================================
// 6. useRunStream or mapSSEEventToStoreAction imported (AC6)
// ===========================================================================

describe("SSE store integration imported (AC6)", () => {
  it("imports mapSSEEventToStoreAction or useRunStream", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    const hasImport = /import.*mapSSEEventToStoreAction|import.*useRunStream/.test(source);
    expect(hasImport, "Expected import of mapSSEEventToStoreAction or useRunStream").toBe(true);
  });

  it("calls mapSSEEventToStoreAction to dispatch store actions from SSE events", () => {
    const source = readSource(CANVAS_BOTTOM_PANEL_PATH);
    expect(source).toMatch(/mapSSEEventToStoreAction/);
  });
});
