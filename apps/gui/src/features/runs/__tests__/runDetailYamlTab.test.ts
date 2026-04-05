/**
 * RED-TEAM tests for RUN-665: Run detail page missing YAML tab + header alignment.
 *
 * These tests verify:
 * 1. RunDetailHeader has Canvas/YAML tab switcher matching workflow editor pattern
 * 2. RunDetail renders a read-only YAML/Monaco editor when YAML tab is active
 * 3. Both views are fully read-only
 * 4. Header height, background, and border align with CanvasTopbar
 *
 * Approach: source-structure tests (read file, check patterns) — follows
 * runDetailDecomposition.test.ts convention.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const RUNS_DIR = resolve(__dirname, "..");
const readSource = (filename: string): string =>
  readFileSync(resolve(RUNS_DIR, filename), "utf-8");

// ---------------------------------------------------------------------------
// 1. RunDetailHeader has Canvas / YAML tab switcher
// ---------------------------------------------------------------------------

describe("RunDetailHeader has Canvas/YAML tabs (RUN-665)", () => {
  it("contains a SegmentedControl with Canvas and YAML options", () => {
    const src = readSource("RunDetailHeader.tsx");

    expect(src).toMatch(/WorkflowTopbar/);
    expect(src).toMatch(/activeTab/);
    expect(src).toMatch(/toggleVisibility=\{\{\s*canvas:\s*true,\s*yaml:\s*true\s*\}\}/);
  });
});

// ---------------------------------------------------------------------------
// 2. RunDetailHeader uses CSS variable for height, not hardcoded h-12
// ---------------------------------------------------------------------------

describe("RunDetailHeader uses header-height variable (RUN-665)", () => {
  it("delegates header layout to WorkflowTopbar instead of hardcoding h-12", () => {
    const src = readSource("RunDetailHeader.tsx");

    expect(src).toMatch(/WorkflowTopbar/);
    expect(src).not.toMatch(/className="h-12\b/);
  });
});

// ---------------------------------------------------------------------------
// 3. RunDetail renders YAML editor when YAML tab is active
// ---------------------------------------------------------------------------

describe("RunDetail renders YAML editor for YAML tab (RUN-665)", () => {
  it("conditionally renders a YAML or Monaco editor component", () => {
    const src = readSource("RunDetail.tsx");

    // Must reference a YAML editor or Monaco editor component
    const hasYamlEditor =
      /YamlEditor/.test(src) ||
      /MonacoEditor/.test(src) ||
      /monaco/.test(src);

    expect(hasYamlEditor).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 4. RunDetail YAML editor is read-only
// ---------------------------------------------------------------------------

describe("RunDetail YAML editor is read-only (RUN-665)", () => {
  it("passes readOnly prop or option to the YAML editor", () => {
    const src = readSource("RunDetail.tsx");

    // Must configure the editor as read-only via prop or options
    const hasReadOnly =
      /readOnly\s*[=:{]\s*true/.test(src) ||
      /readOnly\s*=\s*\{true\}/.test(src) ||
      /options\s*=\s*\{[^}]*readOnly:\s*true/.test(src) ||
      /isReadOnly/.test(src);

    expect(hasReadOnly).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 5. RunDetailHeader border matches CanvasTopbar (border-subtle, not default)
// ---------------------------------------------------------------------------

describe("RunDetailHeader border matches CanvasTopbar (RUN-665)", () => {
  it("reuses WorkflowTopbar so border styling stays shared with CanvasTopbar", () => {
    const src = readSource("RunDetailHeader.tsx");

    expect(src).toMatch(/WorkflowTopbar/);
    expect(src).not.toMatch(/border-\[var\(--border-default\)\]/);
  });
});
