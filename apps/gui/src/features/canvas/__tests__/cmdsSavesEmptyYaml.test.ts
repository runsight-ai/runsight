/**
 * RED-TEAM tests for RUN-418: Fix CanvasPage Cmd+S saves empty YAML.
 *
 * Bug: CanvasPage has its own keydown handler that saves yamlRef.current,
 * which is initialized to "" and never populated — so Cmd+S sends empty
 * YAML to the API, potentially wiping the workflow.
 *
 * Fix: Remove CanvasPage's keydown handler entirely. Let YamlEditor own
 * Cmd+S. Add yamlContent/setYamlContent to useCanvasStore. Save button
 * reads from store, not from a local ref.
 *
 * AC1: Only one Cmd+S handler exists (in YamlEditor, not CanvasPage)
 * AC2: Cmd+S never sends empty YAML
 * AC3: Save button uses same path as Cmd+S (reads from store, not yamlRef)
 *
 * Expected failures (current state):
 *   - CanvasPage has its own keydown handler for Cmd+S (AC1 fails)
 *   - CanvasPage uses yamlRef (initialized to "") for saving (AC2 fails)
 *   - useCanvasStore does not have yamlContent or setYamlContent (AC3 fails)
 *   - handleSave reads from yamlRef.current, not from store (AC3 fails)
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

const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const YAML_EDITOR_PATH = "features/canvas/YamlEditor.tsx";
const CANVAS_STORE_PATH = "store/canvas.ts";

// ===========================================================================
// AC1: Only one Cmd+S handler — in YamlEditor, not CanvasPage
// ===========================================================================

describe("AC1: Single Cmd+S handler lives in YamlEditor only", () => {
  it("CanvasPage does NOT register a keydown listener", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // CanvasPage should not add its own window keydown event listener.
    // The Cmd+S handler should live only in YamlEditor.
    const hasKeydownListener =
      /addEventListener\s*\(\s*["']keydown["']/.test(source);
    expect(
      hasKeydownListener,
      "CanvasPage should NOT have its own keydown event listener — YamlEditor owns Cmd+S",
    ).toBe(false);
  });

  it("CanvasPage does NOT have a useEffect that handles Cmd+S / Ctrl+S", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // CanvasPage should not contain the metaKey/ctrlKey + "s" pattern
    const hasCmdSLogic =
      /metaKey.*key\s*===?\s*["']s["']/.test(source) ||
      /ctrlKey.*key\s*===?\s*["']s["']/.test(source);
    expect(
      hasCmdSLogic,
      "CanvasPage should NOT contain Cmd+S / Ctrl+S detection logic",
    ).toBe(false);
  });

  it("YamlEditor still has its own Cmd+S handler (sanity check)", () => {
    const source = readSource(YAML_EDITOR_PATH);
    const hasCmdS =
      /metaKey.*key\s*===?\s*["']s["']/.test(source) ||
      /ctrlKey.*key\s*===?\s*["']s["']/.test(source);
    expect(
      hasCmdS,
      "YamlEditor should retain its Cmd+S handler",
    ).toBe(true);
  });
});

// ===========================================================================
// AC2: Cmd+S never sends empty YAML — yamlRef pattern removed
// ===========================================================================

describe("AC2: No yamlRef pattern that could send empty YAML", () => {
  it("CanvasPage does NOT declare a yamlRef", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The yamlRef = useRef("") pattern is the root cause of the bug.
    // It's initialized to "" and never updated, so saving sends empty YAML.
    const hasYamlRef = /\byamlRef\b/.test(source);
    expect(
      hasYamlRef,
      'CanvasPage should NOT have yamlRef (was initialized to "" and never populated)',
    ).toBe(false);
  });

  it("CanvasPage handleSave does NOT read from yamlRef.current", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The handleSave that sends { yaml: yamlRef.current } is the bug.
    const readsYamlRef = /yamlRef\.current/.test(source);
    expect(
      readsYamlRef,
      "handleSave should NOT read from yamlRef.current (always empty)",
    ).toBe(false);
  });

  it("no mutation call passes yamlRef.current as the yaml value", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Specifically: { yaml: yamlRef.current } in a mutate call
    const hasBuggyMutation = /yaml\s*:\s*yamlRef\.current/.test(source);
    expect(
      hasBuggyMutation,
      "Mutation should NOT use yamlRef.current as the yaml payload",
    ).toBe(false);
  });
});

// ===========================================================================
// AC3: Save button uses store — useCanvasStore has yamlContent
// ===========================================================================

describe("AC3: useCanvasStore exports yamlContent and setYamlContent", () => {
  it("canvas store interface includes yamlContent field", () => {
    const source = readSource(CANVAS_STORE_PATH);
    const hasYamlContent = /\byamlContent\b\s*:/.test(source);
    expect(
      hasYamlContent,
      "useCanvasStore should have a yamlContent field for sharing YAML state",
    ).toBe(true);
  });

  it("canvas store interface includes setYamlContent action", () => {
    const source = readSource(CANVAS_STORE_PATH);
    const hasSetYamlContent = /\bsetYamlContent\b\s*:/.test(source);
    expect(
      hasSetYamlContent,
      "useCanvasStore should have a setYamlContent action",
    ).toBe(true);
  });

  it("canvas store interface includes blockCount field", () => {
    const source = readSource(CANVAS_STORE_PATH);
    const hasBlockCount = /\bblockCount\b\s*:/.test(source);
    expect(
      hasBlockCount,
      "useCanvasStore should have a blockCount field (per design decision)",
    ).toBe(true);
  });
});

describe("AC3: CanvasPage save reads yamlContent from store", () => {
  it("CanvasPage imports or reads yamlContent from useCanvasStore", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // CanvasPage should access yamlContent from the store for saving.
    // Patterns: useCanvasStore(s => s.yamlContent) or useCanvasStore.getState().yamlContent
    const readsFromStore =
      /useCanvasStore[\s\S]*?yamlContent/.test(source) ||
      /getState\(\)\.yamlContent/.test(source);
    expect(
      readsFromStore,
      "CanvasPage should read yamlContent from useCanvasStore for saving",
    ).toBe(true);
  });

  it("CanvasPage handleSave sends yamlContent (not yamlRef) to the mutation", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The save mutation should use yamlContent from the store.
    // Pattern: { yaml: yamlContent } or similar, NOT { yaml: yamlRef.current }
    const usesStoreForSave = /yaml\s*:\s*(?:yamlContent|getState\(\)\.yamlContent)/.test(source);
    expect(
      usesStoreForSave,
      "handleSave should pass yamlContent from store as the yaml payload",
    ).toBe(true);
  });
});

// ===========================================================================
// Integration: YamlEditor syncs content to the store
// ===========================================================================

describe("AC3: YamlEditor syncs content to canvas store", () => {
  it("YamlEditor imports or accesses useCanvasStore", () => {
    const source = readSource(YAML_EDITOR_PATH);
    const importsStore = /useCanvasStore/.test(source);
    expect(
      importsStore,
      "YamlEditor should import useCanvasStore to sync yamlContent",
    ).toBe(true);
  });

  it("YamlEditor calls setYamlContent on change", () => {
    const source = readSource(YAML_EDITOR_PATH);
    const callsSetYamlContent = /setYamlContent/.test(source);
    expect(
      callsSetYamlContent,
      "YamlEditor should call setYamlContent when editor content changes",
    ).toBe(true);
  });
});
