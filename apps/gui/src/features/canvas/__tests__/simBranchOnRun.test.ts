/**
 * RED-TEAM tests for RUN-423: Wire sim branch creation on dirty run.
 *
 * ADR-001 requires: if dirty, create sim branch first, commit YAML there,
 * then run from that sim branch. If clean, run from main.
 *
 * Source-reading tests that verify:
 *   AC1: gitApi has a createSimBranch method
 *   AC2: RunButton or CanvasPage reads isDirty from store for branch decision
 *   AC3: Run flow checks dirty state before creating run
 *   AC4: Run with dirty state calls sim branch creation
 *   AC5: Run passes branch and source to createRun
 *
 * All tests are expected to FAIL because:
 *   - gitApi has no createSimBranch method
 *   - RunButton does not read isDirty or call createSimBranch
 *   - createRun is called with { workflow_id, source: "manual" } only — no branch
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
// Paths
// ---------------------------------------------------------------------------

const GIT_API_PATH = "api/git.ts";
const RUN_BUTTON_PATH = "features/canvas/RunButton.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

// ===========================================================================
// 1. gitApi has a createSimBranch method (AC1)
// ===========================================================================

describe("gitApi.createSimBranch exists (RUN-423 AC1)", () => {
  it("gitApi exports a createSimBranch method", () => {
    const source = readSource(GIT_API_PATH);
    expect(source).toMatch(/createSimBranch\s*:/);
  });

  it("createSimBranch calls POST /git/sim-branch", () => {
    const source = readSource(GIT_API_PATH);
    expect(source).toMatch(/\/git\/sim-branch/);
  });

  it("createSimBranch accepts workflow_id and yaml_content parameters", () => {
    const source = readSource(GIT_API_PATH);
    // Should have workflow_id and yaml_content in the function body
    expect(source).toMatch(/workflow_id/);
    expect(source).toMatch(/yaml_content/);
  });

  it("createSimBranch returns an object with branch and commit_sha", () => {
    const source = readSource(GIT_API_PATH);
    // The response should be parsed/typed to include branch + commit_sha
    expect(source).toMatch(/branch/);
    expect(source).toMatch(/commit_sha/);
  });
});

// ===========================================================================
// 2. RunButton reads isDirty for branch decision (AC2)
// ===========================================================================

describe("RunButton reads isDirty for branch decision (RUN-423 AC2)", () => {
  it("RunButton reads isDirty from canvas store or props", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/isDirty/);
  });

  it("RunButton imports or accesses gitApi for sim branch creation", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/gitApi|createSimBranch|useCreateSimBranch/);
  });
});

// ===========================================================================
// 3. Run flow checks dirty state before creating run (AC3)
// ===========================================================================

describe("Run flow checks dirty state before creating run (RUN-423 AC3)", () => {
  it("handleClick or run handler checks isDirty before calling createRun", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should have conditional logic: if dirty → sim branch, else → direct run
    const hasDirtyCheck = /isDirty/.test(source) && /createRun/.test(source);
    expect(
      hasDirtyCheck,
      "Expected isDirty check in the same file as createRun call",
    ).toBe(true);
  });

  it("clean state runs from main branch directly", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // When not dirty, should pass branch: "main" or omit branch
    expect(source).toMatch(/branch.*main|"main"/);
  });

  it("dirty state triggers sim branch creation before run", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should call createSimBranch or gitApi.createSimBranch when dirty
    expect(source).toMatch(/createSimBranch/);
  });
});

// ===========================================================================
// 4. Run with dirty state calls sim branch creation (AC4)
// ===========================================================================

describe("Dirty run creates sim branch (RUN-423 AC4)", () => {
  it("passes yamlContent to sim branch creation", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/yamlContent|yaml_content/);
  });

  it("passes workflowId to sim branch creation", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should pass workflow_id to createSimBranch
    const hasWorkflowIdInSimBranch =
      /createSimBranch.*workflow|simBranch.*workflow/s.test(source);
    expect(
      hasWorkflowIdInSimBranch,
      "Expected workflowId passed to sim branch creation",
    ).toBe(true);
  });

  it("waits for sim branch result before calling createRun", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should use await or .then() chaining: createSimBranch → createRun
    const hasAsyncChain =
      /await.*createSimBranch|createSimBranch.*\.then/.test(source);
    expect(
      hasAsyncChain,
      "Expected async chain: createSimBranch then createRun",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Run passes branch and source to createRun (AC5)
// ===========================================================================

describe("createRun receives branch from sim branch result (RUN-423 AC5)", () => {
  it("createRun payload includes branch field", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The mutate call should include branch in the payload
    // Current code: createRun.mutate({ workflow_id: workflowId, source: "manual" })
    // Expected:     createRun.mutate({ workflow_id: workflowId, source: "sim", branch: result.branch })
    expect(source).toMatch(/mutate\([^)]*branch/s);
  });

  it("dirty run sets source to 'sim' instead of 'manual'", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // When running from a sim branch, source should be "sim"
    expect(source).toMatch(/source.*["']sim["']|["']sim["'].*source/);
  });

  it("CanvasPage handleRun also handles dirty/sim branch flow", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // CanvasPage has its own handleRun — it should also check isDirty
    const hasDirtyRunLogic =
      /isDirty/.test(source) && /createSimBranch|simBranch|sim.branch/.test(source);
    expect(
      hasDirtyRunLogic,
      "Expected CanvasPage handleRun to include sim branch logic for dirty state",
    ).toBe(true);
  });
});
