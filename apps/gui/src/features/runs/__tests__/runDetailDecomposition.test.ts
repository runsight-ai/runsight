/**
 * RED-TEAM tests for RUN-243: RunDetail decomposition — extract 4 sub-components.
 *
 * These tests verify:
 * 1. Sub-component files exist and export correctly
 * 2. No single file exceeds 200 lines
 * 3. RunCanvasNode is memoized with a custom comparator
 * 4. CanvasErrorBoundary wraps ReactFlow in RunDetail
 * 5. RunDetail imports from the new sub-component files
 * 6. RunDetail is a thin orchestrator (~120 lines)
 * 7. No local utility duplicates remain in RunDetail
 * 8. Backward compatibility: default export, useParams, etc.
 *
 * Approach: source-structure tests (read file, check patterns).
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const RUNS_DIR = resolve(__dirname, "..");
const readSource = (filename: string): string =>
  readFileSync(resolve(RUNS_DIR, filename), "utf-8");

const countLines = (filename: string): number =>
  readSource(filename).split("\n").length;

const fileExists = (filename: string): boolean =>
  existsSync(resolve(RUNS_DIR, filename));

// ---------------------------------------------------------------------------
// 1. Sub-component files exist and export correctly
// ---------------------------------------------------------------------------

describe("Sub-component files exist (RUN-243)", () => {
  it("RunCanvasNode.tsx exists", () => {
    expect(fileExists("RunCanvasNode.tsx")).toBe(true);
  });

  it("RunInspectorPanel.tsx exists", () => {
    expect(fileExists("RunInspectorPanel.tsx")).toBe(true);
  });

  it("RunBottomPanel.tsx exists", () => {
    expect(fileExists("RunBottomPanel.tsx")).toBe(true);
  });

  it("RunDetailHeader.tsx exists", () => {
    expect(fileExists("RunDetailHeader.tsx")).toBe(true);
  });
});

describe("Sub-component exports (RUN-243)", () => {
  it("RunCanvasNode.tsx has a named export RunCanvasNode", () => {
    const src = readSource("RunCanvasNode.tsx");
    expect(src).toMatch(/export\s+(const|function)\s+RunCanvasNode\b/);
  });

  it("RunInspectorPanel.tsx has a named export RunInspectorPanel", () => {
    const src = readSource("RunInspectorPanel.tsx");
    expect(src).toMatch(/export\s+(const|function)\s+RunInspectorPanel\b/);
  });

  it("RunBottomPanel.tsx has a named export RunBottomPanel", () => {
    const src = readSource("RunBottomPanel.tsx");
    expect(src).toMatch(/export\s+(const|function)\s+RunBottomPanel\b/);
  });

  it("RunDetailHeader.tsx has a named export RunDetailHeader", () => {
    const src = readSource("RunDetailHeader.tsx");
    expect(src).toMatch(/export\s+(const|function)\s+RunDetailHeader\b/);
  });
});

// ---------------------------------------------------------------------------
// 2. Line count — no single file exceeds 200 lines
// ---------------------------------------------------------------------------

describe("Line count constraints (RUN-243)", () => {
  it("RunDetail.tsx does not exceed 200 lines", () => {
    const lines = countLines("RunDetail.tsx");
    expect(lines).toBeLessThanOrEqual(200);
  });

  it("RunCanvasNode.tsx does not exceed 200 lines", () => {
    const lines = countLines("RunCanvasNode.tsx");
    expect(lines).toBeLessThanOrEqual(200);
  });

  it("RunInspectorPanel.tsx does not exceed 200 lines", () => {
    const lines = countLines("RunInspectorPanel.tsx");
    expect(lines).toBeLessThanOrEqual(200);
  });

  it("RunBottomPanel.tsx does not exceed 200 lines", () => {
    const lines = countLines("RunBottomPanel.tsx");
    expect(lines).toBeLessThanOrEqual(200);
  });

  it("RunDetailHeader.tsx does not exceed 200 lines", () => {
    const lines = countLines("RunDetailHeader.tsx");
    expect(lines).toBeLessThanOrEqual(200);
  });
});

// ---------------------------------------------------------------------------
// 3. RunCanvasNode is memoized with a proper custom comparator
// ---------------------------------------------------------------------------

describe("RunCanvasNode memoization (RUN-243)", () => {
  it("uses React.memo or memo()", () => {
    const src = readSource("RunCanvasNode.tsx");
    const hasMemo = src.includes("React.memo") || src.includes("memo(");
    expect(hasMemo).toBe(true);
  });

  it("custom comparator checks data.status", () => {
    const src = readSource("RunCanvasNode.tsx");
    expect(src).toMatch(/data\.status/);
  });

  it("custom comparator checks data.executionCost", () => {
    const src = readSource("RunCanvasNode.tsx");
    expect(src).toMatch(/data\.executionCost/);
  });

  it("custom comparator checks data.duration", () => {
    const src = readSource("RunCanvasNode.tsx");
    expect(src).toMatch(/data\.duration/);
  });

  it("custom comparator checks selected", () => {
    const src = readSource("RunCanvasNode.tsx");
    // The comparator should compare prev.selected vs next.selected
    expect(src).toMatch(/selected/);
  });
});

// ---------------------------------------------------------------------------
// 4. CanvasErrorBoundary wraps ReactFlow in RunDetail
// ---------------------------------------------------------------------------

describe("CanvasErrorBoundary wraps ReactFlow (RUN-243)", () => {
  it("RunDetail imports CanvasErrorBoundary", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/import\s*\{[^}]*CanvasErrorBoundary[^}]*\}/);
  });

  it("RunDetail uses CanvasErrorBoundary in JSX", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/<CanvasErrorBoundary[\s>]/);
  });
});

// ---------------------------------------------------------------------------
// 5. RunDetail imports from sub-component files
// ---------------------------------------------------------------------------

describe("RunDetail imports sub-components (RUN-243)", () => {
  it("imports RunCanvasNode from ./RunCanvasNode", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/import\s*\{[^}]*RunCanvasNode[^}]*\}\s*from\s*["']\.\/RunCanvasNode["']/);
  });

  it("imports RunInspectorPanel from ./RunInspectorPanel", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/import\s*\{[^}]*RunInspectorPanel[^}]*\}\s*from\s*["']\.\/RunInspectorPanel["']/);
  });

  it("imports RunBottomPanel from ./RunBottomPanel", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/import\s*\{[^}]*RunBottomPanel[^}]*\}\s*from\s*["']\.\/RunBottomPanel["']/);
  });

  it("imports RunDetailHeader from ./RunDetailHeader", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/import\s*\{[^}]*RunDetailHeader[^}]*\}\s*from\s*["']\.\/RunDetailHeader["']/);
  });
});

// ---------------------------------------------------------------------------
// 6. RunDetail is a thin orchestrator
// ---------------------------------------------------------------------------

describe("RunDetail is a thin orchestrator (RUN-243)", () => {
  it("RunDetail.tsx is approximately 120 lines (under 200)", () => {
    const lines = countLines("RunDetail.tsx");
    // Must be dramatically reduced from 989 lines
    expect(lines).toBeLessThanOrEqual(200);
  });

  it("RunDetail does NOT define CanvasNodeComponent inline", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).not.toMatch(/function\s+CanvasNodeComponent\b/);
  });

  it("RunDetail does NOT define InspectorPanel inline", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).not.toMatch(/function\s+InspectorPanel\b/);
  });

  it("RunDetail does NOT define BottomPanel inline", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).not.toMatch(/function\s+BottomPanel\b/);
  });
});

// ---------------------------------------------------------------------------
// 7. No local utility duplicates in RunDetail
// ---------------------------------------------------------------------------

describe("No local utility duplicates in RunDetail (RUN-243)", () => {
  it("does NOT contain a local mapRunStatus function", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).not.toMatch(/function\s+mapRunStatus\b/);
  });

  it("does NOT contain a local getIconForBlockType function", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).not.toMatch(/function\s+getIconForBlockType\b/);
  });

  it("mapRunStatus is imported from a shared utility", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/import\s*\{[^}]*mapRunStatus[^}]*\}\s*from/);
  });

  it("getIconForBlockType is imported from a shared utility", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/import\s*\{[^}]*getIconForBlockType[^}]*\}\s*from/);
  });
});

// ---------------------------------------------------------------------------
// 8. Backward compatibility guards
// ---------------------------------------------------------------------------

describe("Backward compatibility (RUN-243)", () => {
  it("RunDetail has a default export", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/export\s+default\b/);
  });

  it("RunDetail uses useParams", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/useParams/);
  });

  it("RunDetail uses useRun hook for data fetching", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/useRun\s*\(/);
  });

  it("RunDetail wraps content in ReactFlowProvider", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/<ReactFlowProvider[\s>]/);
  });

  it("RunDetail exports Component for lazy loading", () => {
    const src = readSource("RunDetail.tsx");
    expect(src).toMatch(/export\s+(const|function)\s+Component\b/);
  });
});

// ---------------------------------------------------------------------------
// 9. RunCanvasNode exports nodeTypes for ReactFlow registration
// ---------------------------------------------------------------------------

describe("RunCanvasNode exports nodeTypes (RUN-243)", () => {
  it("RunCanvasNode.tsx exports a nodeTypes object", () => {
    const src = readSource("RunCanvasNode.tsx");
    expect(src).toMatch(/export\s+(const|let)\s+nodeTypes\b/);
  });
});
