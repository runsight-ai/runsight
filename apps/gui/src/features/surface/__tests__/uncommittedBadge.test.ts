/**
 * RED+GREEN tests for RUN-131: Uncommitted badge, commit dialog, and diff view.
 *
 * Source-reading tests that verify structural acceptance criteria:
 *
 * AC1: GitBadge component exists and is integrated into CanvasTopbar
 * AC2: GitBadge uses useGitStatus hook
 * AC3: Orange/warning badge when repo is not clean
 * AC4: Hidden when repo is clean
 * AC5: Click opens commit dialog
 * AC6: CommitDialog uses Dialog from component library
 * AC7: CommitDialog shows file list from uncommitted_files
 * AC8: Commit message input
 * AC9: Submit calls the explicit workflow save mutation
 * AC10: DiffView uses useGitDiff
 * AC11: Toast feedback on success/error
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

const GIT_BADGE_PATH = "features/git/GitBadge.tsx";
const COMMIT_DIALOG_PATH = "features/git/CommitDialog.tsx";
const DIFF_VIEW_PATH = "features/git/DiffView.tsx";
// ===========================================================================
// 1. GitBadge component exists (AC1)
// ===========================================================================

describe("GitBadge component exists (AC1)", () => {
  it("GitBadge.tsx file exists in git feature", () => {
    expect(
      fileExists(GIT_BADGE_PATH),
      "Expected features/git/GitBadge.tsx to exist",
    ).toBe(true);
  });

  it("exports a named GitBadge component", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+GitBadge/);
  });

});

// ===========================================================================
// 2. GitBadge uses useGitStatus (AC2)
// ===========================================================================

describe("GitBadge uses useGitStatus hook (AC2)", () => {
  it("imports useGitStatus from queries/git", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/import\s+\{[^}]*useGitStatus[^}]*\}\s+from/);
  });

  it("calls useGitStatus inside the component", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/useGitStatus\(/);
  });
});

// ===========================================================================
// 3. Orange/warning badge when not clean (AC3)
// ===========================================================================

describe("Orange/warning badge when not clean (AC3)", () => {
  it("uses Badge component from component library", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(
      /import\s+\{[^}]*Badge[^}]*\}\s+from\s+["'](@runsight\/ui\/badge|@\/components\/ui\/badge)["']/,
    );
  });

  it("uses warning variant on Badge", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/variant.*["']warning["']|warning.*variant/);
  });

  it("uses BadgeDot for dot indicator", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/BadgeDot/);
  });

  it("shows file count from uncommitted_files", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/uncommitted_files/);
  });
});

// ===========================================================================
// 4. Hidden when clean (AC4)
// ===========================================================================

describe("Hidden when repo is clean (AC4)", () => {
  it("checks is_clean from git status", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/is_clean/);
  });

  it("returns null when repo is clean", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/return\s+null/);
  });
});

// ===========================================================================
// 5. Click opens commit dialog (AC5)
// ===========================================================================

describe("Click opens commit dialog (AC5)", () => {
  it("has onClick handler or is wrapped in DialogTrigger", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/onClick|DialogTrigger/);
  });

  it("renders CommitDialog component", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/<CommitDialog/);
  });

  it("manages open state for the dialog", () => {
    const source = readSource(GIT_BADGE_PATH);
    expect(source).toMatch(/useState.*open|open.*useState|setOpen/i);
  });
});

// ===========================================================================
// 6. CommitDialog uses Dialog from library (AC6)
// ===========================================================================

describe("CommitDialog uses Dialog from component library (AC6)", () => {
  it("CommitDialog.tsx file exists", () => {
    expect(
      fileExists(COMMIT_DIALOG_PATH),
      "Expected features/git/CommitDialog.tsx to exist",
    ).toBe(true);
  });

  it("exports a named CommitDialog component", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+CommitDialog/);
  });

  it("imports Dialog components from @runsight/ui/dialog", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/import\s+\{[^}]*Dialog[^}]*\}\s+from\s+["']@runsight\/ui\/dialog["']/);
  });

  it("uses Dialog, DialogContent, DialogTitle in JSX", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/<Dialog[\s>]/);
    expect(source).toMatch(/<DialogContent/);
    expect(source).toMatch(/<DialogTitle/);
  });
});

// ===========================================================================
// 7. CommitDialog shows file list (AC7)
// ===========================================================================

describe("CommitDialog shows file list from uncommitted_files (AC7)", () => {
  it("receives or accesses uncommitted_files", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/uncommitted_files|files/);
  });

  it("maps over files to render a list", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/\.map\s*\(/);
  });
});

// ===========================================================================
// 8. Commit message input (AC8)
// ===========================================================================

describe("Commit message input (AC8)", () => {
  it("has a text input or textarea for commit message", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/<input|<textarea/);
  });

  it("manages message state", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/useState.*message|message.*useState|setMessage/i);
  });

  it("has placeholder text for commit message", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/placeholder/i);
  });
});

// ===========================================================================
// 9. Submit calls useCommit (AC9)
// ===========================================================================

describe("Submit calls explicit workflow save mutation (AC9)", () => {
  it("imports useCommitWorkflow from queries/git", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/import\s+\{[^}]*useCommitWorkflow[^}]*\}\s+from/);
  });

  it("calls useCommitWorkflow hook", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/useCommitWorkflow\(/);
  });

  it("calls the workflow save mutation on submit", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/commitWorkflow\.mutate/);
  });

  it("has a submit/commit button", () => {
    const source = readSource(COMMIT_DIALOG_PATH);
    expect(source).toMatch(/Commit|Submit/);
  });
});

// ===========================================================================
// 10. DiffView uses useGitDiff (AC10)
// ===========================================================================

describe("DiffView uses useGitDiff (AC10)", () => {
  it("DiffView.tsx file exists", () => {
    expect(
      fileExists(DIFF_VIEW_PATH),
      "Expected features/git/DiffView.tsx to exist",
    ).toBe(true);
  });

  it("exports a named DiffView component", () => {
    const source = readSource(DIFF_VIEW_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+DiffView/);
  });

  it("imports useGitDiff from queries/git", () => {
    const source = readSource(DIFF_VIEW_PATH);
    expect(source).toMatch(/import\s+\{[^}]*useGitDiff[^}]*\}\s+from/);
  });

  it("calls useGitDiff hook", () => {
    const source = readSource(DIFF_VIEW_PATH);
    expect(source).toMatch(/useGitDiff\(/);
  });

  it("renders diff in a pre or code block", () => {
    const source = readSource(DIFF_VIEW_PATH);
    expect(source).toMatch(/<pre|<code|CodeBlock/);
  });
});

// ===========================================================================
// 11. Toast feedback on success/error (AC11)
// ===========================================================================

describe("Toast feedback on success/error (AC11)", () => {
  it("useCommit hook has onSuccess with toast", () => {
    const source = readSource("queries/git.ts");
    expect(source).toMatch(/onSuccess.*toast|toast.*success/s);
  });

  it("useCommit hook has onError with toast", () => {
    const source = readSource("queries/git.ts");
    expect(source).toMatch(/onError.*toast|toast.*error/s);
  });

  it("imports toast from sonner in queries/git", () => {
    const source = readSource("queries/git.ts");
    expect(source).toMatch(/import\s+\{[^}]*toast[^}]*\}\s+from\s+["']sonner["']/);
  });
});
