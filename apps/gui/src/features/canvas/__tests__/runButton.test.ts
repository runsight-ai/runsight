/**
 * RED-TEAM tests for RUN-129: Add "Run" button to design canvas.
 *
 * These tests verify:
 * 1. A `runWorkflow` orchestrator exists that sequentially saves then creates a run
 * 2. Save must complete before POST /runs (sequential guarantee)
 * 3. If save fails, run is never created
 * 4. Returns the created run ID for navigation
 * 5. Double-click prevention via loading/disabled state
 * 6. Button disabled when workflow has validation errors
 * 7. The canvas store exposes `validationErrors` state
 * 8. Navigation to /runs/{runId} on success
 * 9. Error toast on failure
 * 10. Button disabled when hasValidationErrors is true
 *
 * All tests are expected to FAIL against the current implementation because:
 * - `runWorkflow` orchestrator does not exist yet
 * - `useCanvasStore` has no `validationErrors` field
 * - WorkflowCanvas.tsx has no "Run" button
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCanvasStore } from "../../../store/canvas";
import type { RunCreate } from "../../../types/generated/zod";

// ---------------------------------------------------------------------------
// 1. Canvas store: validationErrors support
// ---------------------------------------------------------------------------

describe("useCanvasStore — validationErrors (RUN-129)", () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
  });

  it("exposes a validationErrors array, initially empty", () => {
    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("validationErrors");
    expect(state.validationErrors).toEqual([]);
  });

  it("setValidationErrors updates the store", () => {
    const { setValidationErrors } = useCanvasStore.getState();
    expect(setValidationErrors).toBeTypeOf("function");

    setValidationErrors(["Workflow has no entry point"]);

    const state = useCanvasStore.getState();
    expect(state.validationErrors).toEqual(["Workflow has no entry point"]);
  });

  it("hasValidationErrors returns true when errors exist", () => {
    const { setValidationErrors } = useCanvasStore.getState();
    setValidationErrors(["Missing transition"]);

    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("hasValidationErrors");
    expect(state.hasValidationErrors).toBe(true);
  });

  it("hasValidationErrors returns false when errors are empty", () => {
    const state = useCanvasStore.getState();
    expect(state.hasValidationErrors).toBe(false);
  });

  it("reset clears validationErrors", () => {
    const { setValidationErrors } = useCanvasStore.getState();
    setValidationErrors(["Some error"]);
    useCanvasStore.getState().reset();

    expect(useCanvasStore.getState().validationErrors).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 2. runWorkflow orchestrator function
// ---------------------------------------------------------------------------

describe("runWorkflow orchestrator (RUN-129)", () => {
  // The orchestrator should be importable from the canvas feature
  // It coordinates: save workflow -> create run -> return run id
  let runWorkflow: typeof import("../runWorkflow").runWorkflow;

  beforeEach(async () => {
    // Dynamic import so the test file itself compiles even if module is missing
    const mod = await import("../runWorkflow");
    runWorkflow = mod.runWorkflow;
  });

  it("is exported as a function", () => {
    expect(runWorkflow).toBeTypeOf("function");
  });

  it("calls save before createRun (sequential order)", async () => {
    const callOrder: string[] = [];

    const saveFn = vi.fn(async () => {
      callOrder.push("save");
    });
    const createRunFn = vi.fn(async (data: RunCreate) => {
      callOrder.push("createRun");
      return { id: "run-123", workflow_id: data.workflow_id };
    });

    const result = await runWorkflow({
      workflowId: "wf-1",
      save: saveFn,
      createRun: createRunFn,
    });

    expect(saveFn).toHaveBeenCalledTimes(1);
    expect(createRunFn).toHaveBeenCalledTimes(1);
    expect(createRunFn).toHaveBeenCalledWith({
      workflow_id: "wf-1",
      task_data: {},
    });
    expect(callOrder).toEqual(["save", "createRun"]);
    expect(result).toHaveProperty("runId", "run-123");
  });

  it("does NOT call createRun if save throws", async () => {
    const saveFn = vi.fn(async () => {
      throw new Error("Save failed: network error");
    });
    const createRunFn = vi.fn(async (data: RunCreate) => {
      return { id: "run-456", workflow_id: data.workflow_id };
    });

    await expect(
      runWorkflow({
        workflowId: "wf-2",
        save: saveFn,
        createRun: createRunFn,
      }),
    ).rejects.toThrow("Save failed");

    expect(saveFn).toHaveBeenCalledTimes(1);
    expect(createRunFn).not.toHaveBeenCalled();
  });

  it("propagates createRun errors after save succeeds", async () => {
    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async () => {
      throw new Error("Run creation failed: 500");
    });

    await expect(
      runWorkflow({
        workflowId: "wf-3",
        save: saveFn,
        createRun: createRunFn,
      }),
    ).rejects.toThrow("Run creation failed");

    // Save was still called
    expect(saveFn).toHaveBeenCalledTimes(1);
    expect(createRunFn).toHaveBeenCalledTimes(1);
  });

  it("returns the run ID on success for navigation", async () => {
    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async (data: RunCreate) => ({
      id: "run-789",
      workflow_id: data.workflow_id,
    }));

    const result = await runWorkflow({
      workflowId: "wf-4",
      save: saveFn,
      createRun: createRunFn,
    });

    expect(result.runId).toBe("run-789");
  });

  it("passes task_data through to createRun when provided", async () => {
    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async (data: RunCreate) => ({
      id: "run-td-1",
      workflow_id: data.workflow_id,
    }));

    await runWorkflow({
      workflowId: "wf-td",
      save: saveFn,
      createRun: createRunFn,
      taskData: { prompt: "hello" },
    });

    expect(createRunFn).toHaveBeenCalledWith({
      workflow_id: "wf-td",
      task_data: { prompt: "hello" },
    });
  });
});

// ---------------------------------------------------------------------------
// 3. Navigation on successful run (RUN-129)
// ---------------------------------------------------------------------------

describe("runWorkflow navigation (RUN-129)", () => {
  let runWorkflow: typeof import("../runWorkflow").runWorkflow;

  beforeEach(async () => {
    const mod = await import("../runWorkflow");
    runWorkflow = mod.runWorkflow;
  });

  it("calls navigate with /runs/{runId} on success", async () => {
    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async (data: RunCreate) => ({
      id: "run-nav-1",
      workflow_id: data.workflow_id,
    }));
    const navigateFn = vi.fn();

    await runWorkflow({
      workflowId: "wf-nav",
      save: saveFn,
      createRun: createRunFn,
      navigate: navigateFn,
    });

    expect(navigateFn).toHaveBeenCalledTimes(1);
    expect(navigateFn).toHaveBeenCalledWith("/runs/run-nav-1");
  });

  it("does NOT call navigate when createRun fails", async () => {
    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async () => {
      throw new Error("Run creation failed");
    });
    const navigateFn = vi.fn();

    await expect(
      runWorkflow({
        workflowId: "wf-nav-fail",
        save: saveFn,
        createRun: createRunFn,
        navigate: navigateFn,
      }),
    ).rejects.toThrow();

    expect(navigateFn).not.toHaveBeenCalled();
  });

  it("does NOT call navigate when save fails", async () => {
    const saveFn = vi.fn(async () => {
      throw new Error("Save failed");
    });
    const createRunFn = vi.fn(async (data: RunCreate) => ({
      id: "run-should-not-reach",
      workflow_id: data.workflow_id,
    }));
    const navigateFn = vi.fn();

    await expect(
      runWorkflow({
        workflowId: "wf-nav-save-fail",
        save: saveFn,
        createRun: createRunFn,
        navigate: navigateFn,
      }),
    ).rejects.toThrow();

    expect(navigateFn).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 4. Error toast on failure (RUN-129)
// ---------------------------------------------------------------------------

describe("runWorkflow error toast (RUN-129)", () => {
  let runWorkflow: typeof import("../runWorkflow").runWorkflow;

  beforeEach(async () => {
    const mod = await import("../runWorkflow");
    runWorkflow = mod.runWorkflow;
  });

  it("calls onError with the error when save fails", async () => {
    const saveFn = vi.fn(async () => {
      throw new Error("Save failed: network error");
    });
    const createRunFn = vi.fn(async (data: RunCreate) => ({
      id: "run-never",
      workflow_id: data.workflow_id,
    }));
    const onErrorFn = vi.fn();

    await expect(
      runWorkflow({
        workflowId: "wf-toast-save",
        save: saveFn,
        createRun: createRunFn,
        onError: onErrorFn,
      }),
    ).rejects.toThrow("Save failed");

    expect(onErrorFn).toHaveBeenCalledTimes(1);
    expect(onErrorFn).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining("Save failed") }),
    );
  });

  it("calls onError with the error when createRun fails", async () => {
    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async () => {
      throw new Error("Run creation failed: 500");
    });
    const onErrorFn = vi.fn();

    await expect(
      runWorkflow({
        workflowId: "wf-toast-run",
        save: saveFn,
        createRun: createRunFn,
        onError: onErrorFn,
      }),
    ).rejects.toThrow("Run creation failed");

    expect(onErrorFn).toHaveBeenCalledTimes(1);
    expect(onErrorFn).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining("Run creation failed") }),
    );
  });

  it("does NOT call onError on success", async () => {
    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async (data: RunCreate) => ({
      id: "run-ok",
      workflow_id: data.workflow_id,
    }));
    const onErrorFn = vi.fn();

    await runWorkflow({
      workflowId: "wf-toast-ok",
      save: saveFn,
      createRun: createRunFn,
      onError: onErrorFn,
    });

    expect(onErrorFn).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 5. Button disabled when validation errors exist (RUN-129)
// ---------------------------------------------------------------------------

describe("Run button disabled state contract (RUN-129)", () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
  });

  it("hasValidationErrors is false when validationErrors is empty — button should be enabled", () => {
    const state = useCanvasStore.getState();
    expect(state.hasValidationErrors).toBe(false);
    // Contract: the Run button's disabled prop should be bound to hasValidationErrors.
    // When hasValidationErrors is false, the button is enabled.
  });

  it("hasValidationErrors is true when validationErrors has entries — button should be disabled", () => {
    const { setValidationErrors } = useCanvasStore.getState();
    setValidationErrors(["No entry step defined", "Orphan node detected"]);

    const state = useCanvasStore.getState();
    expect(state.hasValidationErrors).toBe(true);
    // Contract: the Run button's disabled prop should be bound to hasValidationErrors.
    // When hasValidationErrors is true, the button must be disabled.
  });

  it("clearing errors re-enables the button (hasValidationErrors goes back to false)", () => {
    const { setValidationErrors } = useCanvasStore.getState();
    setValidationErrors(["Some error"]);
    expect(useCanvasStore.getState().hasValidationErrors).toBe(true);

    setValidationErrors([]);
    expect(useCanvasStore.getState().hasValidationErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 6. Double-click prevention / loading state
// ---------------------------------------------------------------------------

describe("runWorkflow double-click prevention (RUN-129)", () => {
  it("the orchestrator accepts an isRunning guard and skips if true", async () => {
    const mod = await import("../runWorkflow");
    const { runWorkflow } = mod;

    const saveFn = vi.fn(async () => {});
    const createRunFn = vi.fn(async (data: RunCreate) => ({
      id: "run-aaa",
      workflow_id: data.workflow_id,
    }));

    // When isRunning is true, should return null/undefined or skip
    const result = await runWorkflow({
      workflowId: "wf-5",
      save: saveFn,
      createRun: createRunFn,
      isRunning: true,
    });

    expect(saveFn).not.toHaveBeenCalled();
    expect(createRunFn).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });
});
