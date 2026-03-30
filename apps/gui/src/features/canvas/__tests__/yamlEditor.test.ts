/**
 * RED-TEAM tests for RUN-360: T4 — YAML editor full-screen mode (Monaco, loads from API).
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Monaco renders with YAML highlighting
 * AC2: Loads content from API (useWorkflow(id) -> .yaml field)
 * AC3: Changes mark isDirty (local state)
 * AC4: Editor does not own a direct Cmd+S save path
 * AC5: Design system syntax colors (--syntax-* CSS vars)
 * AC6: Editor fills available space below topbar
 *
 * Expected failures (current state):
 *   - CanvasPage has an empty flex-1 div where the editor should go
 *   - No YAML editor component exists that wires Monaco to the API
 *   - No isDirty state tracking
 *   - No keyboard shortcut handler
 *   - No syntax theme definition using --syntax-* tokens
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
const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";

// The YAML editor component — could be a dedicated component or inline in CanvasPage.
// We check for either a YamlEditor component or Monaco usage in CanvasPage.
function getEditorSource(): string {
  // Try dedicated component first
  const candidates = [
    "features/canvas/YamlEditor.tsx",
    "features/canvas/YamlEditorPanel.tsx",
    "features/canvas/EditorPanel.tsx",
  ];
  for (const candidate of candidates) {
    if (fileExists(candidate)) {
      return readSource(candidate);
    }
  }
  // Fall back to CanvasPage itself
  return readSource(CANVAS_PAGE_PATH);
}

// ===========================================================================
// 1. Monaco renders with YAML highlighting (AC1)
// ===========================================================================

describe("Monaco renders with YAML highlighting (AC1)", () => {
  it("CanvasPage or a child component imports Monaco editor", () => {
    const source = getEditorSource();
    const hasMonaco =
      /monaco-editor|MonacoEditor|LazyMonacoEditor/.test(source);
    expect(
      hasMonaco,
      "Expected Monaco editor import (monaco-editor, MonacoEditor, or LazyMonacoEditor)",
    ).toBe(true);
  });

  it("Monaco editor is rendered in the JSX", () => {
    const source = getEditorSource();
    const rendersMonaco =
      /<MonacoEditor|<LazyMonacoEditor|<Editor/.test(source);
    expect(
      rendersMonaco,
      "Expected Monaco editor component to be rendered in JSX",
    ).toBe(true);
  });

  it("YAML language mode is set on the editor", () => {
    const source = getEditorSource();
    // Monaco accepts language prop, should be "yaml"
    expect(source).toMatch(/language\s*=\s*["']yaml["']/);
  });

  it("CanvasPage renders the editor component in the content area", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // The empty flex-1 div should now contain the editor
    const hasEditorInPage =
      /YamlEditor|LazyMonacoEditor|MonacoEditor|EditorPanel/.test(pageSource);
    expect(
      hasEditorInPage,
      "Expected CanvasPage to render the YAML editor component in its content area",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. Loads content from API — useWorkflow(id) -> .yaml field (AC2)
// ===========================================================================

describe("Loads content from API (AC2)", () => {
  it("editor component uses useWorkflow hook to fetch workflow data", () => {
    const source = getEditorSource();
    expect(source).toMatch(/useWorkflow/);
  });

  it("passes the .yaml field from workflow data to the editor value", () => {
    const source = getEditorSource();
    // Should access workflow.yaml or data.yaml and pass it as value/defaultValue
    const accessesYaml = /\.yaml\b/.test(source);
    expect(
      accessesYaml,
      "Expected .yaml field to be accessed from workflow data",
    ).toBe(true);
  });

  it("editor value prop is wired to workflow yaml content", () => {
    const source = getEditorSource();
    // Should have value={...yaml...} or defaultValue={...yaml...} on the editor
    const hasValueProp =
      /(?:value|defaultValue)\s*=\s*\{[^}]*yaml/s.test(source);
    expect(
      hasValueProp,
      "Expected editor value or defaultValue prop to reference yaml content",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Changes mark isDirty — local state (AC3)
// ===========================================================================

describe("isDirty state tracked on changes (AC3)", () => {
  it("has isDirty state variable", () => {
    const source = getEditorSource();
    const hasDirtyState = /isDirty|is_dirty|dirty/.test(source);
    expect(
      hasDirtyState,
      "Expected isDirty (or similar) state variable for tracking unsaved changes",
    ).toBe(true);
  });

  it("isDirty is set to true when editor content changes", () => {
    const source = getEditorSource();
    // Should have an onChange handler that sets dirty state
    const setsOnChange =
      /onChange|onDidChangeModelContent/.test(source) &&
      /setIsDirty|setDirty|dirty.*true/.test(source);
    expect(
      setsOnChange,
      "Expected onChange handler that marks isDirty as true",
    ).toBe(true);
  });

  it("isDirty is reset after successful save", () => {
    const source = getEditorSource();
    // After save completes, isDirty should be set back to false
    const resetsDirty = /setIsDirty\s*\(\s*false\s*\)|setDirty\s*\(\s*false\s*\)/.test(source);
    expect(
      resetsDirty,
      "Expected isDirty to be reset to false after save",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. YamlEditor does not own a direct Cmd+S save path (AC4)
// ===========================================================================

describe("YamlEditor does not own a direct save shortcut (AC4)", () => {
  it("does not register a keyboard event listener for Cmd+S / Ctrl+S", () => {
    const source = getEditorSource();
    const hasKeyHandler =
      /keydown|onKeyDown|addCommand|addAction|KeyMod/.test(source);
    expect(
      hasKeyHandler,
      "YamlEditor should not register its own keyboard save handler once save is modal-driven",
    ).toBe(false);
  });

  it("does not detect Cmd+S (Mac) and Ctrl+S (Windows/Linux)", () => {
    const source = getEditorSource();
    const detectsSaveCombo =
      /(metaKey|ctrlKey).*['"s'"]|KeyMod\.CtrlCmd|key\s*===?\s*['"]s['"]/.test(source);
    expect(
      detectsSaveCombo,
      "YamlEditor should not detect keyboard save combos directly",
    ).toBe(false);
  });

  it("does not call preventDefault for a direct save shortcut", () => {
    const source = getEditorSource();
    expect(source).not.toMatch(/preventDefault/);
  });

  it("does not import or call useUpdateWorkflow for direct keyboard save", () => {
    const source = getEditorSource();
    expect(source).not.toMatch(/useUpdateWorkflow/);
    expect(source).not.toMatch(/mutate\s*\(/);
  });
});

// ===========================================================================
// 5. Design system syntax colors — --syntax-* CSS vars (AC5)
// ===========================================================================

describe("Design system syntax colors (AC5)", () => {
  it("defines a custom Monaco theme", () => {
    const allSources = getAllEditorRelatedSources();
    const definesTheme =
      /defineTheme|editor\.defineTheme/.test(allSources);
    expect(
      definesTheme,
      "Expected monaco.editor.defineTheme() call to register custom syntax theme",
    ).toBe(true);
  });

  it("custom theme references --syntax-key CSS variable", () => {
    const allSources = getAllEditorRelatedSources();
    expect(allSources).toMatch(/--syntax-key/);
  });

  it("custom theme references --syntax-string CSS variable", () => {
    const allSources = getAllEditorRelatedSources();
    expect(allSources).toMatch(/--syntax-string/);
  });

  it("custom theme references --syntax-value CSS variable", () => {
    const allSources = getAllEditorRelatedSources();
    expect(allSources).toMatch(/--syntax-value/);
  });

  it("custom theme references --syntax-comment CSS variable", () => {
    const allSources = getAllEditorRelatedSources();
    expect(allSources).toMatch(/--syntax-comment/);
  });

  it("custom theme references --syntax-punct CSS variable", () => {
    const allSources = getAllEditorRelatedSources();
    expect(allSources).toMatch(/--syntax-punct/);
  });

  it("applies the custom theme to the editor", () => {
    const source = getEditorSource();
    // Monaco editor should have theme prop set to the custom theme name
    expect(source).toMatch(/theme\s*=\s*\{?["']/);
  });
});

// ===========================================================================
// 6. Editor fills available space below topbar (AC6)
// ===========================================================================

describe("Editor fills available space (AC6)", () => {
  it("CanvasPage content area uses flex-1 to fill remaining space", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    // The div containing the editor should have flex-1
    expect(pageSource).toMatch(/flex-1/);
  });

  it("CanvasPage has flex-col layout for vertical stacking", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/flex-col/);
  });

  it("CanvasPage root has h-full for full viewport height", () => {
    const pageSource = readSource(CANVAS_PAGE_PATH);
    expect(pageSource).toMatch(/h-full|h-screen/);
  });

  it("editor component has height 100% or fills its container", () => {
    const source = getEditorSource();
    // Monaco needs explicit height — should have height="100%" or h-full
    // AND the source must actually contain a Monaco editor (not just an empty div)
    const hasEditor = /MonacoEditor|LazyMonacoEditor|Editor/.test(source);
    const hasFullHeight =
      /height\s*=\s*["']100%["']|h-full|height:\s*['"]?100%/.test(source);
    expect(
      hasEditor && hasFullHeight,
      "Expected editor component with height='100%' or h-full to fill container",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. Save button in topbar wired to isDirty (bonus structural check)
// ===========================================================================

describe("Topbar Save button reflects dirty state", () => {
  it("CanvasTopbar accepts isDirty or onSave prop", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    const acceptsProp = /isDirty|onSave|dirty/.test(source);
    expect(
      acceptsProp,
      "Expected CanvasTopbar to accept isDirty or onSave prop for save integration",
    ).toBe(true);
  });

  it("Save placeholder is replaced with a functional button", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Should have a <button> or Button component for Save, not just a <span>
    const hasSaveButton =
      /<button[^>]*>.*Save|<Button[^>]*>.*Save/s.test(source);
    expect(
      hasSaveButton,
      "Expected Save to be a button element, not a placeholder span",
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Helpers for collecting all editor-related sources
// ---------------------------------------------------------------------------

function getAllEditorRelatedSources(): string {
  const sources: string[] = [];

  // Main editor component
  sources.push(getEditorSource());

  // Check for dedicated theme file
  const themeCandidates = [
    "features/canvas/monacoTheme.ts",
    "features/canvas/editorTheme.ts",
    "features/canvas/yamlTheme.ts",
    "features/canvas/theme.ts",
    "lib/monacoTheme.ts",
    "lib/editorTheme.ts",
  ];
  for (const candidate of themeCandidates) {
    if (fileExists(candidate)) {
      sources.push(readSource(candidate));
    }
  }

  // Also check LazyMonacoEditor
  if (fileExists("features/canvas/LazyMonacoEditor.tsx")) {
    sources.push(readSource("features/canvas/LazyMonacoEditor.tsx"));
  }

  return sources.join("\n");
}
