/**
 * RED-TEAM tests for RUN-422: Wire CommitDialog reachable from banner Save link.
 *
 * These tests verify the wiring acceptance criteria by reading source files
 * and asserting observable properties:
 *
 * AC1: CanvasPage imports and renders CommitDialog
 * AC2: CanvasPage has state to control CommitDialog open/close
 * AC3: UncommittedBanner does NOT navigate to /settings (no <Link to="/settings">)
 * AC4: UncommittedBanner triggers CommitDialog via callback prop or click handler
 * AC5: CommitDialog is functional (sanity — should already pass)
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
const BANNER_PATH = "features/canvas/UncommittedBanner.tsx";
const COMMIT_DIALOG_PATH = "features/git/CommitDialog.tsx";

// ===========================================================================
// AC1: CanvasPage imports and renders CommitDialog
// ===========================================================================

describe("CanvasPage imports and renders CommitDialog (AC1)", () => {
  it("imports CommitDialog from the git feature", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(
      source,
      "CanvasPage must import CommitDialog from features/git/CommitDialog",
    ).toMatch(/import\s+\{[^}]*CommitDialog[^}]*\}\s+from\s+["'][^"']*CommitDialog["']/);
  });

  it("renders <CommitDialog in JSX", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(
      source,
      "CanvasPage must render <CommitDialog ... /> somewhere in its JSX",
    ).toMatch(/<CommitDialog[\s/>]/);
  });

  it("passes open prop to CommitDialog", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(
      source,
      "CanvasPage must pass an 'open' prop to CommitDialog",
    ).toMatch(/<CommitDialog[^>]*\bopen[=\s{]/);
  });

  it("passes onOpenChange prop to CommitDialog", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(
      source,
      "CanvasPage must pass an 'onOpenChange' prop to CommitDialog",
    ).toMatch(/<CommitDialog[^>]*\bonOpenChange[=\s{]/);
  });

  it("passes files prop to CommitDialog", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(
      source,
      "CanvasPage must pass a 'files' prop to CommitDialog",
    ).toMatch(/<CommitDialog[^>]*\bfiles[=\s{]/);
  });
});

// ===========================================================================
// AC2: CanvasPage has state to control CommitDialog open/close
// ===========================================================================

describe("CanvasPage has CommitDialog open/close state (AC2)", () => {
  it("has useState for commit dialog open state", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should have something like useState(false) for commitDialogOpen or similar
    expect(
      source,
      "CanvasPage must have a useState for controlling CommitDialog visibility",
    ).toMatch(/useState.*commit|commit.*useState/i);
  });

  it("has a handler or setter to open the commit dialog", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should have a function/callback that sets commit dialog state to true
    expect(
      source,
      "CanvasPage must have a way to open the commit dialog (setter or handler)",
    ).toMatch(/setCommitDialog|commitDialog.*true|openCommitDialog|handleOpenCommit|handleCommit/i);
  });
});

// ===========================================================================
// AC3: UncommittedBanner does NOT navigate to /settings
// ===========================================================================

describe("UncommittedBanner does not navigate to /settings (AC3)", () => {
  it("does NOT contain a Link to /settings", () => {
    const source = readSource(BANNER_PATH);
    // The current code has <Link to="/settings"> which must be removed
    expect(
      source,
      "UncommittedBanner must NOT contain <Link to=\"/settings\"> — it should open CommitDialog instead",
    ).not.toMatch(/to=["']\/settings["']/);
  });

  it("does NOT import Link from react-router", () => {
    const source = readSource(BANNER_PATH);
    // If there's no Link usage, the import should also be removed
    // Allow the import to remain only if Link is used for something else
    const hasLinkImport = /import\s+\{[^}]*\bLink\b[^}]*\}\s+from\s+["']react-router["']/.test(source);
    const hasLinkToSettings = /to=["']\/settings["']/.test(source);
    expect(
      hasLinkImport && hasLinkToSettings,
      "UncommittedBanner must not use Link to navigate to /settings",
    ).toBe(false);
  });
});

// ===========================================================================
// AC4: UncommittedBanner triggers CommitDialog via callback or click handler
// ===========================================================================

describe("UncommittedBanner triggers CommitDialog opening (AC4)", () => {
  it("uses a button (not a Link) for the commit action", () => {
    const source = readSource(BANNER_PATH);
    // The "Commit" text must be inside a <button> or element with onClick,
    // not inside a <Link> component. Find the Commit action and verify it's
    // NOT wrapped in a Link.
    const commitLinkPattern = /<Link[^>]*>[\s\S]*?Commit[\s\S]*?<\/Link>/;
    const commitButtonPattern = /<button[^>]*onClick[^>]*>[\s\S]*?Commit|onClick[^>]*>[\s\S]*?Commit/;
    const usesLink = commitLinkPattern.test(source);
    const usesButton = commitButtonPattern.test(source);
    expect(
      usesLink,
      "UncommittedBanner must NOT use <Link> for the Commit action",
    ).toBe(false);
    expect(
      usesButton,
      "UncommittedBanner must use a <button> with onClick for the Commit action",
    ).toBe(true);
  });

  it("accepts a callback prop for opening commit dialog", () => {
    const source = readSource(BANNER_PATH);
    // Component should accept a prop like onCommitClick, onOpenCommit, or onSave
    expect(
      source,
      "UncommittedBanner should accept a callback prop (e.g. onCommitClick) in its props/signature",
    ).toMatch(/onCommit|onOpenCommit|onSave/);
  });

  it("CanvasPage passes commit-open callback to UncommittedBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // CanvasPage must pass a callback to UncommittedBanner
    expect(
      source,
      "CanvasPage must pass a callback prop to <UncommittedBanner> for opening CommitDialog",
    ).toMatch(/<UncommittedBanner[^/>]*\b(onCommit|onOpenCommit|onSave)\b/);
  });
});

// ===========================================================================
// AC5: CommitDialog is functional (sanity — should already pass)
// ===========================================================================

describe("CommitDialog is functional (AC5 — sanity)", () => {
  it("exports CommitDialog component", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/export\s+function\s+CommitDialog/);
  });

  it("accepts open, onOpenChange, and files props", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/open:\s*boolean/);
    expect(source).toMatch(/onOpenChange:\s*\(open:\s*boolean\)\s*=>\s*void/);
    expect(source).toMatch(/files:\s*FileStatus\[\]/);
  });

  it("uses useCommit hook for git operations", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/useCommit\(/);
  });

  it("renders DiffView for showing diffs", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/<DiffView/);
  });

  it("has a commit message textarea", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/<textarea/);
  });

  it("has submit handler that calls commit.mutate", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/commit\.mutate/);
  });
});
