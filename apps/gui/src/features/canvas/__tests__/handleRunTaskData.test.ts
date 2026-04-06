/**
 * RED-TEAM tests for RUN-736: CanvasPage.handleRun missing task_data.instruction
 *
 * Source-reading pattern: read .tsx source files as strings and assert on
 * their content — no DOM rendering required.
 *
 * Bug:
 *   CanvasPage.handleRun() calls createRun.mutate() WITHOUT task_data.
 *   RunButton.handleClick() correctly sends { instruction: "Execute workflow" }.
 *   The backend raises ValueError when task_data["instruction"] is absent,
 *   causing the "save API key → run" onboarding path to produce a failed run.
 *
 * AC:
 *   AC1: handleRun() includes task_data.instruction in BOTH createRun.mutate()
 *        call sites (simulation branch AND manual branch).
 *   AC2: The task_data value in handleRun matches RunButton's taskData constant
 *        — no divergence between the two entry points.
 *
 * All tests are expected to FAIL on the current source because handleRun does
 * not yet pass task_data to createRun.mutate().
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
const RUN_BUTTON_PATH = "features/canvas/RunButton.tsx";

// ===========================================================================
// 1. handleRun simulation branch includes task_data (AC1)
// ===========================================================================

describe("CanvasPage.handleRun simulation branch includes task_data (RUN-736 AC1)", () => {
  it("handleRun passes task_data to createRun.mutate in the simulation branch", () => {
    const source = readSource(CANVAS_PAGE_PATH);

    // Find the handleRun function body.  We look for the simulation path:
    // createRun.mutate({ workflow_id: id!, source: "simulation", branch: ... })
    // and require task_data to appear alongside source: "simulation".
    //
    // The regex anchors on the simulation call-site and demands task_data
    // somewhere inside the same object literal before the closing brace.
    const simBranchHasTaskData =
      /createRun\.mutate\(\s*\{[^}]*source:\s*["']simulation["'][^}]*task_data[^}]*\}/s.test(
        source,
      ) ||
      /createRun\.mutate\(\s*\{[^}]*task_data[^}]*source:\s*["']simulation["'][^}]*\}/s.test(
        source,
      );

    expect(
      simBranchHasTaskData,
      "Expected handleRun simulation branch to include task_data in createRun.mutate() payload",
    ).toBe(true);
  });

  it("handleRun simulation branch payload contains instruction field", () => {
    const source = readSource(CANVAS_PAGE_PATH);

    // The instruction field must appear somewhere inside handleRun's simulation
    // createRun.mutate call.  We detect the simulation context first, then look
    // for instruction nearby.
    const hasInstruction =
      /source:\s*["']simulation["'][\s\S]{0,300}instruction/.test(source) ||
      /instruction[\s\S]{0,300}source:\s*["']simulation["']/.test(source);

    expect(
      hasInstruction,
      "Expected handleRun simulation branch to include instruction in task_data",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. handleRun manual branch includes task_data (AC1)
// ===========================================================================

describe("CanvasPage.handleRun manual branch includes task_data (RUN-736 AC1)", () => {
  it("handleRun passes task_data to createRun.mutate in the manual branch", () => {
    const source = readSource(CANVAS_PAGE_PATH);

    const manualBranchHasTaskData =
      /createRun\.mutate\(\s*\{[^}]*source:\s*["']manual["'][^}]*task_data[^}]*\}/s.test(
        source,
      ) ||
      /createRun\.mutate\(\s*\{[^}]*task_data[^}]*source:\s*["']manual["'][^}]*\}/s.test(
        source,
      );

    expect(
      manualBranchHasTaskData,
      "Expected handleRun manual branch to include task_data in createRun.mutate() payload",
    ).toBe(true);
  });

  it("handleRun manual branch payload contains instruction field", () => {
    const source = readSource(CANVAS_PAGE_PATH);

    const hasInstruction =
      /source:\s*["']manual["'][\s\S]{0,300}instruction/.test(source) ||
      /instruction[\s\S]{0,300}source:\s*["']manual["']/.test(source);

    expect(
      hasInstruction,
      "Expected handleRun manual branch to include instruction in task_data",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. No divergence — handleRun and RunButton use identical instruction (AC2)
// ===========================================================================

describe("handleRun and RunButton use the same instruction string (RUN-736 AC2)", () => {
  it("RunButton defines a taskData constant with instruction: 'Execute workflow'", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Canonical value established by RunButton — this must pass now and after fix.
    expect(source).toMatch(
      /taskData\s*=\s*\{\s*instruction:\s*["']Execute workflow["']/,
    );
  });

  it("CanvasPage.handleRun uses the same instruction string as RunButton", () => {
    const canvasSource = readSource(CANVAS_PAGE_PATH);
    const runButtonSource = readSource(RUN_BUTTON_PATH);

    // Extract the instruction value from RunButton (ground truth).
    const runButtonMatch = runButtonSource.match(
      /taskData\s*=\s*\{[^}]*instruction:\s*["']([^"']+)["']/,
    );
    expect(
      runButtonMatch,
      "Could not extract instruction value from RunButton.tsx",
    ).toBeTruthy();
    const canonicalInstruction = runButtonMatch![1];

    // CanvasPage must contain the same string literal within handleRun.
    // We look for the canonical instruction value appearing in a context that
    // also references createRun.mutate — confirming it is wired into the call.
    const canvasHasInstruction = canvasSource.includes(
      `"${canonicalInstruction}"`,
    ) || canvasSource.includes(`'${canonicalInstruction}'`);

    expect(
      canvasHasInstruction,
      `Expected CanvasPage to use the same instruction as RunButton: "${canonicalInstruction}"`,
    ).toBe(true);
  });

  it("CanvasPage.handleRun instruction is wired into a createRun.mutate call", () => {
    const source = readSource(CANVAS_PAGE_PATH);

    // The instruction must appear inside a createRun.mutate argument, not just
    // as a standalone comment or string.  We look for instruction within 400
    // characters of a createRun.mutate( opening.
    const mutateWithInstruction =
      /createRun\.mutate\([\s\S]{0,400}instruction/.test(source);

    expect(
      mutateWithInstruction,
      "Expected instruction to appear inside a createRun.mutate() call in handleRun",
    ).toBe(true);
  });
});
