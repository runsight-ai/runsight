/**
 * RED-TEAM tests for RUN-595: Make fork an in-place WorkflowSurface
 * mode transition.
 *
 * Currently, `useForkWorkflow` creates a new workflow then calls
 * `navigate("/workflows/:id/edit")` — a full route change that mounts
 * a completely different page product. RUN-595 changes this so fork
 * is an in-place mode transition on the existing WorkflowSurface:
 *
 *   historical → fork-draft (same surface, mode prop changes)
 *
 * Tests verify:
 * 1. useForkWorkflow does NOT call navigate() after forking — the
 *    in-place transition replaces the old navigation approach
 * 2. useForkWorkflow returns/invokes a mode-transition callback that
 *    changes the surface from historical to fork-draft
 * 3. useForkWorkflow provides the new workflow ID for the surface to
 *    adopt after the fork
 * 4. WorkflowSurface accepts an onFork callback (or mode-transition
 *    mechanism) that updates mode and workflowId without remounting
 * 5. Fork-draft mode activates editing: palette interactive, canvas
 *    editable, save available — verified via the existing contract
 * 6. Edge cases: fork from failed run, snapshot unavailable prevents
 *    fork, route updates without surface reset
 *
 * Expected failures: useForkWorkflow still calls navigate() and has
 * no in-place transition wiring. WorkflowSurface does not yet accept
 * a fork-transition mechanism.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers — source analysis
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  const fullPath = resolve(SRC_DIR, relativePath);
  if (!existsSync(fullPath)) return "";
  return readFileSync(fullPath, "utf-8");
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const FORK_HOOK_PATH = "features/runs/useForkWorkflow.ts";
const FORK_HOOK_PATH_TSX = "features/runs/useForkWorkflow.tsx";
const WORKFLOW_SURFACE_PATH = "features/canvas/WorkflowSurface.tsx";
const CONTRACT_PATH = "features/canvas/workflowSurfaceContract.ts";
const ROUTES_PATH = "routes/index.tsx";

function readForkHook(): string {
  return [
    readSource(FORK_HOOK_PATH),
    readSource(FORK_HOOK_PATH_TSX),
  ].join("\n");
}

// ===========================================================================
// 1. useForkWorkflow no longer calls navigate() — in-place transition
// ===========================================================================

describe("useForkWorkflow does not navigate away after fork (RUN-595 AC1)", () => {
  it("does not import useNavigate from react-router", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // After RUN-595, navigate is replaced by in-place mode transition
    expect(src).not.toMatch(/import\s*\{[^}]*useNavigate[^}]*\}\s*from\s*["']react-router["']/);
  });

  it("does not call navigate() with a /workflows route", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // The old pattern: navigate(`/workflows/${result.id}/edit`)
    // should no longer exist after the in-place transition change
    expect(src).not.toMatch(/navigate\s*\(\s*[`"']\/workflows\//);
  });

  it("does not call navigate() at all in the fork execution path", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // navigate should not be referenced anywhere in the fork hook
    expect(src).not.toMatch(/\bnavigate\s*\(/);
  });
});

// ===========================================================================
// 2. useForkWorkflow accepts an onTransition callback for mode change
// ===========================================================================

describe("useForkWorkflow accepts an in-place transition callback (RUN-595 AC1 + AC2)", () => {
  it("accepts an onTransition or onForkComplete callback in its options", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // The hook should accept a callback that WorkflowSurface provides
    // to trigger mode change after fork completes
    const hasTransitionCallback =
      /onTransition/.test(src) ||
      /onForkComplete/.test(src) ||
      /onModeChange/.test(src);
    expect(
      hasTransitionCallback,
      "Expected useForkWorkflow to accept an onTransition/onForkComplete/onModeChange callback",
    ).toBe(true);
  });

  it("invokes the transition callback with the new workflow ID after successful fork", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // After creating the workflow via API, the hook should invoke the
    // callback with the new workflow's ID so the surface can adopt it
    const invokesWithId =
      /onTransition\s*\(\s*\{?.*result\.id|onTransition\(.*id/.test(src) ||
      /onForkComplete\s*\(\s*\{?.*result\.id|onForkComplete\(.*id/.test(src) ||
      /onModeChange\s*\(\s*\{?.*result\.id|onModeChange\(.*id/.test(src);
    expect(
      invokesWithId,
      "Expected transition callback to be invoked with the new workflow ID",
    ).toBe(true);
  });

  it("provides the new workflow ID in its return value or via callback", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // Either the return object includes forkedWorkflowId, or the callback
    // receives it — the surface needs the new ID to update its state
    const providesNewId =
      /forkedWorkflowId/.test(src) ||
      /newWorkflowId/.test(src) ||
      /forkResult/.test(src) ||
      (/onTransition|onForkComplete|onModeChange/.test(src) &&
       /result\.id/.test(src));
    expect(
      providesNewId,
      "Expected useForkWorkflow to provide the forked workflow ID to the caller",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. WorkflowSurface supports in-place fork transition
// ===========================================================================

describe("WorkflowSurface supports fork mode transition (RUN-595 AC1 + AC3)", () => {
  it("WorkflowSurface manages mode as mutable state, not just a static prop", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    expect(src.length).toBeGreaterThan(0);
    // The surface needs internal state for mode so it can transition
    // from historical to fork-draft without a remount
    const hasModeState =
      /useState.*mode|useState<WorkflowSurfaceMode>/.test(src) ||
      /\[.*mode.*,\s*set.*[Mm]ode\]/.test(src);
    expect(
      hasModeState,
      "Expected WorkflowSurface to manage mode as mutable useState, not just a prop",
    ).toBe(true);
  });

  it("WorkflowSurface manages workflowId as mutable state for fork adoption", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    expect(src.length).toBeGreaterThan(0);
    // After fork, the workflowId must change from the original to the
    // new fork — this requires mutable state
    const hasWorkflowIdState =
      /useState.*workflowId|useState<string>/.test(src) ||
      /\[.*workflowId.*,\s*set.*[Ww]orkflowId\]/.test(src);
    expect(
      hasWorkflowIdState,
      "Expected WorkflowSurface to manage workflowId as mutable state for fork adoption",
    ).toBe(true);
  });

  it("defines a handleForkTransition (or equivalent) that sets mode to fork-draft", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    expect(src.length).toBeGreaterThan(0);
    // The surface should define a handler that:
    //   1. Updates mode to "fork-draft"
    //   2. Updates workflowId to the new fork's ID
    const hasTransitionHandler =
      /handleForkTransition|handleFork|onForkTransition/.test(src) &&
      /fork-draft/.test(src);
    expect(
      hasTransitionHandler,
      "Expected WorkflowSurface to define a fork transition handler that sets mode to fork-draft",
    ).toBe(true);
  });

  it("passes the fork transition handler to useForkWorkflow or the topbar", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    expect(src.length).toBeGreaterThan(0);
    // The handler must be wired: either passed to useForkWorkflow as a
    // callback option, or to the topbar as an onFork prop
    const passesHandler =
      /useForkWorkflow\s*\(\s*\{[\s\S]*?(onTransition|onForkComplete|onModeChange)/.test(src) ||
      /onFork=\{/.test(src) ||
      /onForkTransition=\{/.test(src) ||
      /handleForkTransition/.test(src);
    expect(
      passesHandler,
      "Expected WorkflowSurface to wire the fork transition handler to the hook or topbar",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Fork-draft mode enables editing via the same surface
// ===========================================================================

describe("Fork-draft mode activates editing on the shared surface (RUN-595 AC2)", () => {
  it("fork-draft contract enables palette interaction (not dimmed)", () => {
    const contractSrc = readSource(CONTRACT_PATH);
    expect(contractSrc.length).toBeGreaterThan(0);
    // fork-draft palette should be: visible: true, dimmed: false, searchEditable: true
    // This verifies the contract already defines fork-draft as editable
    const forkDraftSection = contractSrc.match(
      /["']fork-draft["']\s*:\s*\{[\s\S]*?\n\s{2}\}/,
    );
    expect(forkDraftSection).not.toBeNull();
    expect(forkDraftSection![0]).toMatch(/dimmed:\s*false/);
  });

  it("fork-draft contract enables canvas dragging and connections", () => {
    const contractSrc = readSource(CONTRACT_PATH);
    const forkDraftSection = contractSrc.match(
      /["']fork-draft["']\s*:\s*\{[\s\S]*?\n\s{2}\}/,
    );
    expect(forkDraftSection).not.toBeNull();
    expect(forkDraftSection![0]).toMatch(/draggable:\s*true/);
    expect(forkDraftSection![0]).toMatch(/connectionsAllowed:\s*true/);
  });

  it("fork-draft contract enables save button (dirty-dependent)", () => {
    const contractSrc = readSource(CONTRACT_PATH);
    const forkDraftSection = contractSrc.match(
      /["']fork-draft["']\s*:\s*\{[\s\S]*?\n\s{2}\}/,
    );
    expect(forkDraftSection).not.toBeNull();
    expect(forkDraftSection![0]).toMatch(/saveButton:\s*["']dirty-dependent["']/);
  });

  it("fork-draft contract has the same editing capabilities as workflow mode", () => {
    const contractSrc = readSource(CONTRACT_PATH);
    // Verify key editing fields match between workflow and fork-draft
    const workflowSection = contractSrc.match(
      /\bworkflow\s*:\s*\{[\s\S]*?\n\s{2}\}/,
    );
    const forkDraftSection = contractSrc.match(
      /["']fork-draft["']\s*:\s*\{[\s\S]*?\n\s{2}\}/,
    );
    expect(workflowSection).not.toBeNull();
    expect(forkDraftSection).not.toBeNull();

    // Both should have: fieldsEditable: true, draggable: true,
    // connectionsAllowed: true, deletionAllowed: true
    expect(forkDraftSection![0]).toMatch(/fieldsEditable:\s*true/);
    expect(forkDraftSection![0]).toMatch(/deletionAllowed:\s*true/);
  });
});

// ===========================================================================
// 5. Route updates without surface component reset
// ===========================================================================

describe("Route updates without surface reset (RUN-595 AC1 + DoD)", () => {
  it("useForkWorkflow uses replaceState or window.history for URL update, not navigate", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // After fork, the URL should change to reflect the new workflow
    // but without triggering a React Router navigation that remounts.
    // Options: window.history.replaceState, router.replace with state,
    // or URL is handled by the caller (WorkflowSurface)
    const usesHistoryReplace =
      /history\.replaceState/.test(src) ||
      /window\.history/.test(src) ||
      /replaceState/.test(src) ||
      // Or the hook does not update the URL at all — the surface does it
      /onTransition|onForkComplete|onModeChange/.test(src);
    expect(
      usesHistoryReplace,
      "Expected fork to use history.replaceState or delegate URL update to surface callback, not navigate()",
    ).toBe(true);
  });

  it("WorkflowSurface updates the URL after fork transition without remounting", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    expect(src.length).toBeGreaterThan(0);
    // After the mode transitions to fork-draft and workflowId changes,
    // the surface should update the browser URL to reflect the new workflow
    const updatesUrl =
      /history\.replaceState/.test(src) ||
      /window\.history/.test(src) ||
      /replaceState/.test(src) ||
      // Or uses a useEffect that syncs URL based on workflowId changes
      /useEffect[\s\S]*?workflowId[\s\S]*?history|useEffect[\s\S]*?workflowId[\s\S]*?replaceState/.test(src);
    expect(
      updatesUrl,
      "Expected WorkflowSurface to update the URL after fork transition without remounting",
    ).toBe(true);
  });

  it("no separate fork-only page product exists in the routes", () => {
    const routesSrc = readSource(ROUTES_PATH);
    expect(routesSrc.length).toBeGreaterThan(0);
    // There should be no dedicated /fork or /workflows/:id/fork route
    expect(routesSrc).not.toMatch(/path:\s*["'].*fork/);
  });
});

// ===========================================================================
// 6. Historical overlay no longer defines active editing state after fork
// ===========================================================================

describe("Historical state deactivates after fork begins (RUN-595 AC3)", () => {
  it("WorkflowSurface clears runId from active state after fork transition", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    expect(src.length).toBeGreaterThan(0);
    // When transitioning from historical to fork-draft, the runId should
    // be cleared since fork-draft is a new workflow with no existing run
    const clearsRunId =
      /setRunId\s*\(\s*undefined\s*\)/.test(src) ||
      /setRunId\s*\(\s*null\s*\)/.test(src) ||
      /runId:\s*undefined/.test(src) ||
      // Or the fork transition handler explicitly removes runId
      (/handleForkTransition|handleFork|onForkTransition/.test(src) &&
       /runId/.test(src));
    expect(
      clearsRunId,
      "Expected fork transition to clear runId from active surface state",
    ).toBe(true);
  });

  it("fork-draft mode does not render historical run overlay elements", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    // WorkflowSurface must exist and contain the fork transition logic
    expect(
      src.length,
      "Expected WorkflowSurface.tsx to exist with fork transition logic",
    ).toBeGreaterThan(0);
    // After transitioning to fork-draft, any historical-only UI elements
    // (run status badge, read-only overlay, run metrics) should disappear.
    // The contract handles this: fork-draft.topbar.metricsVisible is false.
    // Verify the surface has fork-draft handling that clears historical state.
    expect(src).toMatch(
      /fork-draft/,
      "Expected WorkflowSurface to reference fork-draft mode for transition handling",
    );
  });
});

// ===========================================================================
// 7. Edge cases
// ===========================================================================

describe("Edge cases (RUN-595)", () => {
  it("fork from failed run triggers the same in-place transition", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // The fork hook should not check run status — status gating is done
    // in the button/UI layer. The hook itself should work for any status.
    // After RUN-595, it should invoke onTransition regardless of origin status.
    const hasTransitionCallback =
      /onTransition/.test(src) ||
      /onForkComplete/.test(src) ||
      /onModeChange/.test(src);
    expect(
      hasTransitionCallback,
      "Expected fork hook to invoke transition callback for any run status (including failed)",
    ).toBe(true);
    // And should NOT filter by status
    expect(src).not.toMatch(/status\s*===\s*["']failed["'].*return/);
  });

  it("snapshot unavailable prevents fork but error stays on historical mode", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // The hook must accept a transition callback (proving the new pattern exists)
    // AND the error handler must NOT invoke it — surface stays in historical
    // mode on failure. Both conditions must hold.
    const hasTransitionCallback =
      /onTransition/.test(src) ||
      /onForkComplete/.test(src) ||
      /onModeChange/.test(src);
    expect(
      hasTransitionCallback,
      "Expected hook to accept a transition callback (new in-place pattern)",
    ).toBe(true);
    // And the error handler must not call it
    expect(src).not.toMatch(
      /catch[\s\S]*?(onTransition|onForkComplete|onModeChange)\s*\(/,
    );
  });

  it("fork transition does not discard unsaved state from historical inspection", () => {
    const src = readSource(WORKFLOW_SURFACE_PATH);
    expect(src.length).toBeGreaterThan(0);
    // The fork transition handler should be aware that the surface may
    // have inspector/panel state open from historical viewing.
    // It should not blindly reset all panel state — just mode and workflowId.
    const hasCleanTransition =
      /handleForkTransition|handleFork|onForkTransition/.test(src) &&
      /set.*[Mm]ode/.test(src) &&
      /set.*[Ww]orkflowId/.test(src);
    expect(
      hasCleanTransition,
      "Expected fork transition to update mode + workflowId without resetting all panel state",
    ).toBe(true);
  });

  it("fork hook still creates the workflow file on disk via API before transitioning", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    // The workflow creation API call must still happen — fork still
    // writes a YAML file. Only the navigation behavior changes.
    expect(src).toMatch(/createWorkflow/);
    expect(src).toMatch(/getGitFile/);
  });

  it("fork hook still sets enabled: false on the new workflow", () => {
    const src = readForkHook();
    expect(src.length).toBeGreaterThan(0);
    const setsEnabledFalse =
      src.includes("enabled: false") ||
      src.includes("enabled:false");
    expect(setsEnabledFalse).toBe(true);
  });
});
