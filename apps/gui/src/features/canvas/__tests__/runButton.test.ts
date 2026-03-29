/**
 * RED-TEAM tests for RUN-359: Run/Cancel button state machine + execution flow.
 *
 * These tests verify the run/cancel button implements the state machine:
 *   Idle:      [Run]    -> click -> Running
 *   Running:   [Cancel] -> click -> Cancelled
 *   Completed: [Run]    -> new run
 *   Failed:    [Run]    -> new run
 *   Cancelled: [Run]    -> new run
 *
 * Acceptance Criteria:
 *   AC1: Run button creates run via POST /api/runs
 *   AC2: Button text/icon changes based on run status (idle->running->completed)
 *   AC3: Cancel button calls POST /api/runs/:id/cancel
 *   AC4: activeRunId stored in canvas store
 *   AC5: Uses Button component from library
 *   AC6: Disabled state when no workflow content
 *
 * All tests are expected to FAIL because:
 *   - No RunButton component exists yet
 *   - CanvasTopbar has only a plain <span> "Run" placeholder
 *   - No state machine logic wired in the topbar
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCanvasStore } from "../../../store/canvas";

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
// Paths
// ---------------------------------------------------------------------------

const RUN_BUTTON_PATH = "features/canvas/RunButton.tsx";
const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";

// ===========================================================================
// 1. RunButton component exists (AC5)
// ===========================================================================

describe("RunButton component exists (RUN-359)", () => {
  it("RunButton.tsx file exists", () => {
    expect(
      fileExists(RUN_BUTTON_PATH),
      "Expected features/canvas/RunButton.tsx to exist",
    ).toBe(true);
  });

  it("exports RunButton as a named export", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+RunButton/);
  });

  it("CanvasTopbar renders RunButton", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/<RunButton/);
  });

  it("CanvasTopbar imports RunButton", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/import.*RunButton.*from/);
  });
});

// ===========================================================================
// 2. Uses Button component from design system library (AC5)
// ===========================================================================

describe("RunButton uses Button from component library (RUN-359 AC5)", () => {
  it("imports Button from @runsight/ui/button", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/import.*Button.*from.*@runsight\/ui\/button/);
  });

  it("renders <Button> element (not raw <button>)", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/<Button[\s>]/);
  });
});

// ===========================================================================
// 3. Run button creates run via POST /api/runs (AC1)
// ===========================================================================

describe("RunButton creates run via useCreateRun (RUN-359 AC1)", () => {
  it("imports useCreateRun from queries/runs", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/import.*useCreateRun.*from.*queries\/runs/);
  });

  it("calls createRun mutate with workflow_id", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should invoke the mutation with workflow_id
    expect(source).toMatch(/mutate\(|mutateAsync\(/);
    expect(source).toMatch(/workflow_id/);
  });

  it("passes source: 'manual' in the create run payload", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The ticket specifies POST /api/runs with { workflow_id, source: "manual" }
    expect(source).toMatch(/source.*manual|"manual"/);
  });
});

// ===========================================================================
// 4. Cancel button calls POST /api/runs/:id/cancel (AC3)
// ===========================================================================

describe("RunButton cancel flow (RUN-359 AC3)", () => {
  it("imports useCancelRun from queries/runs", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/import.*useCancelRun.*from.*queries\/runs/);
  });

  it("calls cancelRun mutate with activeRunId", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should call cancel mutation with the active run ID
    expect(source).toMatch(/cancelRun|cancel.*mutate/);
  });
});

// ===========================================================================
// 5. activeRunId stored in canvas store (AC4)
// ===========================================================================

describe("RunButton uses activeRunId from canvas store (RUN-359 AC4)", () => {
  it("imports useCanvasStore", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/import.*useCanvasStore.*from.*store\/canvas/);
  });

  it("reads activeRunId from the store", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/activeRunId/);
  });

  it("calls setActiveRunId after creating a run", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/setActiveRunId/);
  });

  it("clears activeRunId when run completes, fails, or is cancelled", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should call setActiveRunId(null) on terminal states
    expect(source).toMatch(/setActiveRunId\(\s*null\s*\)/);
  });

  it("canvas store setActiveRunId stores the run ID correctly", () => {
    useCanvasStore.getState().reset();
    const { setActiveRunId } = useCanvasStore.getState();
    setActiveRunId("run-abc-123");
    expect(useCanvasStore.getState().activeRunId).toBe("run-abc-123");
  });

  it("canvas store setActiveRunId(null) clears the run ID", () => {
    useCanvasStore.getState().reset();
    const { setActiveRunId } = useCanvasStore.getState();
    setActiveRunId("run-xyz");
    setActiveRunId(null);
    expect(useCanvasStore.getState().activeRunId).toBeNull();
  });
});

// ===========================================================================
// 6. Button text/icon changes based on run status — state machine (AC2)
// ===========================================================================

describe("RunButton state machine — status-based rendering (RUN-359 AC2)", () => {
  it("renders 'Run' label in idle state (no activeRunId)", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should conditionally show "Run" text
    expect(source).toMatch(/Run/);
  });

  it("renders 'Cancel' label in running state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should conditionally show "Cancel" text when running
    expect(source).toMatch(/Cancel/);
  });

  it("uses a play icon for Run state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should have a play/triangle icon for Run
    // Common: Play, PlayIcon, PlayCircle, or an SVG triangle
    expect(source).toMatch(/Play|play|▶/i);
  });

  it("uses a stop/X icon for Cancel state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should have an X/stop icon for Cancel
    // Common: X, XIcon, XCircle, Square, StopCircle
    expect(source).toMatch(/X\b|Stop|Square|×|✕/i);
  });

  it("determines button mode from activeRunId and run status", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The component should branch on whether there is an active run
    // and what its status is
    const hasStatusLogic =
      /status.*===.*running|isRunning|activeRunId/.test(source);
    expect(
      hasStatusLogic,
      "Expected status-based conditional rendering logic",
    ).toBe(true);
  });

  it("uses useRun hook to track active run status", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should import useRun to poll/track the active run's status
    expect(source).toMatch(/import.*useRun.*from.*queries\/runs/);
  });

  it("after completed status, button returns to Run state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should handle completed/failed/cancelled to reset button
    const handlesTerminalStates =
      /completed|failed|cancelled/.test(source);
    expect(
      handlesTerminalStates,
      "Expected handling of terminal run statuses (completed/failed/cancelled)",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. Disabled state when no workflow content (AC6)
// ===========================================================================

describe("RunButton disabled when no blocks on canvas (RUN-359 AC6)", () => {
  it("checks canvas nodes to determine if workflow has content", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should read nodes from canvas store to check if canvas is empty
    expect(source).toMatch(/nodes/);
  });

  it("disables the button when there are no nodes on canvas", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should pass disabled prop when nodes array is empty
    const hasDisabledLogic =
      /disabled.*nodes\.length|nodes\.length.*===.*0|!nodes\.length|isEmpty/.test(source);
    expect(
      hasDisabledLogic,
      "Expected disabled logic based on empty nodes array",
    ).toBe(true);
  });

  it("shows tooltip 'Add at least one block' when disabled", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/Add at least one block/);
  });

  it("imports Tooltip from component library for disabled hint", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/import.*Tooltip.*from.*components\/ui\/tooltip/);
  });
});

// ===========================================================================
// 8. Button variant and styling
// ===========================================================================

describe("RunButton styling and variants (RUN-359)", () => {
  it("uses primary variant for Run state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Run button should use primary variant
    expect(source).toMatch(/variant.*primary|"primary"/);
  });

  it("uses danger variant for Cancel state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Cancel button should use danger variant to signal destructive action
    expect(source).toMatch(/variant.*danger|"danger"/);
  });

  it("shows loading state while run is being created", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Button component supports loading prop — should be used during mutation
    expect(source).toMatch(/loading|isPending|isLoading/);
  });
});

// ===========================================================================
// 9. CanvasTopbar no longer has plain Run placeholder
// ===========================================================================

describe("CanvasTopbar Run placeholder replaced (RUN-359)", () => {
  it("CanvasTopbar does NOT have a bare <span> 'Run' placeholder", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The old placeholder: <span className="text-sm text-secondary">Run</span>
    // Should be replaced with <RunButton ... />
    expect(source).not.toMatch(/<span[^>]*>Run<\/span>/);
  });
});

// ===========================================================================
// 10. workflowId prop contract
// ===========================================================================

describe("RunButton receives workflowId (RUN-359)", () => {
  it("RunButton accepts workflowId prop", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/workflowId/);
  });

  it("CanvasTopbar passes workflowId to RunButton", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/<RunButton[^>]*workflowId/);
  });
});
