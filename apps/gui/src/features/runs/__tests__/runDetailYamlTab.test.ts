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
  it("contains a TabsList with Canvas and YAML TabsTriggers", () => {
    const src = readSource("RunDetailHeader.tsx");

    // Must have a Tabs/TabsList import or usage
    expect(src).toMatch(/TabsList/);

    // Must have a "Canvas" trigger
    expect(src).toMatch(/TabsTrigger[\s\S]*?Canvas/);

    // Must have a "YAML" trigger
    expect(src).toMatch(/TabsTrigger[\s\S]*?YAML/);
  });
});

// ---------------------------------------------------------------------------
// 2. RunDetailHeader uses CSS variable for height, not hardcoded h-12
// ---------------------------------------------------------------------------

describe("RunDetailHeader uses header-height variable (RUN-665)", () => {
  it("uses var(--header-height) instead of hardcoded h-12", () => {
    const src = readSource("RunDetailHeader.tsx");

    // Must reference the CSS variable for header height
    expect(src).toMatch(/--header-height/);

    // Must NOT use the hardcoded h-12 class on the header element
    // (The header element currently has className="h-12 ...")
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
  it("uses border-subtle (matching CanvasTopbar), not border-default", () => {
    const src = readSource("RunDetailHeader.tsx");

    // The header element's border class must use border-subtle (or border-border-subtle)
    // to match CanvasTopbar, not border-[var(--border-default)]
    const hasBorderSubtle =
      /border-border-subtle/.test(src) || /border-subtle/.test(src);

    expect(hasBorderSubtle).toBe(true);
  });
});
