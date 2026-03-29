/**
 * RED-TEAM tests for RUN-358: T5 — YAML validation errors + sync indicator.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Debounce 500ms after last keystroke before validating
 * AC2: Parse YAML client-side for syntax errors -> Monaco markers
 * AC3: Syntax errors shown as red squiggly in editor (Monaco markers)
 * AC4: Sync indicator in topbar (checkmark when valid, warning when errors)
 *
 * Expected failures (current state):
 *   - YamlEditor.tsx has no validation logic
 *   - No debounce on YAML content changes
 *   - No yaml parsing for syntax errors
 *   - No Monaco markers API usage
 *   - No sync indicator in CanvasTopbar
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

/** Collect all editor and topbar related sources for broader assertions. */
function getAllValidationSources(): string {
  const sources: string[] = [];
  const candidates = [
    "features/canvas/YamlEditor.tsx",
    "features/canvas/yamlValidation.ts",
    "features/canvas/useYamlValidation.ts",
    "features/canvas/useYamlValidation.tsx",
    "features/canvas/CanvasPage.tsx",
  ];
  for (const c of candidates) {
    if (fileExists(c)) sources.push(readSource(c));
  }
  return sources.join("\n");
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const YAML_EDITOR_PATH = "features/canvas/YamlEditor.tsx";
const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. YAML parsing — imports `yaml` package for client-side validation (AC2)
// ===========================================================================

describe("YAML parsing for syntax errors (AC2)", () => {
  it("imports the yaml package (eemeli/yaml) for parsing", () => {
    const allSources = getAllValidationSources();
    // Should import yaml or { parse } from "yaml"
    const importsYaml =
      /import\s+.*from\s+["']yaml["']|require\s*\(\s*["']yaml["']\s*\)/.test(
        allSources,
      );
    expect(
      importsYaml,
      "Expected import from 'yaml' package for client-side YAML parsing",
    ).toBe(true);
  });

  it("calls yaml.parse or parse() to detect syntax errors", () => {
    const allSources = getAllValidationSources();
    // Should call parse() from the yaml package
    const callsParse =
      /yaml\.parse\s*\(|(?:^|\n)\s*parse\s*\(/.test(allSources);
    expect(
      callsParse,
      "Expected yaml.parse() or parse() call for syntax validation",
    ).toBe(true);
  });

  it("catches YAMLError from parsing to extract error details", () => {
    const allSources = getAllValidationSources();
    // Should have try/catch around parse or check for errors
    const catchesErrors =
      /catch\s*\(|YAMLError|\.errors|\.message/.test(allSources) &&
      /parse/.test(allSources);
    expect(
      catchesErrors,
      "Expected error handling around YAML parsing (try/catch or error checking)",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. Debounce 500ms after last keystroke (AC1)
// ===========================================================================

describe("Debounce 500ms after last keystroke (AC1)", () => {
  it("uses a debounce mechanism (setTimeout, useDebouncedCallback, or debounce utility)", () => {
    const allSources = getAllValidationSources();
    const hasDebounce =
      /debounce|setTimeout.*500|useDebounce|useDebouncedCallback/.test(
        allSources,
      );
    expect(
      hasDebounce,
      "Expected debounce mechanism (debounce utility, setTimeout with ~500ms, or useDebouncedCallback)",
    ).toBe(true);
  });

  it("debounce delay is approximately 500ms", () => {
    const allSources = getAllValidationSources();
    // Should have 500 as debounce delay constant
    const has500ms = /500/.test(allSources);
    expect(
      has500ms,
      "Expected 500ms debounce delay for validation",
    ).toBe(true);
  });

  it("validation is triggered from onChange or content change, not on every render", () => {
    const allSources = getAllValidationSources();
    // Should tie validation to content changes, not mount/render
    const triggeredByChange =
      /onChange|onDidChangeModelContent|contentRef|value/.test(allSources) &&
      /debounce|setTimeout/.test(allSources);
    expect(
      triggeredByChange,
      "Expected validation to be triggered by content changes with debounce, not on every render",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Monaco markers API — red squiggly underlines (AC3)
// ===========================================================================

describe("Monaco markers for syntax errors (AC3)", () => {
  it("uses monaco.editor.setModelMarkers to set error markers", () => {
    const allSources = getAllValidationSources();
    const setsMarkers = /setModelMarkers/.test(allSources);
    expect(
      setsMarkers,
      "Expected monaco.editor.setModelMarkers() call to display red squiggly underlines",
    ).toBe(true);
  });

  it("markers use MarkerSeverity.Error for syntax errors", () => {
    const allSources = getAllValidationSources();
    const usesErrorSeverity =
      /MarkerSeverity\.Error|severity.*Error|severity.*8/.test(allSources);
    expect(
      usesErrorSeverity,
      "Expected MarkerSeverity.Error for syntax error markers",
    ).toBe(true);
  });

  it("markers include startLineNumber from parsed YAML error position", () => {
    const allSources = getAllValidationSources();
    const hasLineInfo =
      /startLineNumber|lineNumber|line/.test(allSources) &&
      /setModelMarkers/.test(allSources);
    expect(
      hasLineInfo,
      "Expected markers to include line number information from YAML parse errors",
    ).toBe(true);
  });

  it("markers include error message from YAML parser", () => {
    const allSources = getAllValidationSources();
    const hasMessage =
      /message/.test(allSources) && /setModelMarkers/.test(allSources);
    expect(
      hasMessage,
      "Expected markers to include the error message from the YAML parser",
    ).toBe(true);
  });

  it("clears markers when YAML becomes valid (empty array)", () => {
    const allSources = getAllValidationSources();
    // When YAML is valid, markers should be cleared: setModelMarkers(model, owner, [])
    const clearsMarkers = /setModelMarkers\s*\([^)]*\[\s*\]/.test(allSources);
    expect(
      clearsMarkers,
      "Expected setModelMarkers called with empty array to clear markers when YAML is valid",
    ).toBe(true);
  });

  it("accesses the Monaco editor instance (editorRef or onMount callback)", () => {
    const editorSource = readSource(YAML_EDITOR_PATH);
    // Need a ref to the Monaco editor instance to call setModelMarkers
    const hasEditorRef =
      /editorRef|onMount|editorDidMount|editor\.getModel/.test(editorSource);
    expect(
      hasEditorRef,
      "Expected editor instance ref (editorRef, onMount) for Monaco markers API access",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Sync indicator in topbar — checkmark vs warning (AC4)
// ===========================================================================

describe("Sync indicator in topbar (AC4)", () => {
  it("CanvasTopbar accepts a validation state prop (e.g., yamlValid, validationErrors, syncStatus)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    const hasValidationProp =
      /yamlValid|validationErrors|syncStatus|errorCount|hasErrors|isValid/.test(
        source,
      );
    expect(
      hasValidationProp,
      "Expected CanvasTopbar to accept a validation state prop (yamlValid, validationErrors, syncStatus, etc.)",
    ).toBe(true);
  });

  it("CanvasTopbar renders a checkmark icon when YAML is valid", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    const hasCheckmark =
      /Check|CheckCircle|check-circle|CircleCheck|checkmark|✓/.test(source);
    expect(
      hasCheckmark,
      "Expected a checkmark icon (Check, CheckCircle, etc.) in topbar for valid YAML state",
    ).toBe(true);
  });

  it("CanvasTopbar renders a warning icon when YAML has errors", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    const hasWarning =
      /AlertTriangle|Warning|AlertCircle|TriangleAlert|warning|⚠/.test(source);
    expect(
      hasWarning,
      "Expected a warning icon (AlertTriangle, Warning, etc.) in topbar for YAML error state",
    ).toBe(true);
  });

  it("sync indicator conditionally switches between valid and error states", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Should have conditional rendering based on validation state
    const hasConditional =
      /yamlValid|validationErrors|syncStatus|errorCount|hasErrors|isValid/.test(
        source,
      ) && /\?/.test(source);
    expect(
      hasConditional,
      "Expected conditional rendering that switches between checkmark and warning based on validation state",
    ).toBe(true);
  });

  it("CanvasPage passes validation state from YamlEditor to CanvasTopbar", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // CanvasPage should have state for validation and pass it to topbar
    const passesValidation =
      /yamlValid|validationErrors|syncStatus|errorCount|hasErrors|isValid/.test(
        pageSource,
      );
    expect(
      passesValidation,
      "Expected CanvasPage to manage and pass validation state between YamlEditor and CanvasTopbar",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Error count display (bonus structural check)
// ===========================================================================

describe("Error count display", () => {
  it("YamlEditor exposes error count or validation errors to parent", () => {
    const editorSource = readSource(YAML_EDITOR_PATH);
    // Should have a callback prop or return validation info
    const exposesErrors =
      /onValidation|onErrors|onErrorCount|validationErrors/.test(editorSource);
    expect(
      exposesErrors,
      "Expected YamlEditor to expose validation errors to parent via callback (onValidation, onErrors, etc.)",
    ).toBe(true);
  });

  it("topbar shows the number of errors when YAML has syntax issues", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Should display error count, e.g., "3 errors" or "{count} errors"
    const showsCount =
      /error|Error/.test(source) &&
      /\d|count|length|errorCount/.test(source);
    expect(
      showsCount,
      "Expected topbar to display error count when YAML has syntax issues",
    ).toBe(true);
  });
});

// ===========================================================================
// 6. Validation cleans up on unmount
// ===========================================================================

describe("Validation cleanup", () => {
  it("debounce timer is cleaned up on unmount (clearTimeout or cleanup in useEffect)", () => {
    const allSources = getAllValidationSources();
    const cleansUp =
      /clearTimeout|return\s*\(\s*\)\s*=>|cleanup|cancel/.test(allSources) &&
      /debounce|setTimeout/.test(allSources);
    expect(
      cleansUp,
      "Expected debounce timer cleanup on unmount (clearTimeout in useEffect return)",
    ).toBe(true);
  });
});
