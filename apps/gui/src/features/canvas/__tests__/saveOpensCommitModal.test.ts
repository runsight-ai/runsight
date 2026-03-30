/**
 * RED-TEAM tests for RUN-424: Save button opens commit modal (ADR-001).
 *
 * ADR-001: Save = commit to main via commit modal. Current code has
 * handleSave calling updateWorkflow.mutate() directly (PUT to disk,
 * no modal). The fix is to change handleSave to open CommitDialog
 * instead.
 *
 * AC1: handleSave sets commitDialogOpen = true (not PUT)
 * AC2: handleSave does NOT call updateWorkflow.mutate
 * AC3: Cmd+S opens commit modal (same path as Save button)
 * AC4: CommitDialog accepts onCommitSuccess callback to reset isDirty
 * AC5: CanvasPage passes isDirty-reset callback to CommitDialog
 * AC6: After commit, isDirty resets to false
 *
 * Expected failures (current state):
 *   - handleSave calls updateWorkflow.mutate({ id, data: { yaml } }) (AC1, AC2 fail)
 *   - handleSave does NOT set commitDialogOpen = true (AC1 fails)
 *   - CommitDialog has no onCommitSuccess prop (AC4 fails)
 *   - CanvasPage does not pass onCommitSuccess to CommitDialog (AC5 fails)
 *   - isDirty reset is tied to PUT onSuccess, not to commit flow (AC6 fails)
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
const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";
const COMMIT_DIALOG_PATH = "features/git/CommitDialog.tsx";

// ===========================================================================
// AC1: handleSave opens CommitDialog (sets commitDialogOpen = true)
// ===========================================================================

describe("AC1: handleSave opens CommitDialog instead of calling PUT", () => {
  it("handleSave body contains setCommitDialogOpen(true)", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Extract the handleSave function body. It should set commitDialogOpen = true.
    // Match: handleSave = useCallback(() => { ... setCommitDialogOpen(true) ... })
    // or:   function handleSave() { ... setCommitDialogOpen(true) ... }
    const handleSaveMatch = source.match(
      /handleSave\s*=\s*useCallback\(\s*\(\)\s*=>\s*\{([\s\S]*?)\}\s*,/,
    );
    expect(
      handleSaveMatch,
      "Expected handleSave defined as useCallback in CanvasPage",
    ).toBeTruthy();

    const handleSaveBody = handleSaveMatch![1];
    expect(
      handleSaveBody,
      "handleSave body must call setCommitDialogOpen(true) to open the commit modal",
    ).toMatch(/setCommitDialogOpen\s*\(\s*true\s*\)/);
  });

  it("handleSave does NOT contain updateWorkflow.mutate", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Extract handleSave body and verify it does NOT call updateWorkflow.mutate
    const handleSaveMatch = source.match(
      /handleSave\s*=\s*useCallback\(\s*\(\)\s*=>\s*\{([\s\S]*?)\}\s*,/,
    );
    expect(handleSaveMatch).toBeTruthy();

    const handleSaveBody = handleSaveMatch![1];
    expect(
      handleSaveBody,
      "handleSave must NOT call updateWorkflow.mutate — save should open the commit modal, not PUT directly",
    ).not.toMatch(/updateWorkflow\.mutate/);
  });

  it("handleSave does NOT read yamlContent from the store", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // If handleSave only opens the modal, it should not need to read yamlContent.
    // The CommitDialog handles the actual commit flow.
    const handleSaveMatch = source.match(
      /handleSave\s*=\s*useCallback\(\s*\(\)\s*=>\s*\{([\s\S]*?)\}\s*,/,
    );
    expect(handleSaveMatch).toBeTruthy();

    const handleSaveBody = handleSaveMatch![1];
    expect(
      handleSaveBody,
      "handleSave should not read yamlContent — it only opens the modal",
    ).not.toMatch(/yamlContent|getState\(\)/);
  });
});

// ===========================================================================
// AC2: handleSave does NOT call updateWorkflow.mutate anywhere in its flow
// ===========================================================================

describe("AC2: No direct PUT in the save flow", () => {
  it("handleSave dependency array does NOT include updateWorkflow", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Extract the useCallback dependency array for handleSave
    // Pattern: handleSave = useCallback(() => { ... }, [deps])
    const depMatch = source.match(
      /handleSave\s*=\s*useCallback\(\s*\(\)\s*=>\s*\{[\s\S]*?\}\s*,\s*\[([\s\S]*?)\]\s*\)/,
    );
    expect(depMatch, "Expected handleSave with useCallback and dependency array").toBeTruthy();

    const deps = depMatch![1];
    expect(
      deps,
      "handleSave deps should NOT include updateWorkflow — it no longer calls mutate",
    ).not.toMatch(/updateWorkflow/);
  });

  it("handleSave dependency array does NOT include id (not needed for opening modal)", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    const depMatch = source.match(
      /handleSave\s*=\s*useCallback\(\s*\(\)\s*=>\s*\{[\s\S]*?\}\s*,\s*\[([\s\S]*?)\]\s*\)/,
    );
    expect(depMatch).toBeTruthy();

    const deps = depMatch![1];
    // Opening a modal doesn't need the workflow id — that's a concern for CommitDialog
    expect(
      deps,
      "handleSave deps should NOT include id — opening a modal has no external deps",
    ).not.toMatch(/\bid\b/);
  });
});

// ===========================================================================
// AC3: Cmd+S opens commit modal (same path as Save button)
// ===========================================================================

describe("AC3: Cmd+S opens commit modal", () => {
  it("CanvasTopbar Cmd+S handler calls onSave (which opens the modal)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The Cmd+S handler calls onSave?.() which is handleSave from CanvasPage.
    // This test verifies the handler exists and calls onSave — the fact that
    // onSave opens the modal is verified in AC1.
    expect(
      source,
      "CanvasTopbar must have a Cmd+S handler that calls onSave",
    ).toMatch(/onSave\s*\?\.\s*\(\)/);
  });

  it("CanvasPage passes handleSave (the modal opener) as onSave to CanvasTopbar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Verify CanvasPage passes handleSave to the topbar's onSave prop.
    // Since handleSave now opens the modal, Cmd+S -> onSave -> handleSave -> modal opens.
    expect(source).toMatch(/<CanvasTopbar[^>]*onSave\s*=\s*\{handleSave\}/);
  });

  it("Save button onClick calls onSave (same function that opens modal)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The Save button's onClick should call the same onSave function
    // Pattern: onClick={onSave} on a Button that contains "Save"
    expect(source).toMatch(/onClick\s*=\s*\{onSave\}/);
  });
});

// ===========================================================================
// AC4: CommitDialog accepts onCommitSuccess callback
// ===========================================================================

describe("AC4: CommitDialog accepts onCommitSuccess callback", () => {
  it("CommitDialogProps interface includes onCommitSuccess", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    // CommitDialog should accept an onCommitSuccess callback so the parent
    // can react to a successful commit (e.g., reset isDirty).
    expect(
      source,
      "CommitDialogProps must include onCommitSuccess callback",
    ).toMatch(/onCommitSuccess\s*[?:]?\s*:\s*\(\s*\)\s*=>\s*void/);
  });

  it("CommitDialog calls onCommitSuccess after successful commit", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    // After commit.mutate succeeds, onCommitSuccess should be called.
    // Pattern: onSuccess callback that invokes onCommitSuccess
    expect(
      source,
      "CommitDialog must call onCommitSuccess in the commit onSuccess handler",
    ).toMatch(/onCommitSuccess/);
  });

  it("CommitDialog destructures onCommitSuccess from props", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    // The component function should destructure onCommitSuccess from its props
    expect(
      source,
      "CommitDialog should destructure onCommitSuccess from props",
    ).toMatch(/\{\s*[^}]*onCommitSuccess[^}]*\}\s*:\s*CommitDialogProps/);
  });
});

// ===========================================================================
// AC5: CanvasPage passes isDirty-reset callback to CommitDialog
// ===========================================================================

describe("AC5: CanvasPage passes onCommitSuccess to CommitDialog", () => {
  it("CommitDialog element receives onCommitSuccess prop", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // CanvasPage renders <CommitDialog ... onCommitSuccess={...} />
    expect(
      source,
      "CanvasPage must pass onCommitSuccess prop to <CommitDialog>",
    ).toMatch(/<CommitDialog[^>]*\bonCommitSuccess\b/);
  });

  it("onCommitSuccess callback resets isDirty to false", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The onCommitSuccess handler should call setIsDirty(false).
    // Pattern: onCommitSuccess={() => setIsDirty(false)} or a named handler.
    // We check that somewhere near the CommitDialog rendering, setIsDirty(false)
    // is connected to onCommitSuccess.
    const hasResetInCallback =
      /onCommitSuccess\s*=\s*\{[^}]*setIsDirty\s*\(\s*false\s*\)/.test(source) ||
      /onCommitSuccess\s*=\s*\{handleCommitSuccess\}/.test(source);
    expect(
      hasResetInCallback,
      "onCommitSuccess must reset isDirty to false after a successful commit",
    ).toBe(true);
  });
});

// ===========================================================================
// AC6: After commit, isDirty resets (end-to-end path verification)
// ===========================================================================

describe("AC6: isDirty reset is tied to commit flow, not to PUT", () => {
  /**
   * Helper: extract the full handleSave body by counting braces,
   * so we correctly capture nested callbacks like onSuccess.
   */
  function extractHandleSaveBody(source: string): string | null {
    const marker = source.indexOf("handleSave = useCallback(");
    if (marker === -1) return null;
    // Find the opening brace of the arrow body: () => {
    const arrowIdx = source.indexOf("=> {", marker);
    if (arrowIdx === -1) return null;
    const bodyStart = source.indexOf("{", arrowIdx);
    let depth = 0;
    let i = bodyStart;
    for (; i < source.length; i++) {
      if (source[i] === "{") depth++;
      if (source[i] === "}") depth--;
      if (depth === 0) break;
    }
    return source.slice(bodyStart + 1, i);
  }

  it("setIsDirty(false) is NOT inside handleSave", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // In the old code, setIsDirty(false) was in handleSave's onSuccess for PUT.
    // Now it should NOT be there — it belongs in the commit success path.
    const body = extractHandleSaveBody(source);
    expect(body, "Expected handleSave function body to be extractable").toBeTruthy();
    expect(
      body!,
      "setIsDirty(false) must NOT be inside handleSave — it belongs in the commit success flow",
    ).not.toMatch(/setIsDirty\s*\(\s*false\s*\)/);
  });

  it("CanvasPage does NOT use updateWorkflow for the save action", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The handleSave function should no longer use updateWorkflow at all.
    // updateWorkflow may still exist for name editing (in CanvasTopbar), but
    // CanvasPage's handleSave should NOT reference it.
    const body = extractHandleSaveBody(source);
    expect(body, "Expected handleSave function body to be extractable").toBeTruthy();
    const hasMutateCall = /\.mutate\s*\(/.test(body!);
    expect(
      hasMutateCall,
      "handleSave should NOT call any .mutate() — the commit modal handles persistence",
    ).toBe(false);
  });
});
