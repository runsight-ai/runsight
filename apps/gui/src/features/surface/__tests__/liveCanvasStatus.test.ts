/**
 * RED-TEAM tests for RUN-7: Live canvas — real-time node status updates during execution.
 *
 * These tests verify:
 * 1. Canvas store exposes `setNodeStatus(nodeId, status)` to update a single node's data.status
 * 2. Canvas store exposes `resetNodeStatuses()` to reset all nodes to "idle"
 * 3. Canvas store exposes `activeRunId` / `setActiveRunId` for tracking the current run
 * 4. Canvas store exposes `runCost` / `setRunCost` for tracking total run cost
 * 5. A pure function `mapSSEEventToStoreAction` maps SSE event types to store action calls
 * 6. A pure function `getStatusBorderColor(status)` returns the correct CSS class per status
 *
 * All tests are expected to FAIL against the current implementation because:
 * - `useCanvasStore` has no `setNodeStatus`, `resetNodeStatuses`, `activeRunId`,
 *   `setActiveRunId`, `runCost`, or `setRunCost` fields
 * - `mapSSEEventToStoreAction` does not exist yet
 * - `getStatusBorderColor` does not exist yet
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useCanvasStore } from "../../../store/canvas";
import type { RunStatus, StepNodeData } from "../../../types/schemas/canvas";
import type { Node } from "@xyflow/react";
import type {
  getStatusBorderColor as GetStatusBorderColorFn,
  mapSSEEventToStoreAction as MapSSEEventToStoreActionFn,
} from "../useRunStream";

// ---------------------------------------------------------------------------
// Helpers — create minimal canvas nodes for testing
// ---------------------------------------------------------------------------

function makeNode(id: string, status: RunStatus = "idle"): Node<StepNodeData> {
  return {
    id,
    type: "canvasNode",
    position: { x: 0, y: 0 },
    data: {
      stepId: id,
      name: `Step ${id}`,
      stepType: "linear",
      status,
    },
  };
}

// ===========================================================================
// 1. Canvas store: setNodeStatus
// ===========================================================================

describe("useCanvasStore — setNodeStatus (RUN-7)", () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
  });

  it("exposes setNodeStatus as a function", () => {
    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("setNodeStatus");
    expect(state.setNodeStatus).toBeTypeOf("function");
  });

  it("updates a specific node's data.status to 'running'", () => {
    const nodes = [makeNode("block_1"), makeNode("block_2")];
    useCanvasStore.getState().setNodes(nodes, false);

    useCanvasStore.getState().setNodeStatus("block_1", "running");

    const updated = useCanvasStore.getState().nodes as Node<StepNodeData>[];
    expect(updated[0].data.status).toBe("running");
    // The other node should be untouched
    expect(updated[1].data.status).toBe("idle");
  });

  it("updates a specific node's data.status to 'completed'", () => {
    const nodes = [makeNode("block_1", "running")];
    useCanvasStore.getState().setNodes(nodes, false);

    useCanvasStore.getState().setNodeStatus("block_1", "completed");

    const updated = useCanvasStore.getState().nodes as Node<StepNodeData>[];
    expect(updated[0].data.status).toBe("completed");
  });

  it("updates a specific node's data.status to 'failed'", () => {
    const nodes = [makeNode("block_1", "running")];
    useCanvasStore.getState().setNodes(nodes, false);

    useCanvasStore.getState().setNodeStatus("block_1", "failed");

    const updated = useCanvasStore.getState().nodes as Node<StepNodeData>[];
    expect(updated[0].data.status).toBe("failed");
  });

  it("is a no-op when the nodeId does not exist (no crash)", () => {
    const nodes = [makeNode("block_1")];
    useCanvasStore.getState().setNodes(nodes, false);

    // Should not throw
    useCanvasStore.getState().setNodeStatus("nonexistent", "running");

    const updated = useCanvasStore.getState().nodes as Node<StepNodeData>[];
    expect(updated).toHaveLength(1);
    expect(updated[0].data.status).toBe("idle");
  });

  it("does not mark the canvas as dirty (runtime state, not persisted)", () => {
    const nodes = [makeNode("block_1")];
    useCanvasStore.getState().setNodes(nodes, false);
    // Ensure isDirty starts false
    expect(useCanvasStore.getState().isDirty).toBe(false);

    useCanvasStore.getState().setNodeStatus("block_1", "running");

    expect(useCanvasStore.getState().isDirty).toBe(false);
  });
});

// ===========================================================================
// 2. Canvas store: resetNodeStatuses
// ===========================================================================

describe("useCanvasStore — resetNodeStatuses (RUN-7)", () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
  });

  it("exposes resetNodeStatuses as a function", () => {
    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("resetNodeStatuses");
    expect(state.resetNodeStatuses).toBeTypeOf("function");
  });

  it("sets all nodes back to 'idle' status", () => {
    const nodes = [
      makeNode("block_1", "completed"),
      makeNode("block_2", "failed"),
      makeNode("block_3", "running"),
    ];
    useCanvasStore.getState().setNodes(nodes, false);

    useCanvasStore.getState().resetNodeStatuses();

    const updated = useCanvasStore.getState().nodes as Node<StepNodeData>[];
    expect(updated[0].data.status).toBe("idle");
    expect(updated[1].data.status).toBe("idle");
    expect(updated[2].data.status).toBe("idle");
  });

  it("is a no-op when there are no nodes", () => {
    // No nodes loaded
    useCanvasStore.getState().resetNodeStatuses();

    const updated = useCanvasStore.getState().nodes;
    expect(updated).toEqual([]);
  });

  it("does not mark the canvas as dirty", () => {
    const nodes = [makeNode("block_1", "running")];
    useCanvasStore.getState().setNodes(nodes, false);
    expect(useCanvasStore.getState().isDirty).toBe(false);

    useCanvasStore.getState().resetNodeStatuses();

    expect(useCanvasStore.getState().isDirty).toBe(false);
  });
});

// ===========================================================================
// 3. Canvas store: activeRunId / setActiveRunId
// ===========================================================================

describe("useCanvasStore — activeRunId (RUN-7)", () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
  });

  it("exposes activeRunId, initially null", () => {
    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("activeRunId");
    expect(state.activeRunId).toBeNull();
  });

  it("exposes setActiveRunId as a function", () => {
    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("setActiveRunId");
    expect(state.setActiveRunId).toBeTypeOf("function");
  });

  it("sets activeRunId to a run ID string", () => {
    useCanvasStore.getState().setActiveRunId("run-abc-123");

    expect(useCanvasStore.getState().activeRunId).toBe("run-abc-123");
  });

  it("clears activeRunId when set to null", () => {
    useCanvasStore.getState().setActiveRunId("run-abc-123");
    useCanvasStore.getState().setActiveRunId(null);

    expect(useCanvasStore.getState().activeRunId).toBeNull();
  });

  it("reset clears activeRunId", () => {
    useCanvasStore.getState().setActiveRunId("run-xyz");
    useCanvasStore.getState().reset();

    expect(useCanvasStore.getState().activeRunId).toBeNull();
  });
});

// ===========================================================================
// 4. Canvas store: runCost / setRunCost
// ===========================================================================

describe("useCanvasStore — runCost (RUN-7)", () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
  });

  it("exposes runCost, initially 0", () => {
    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("runCost");
    expect(state.runCost).toBe(0);
  });

  it("exposes setRunCost as a function", () => {
    const state = useCanvasStore.getState();
    expect(state).toHaveProperty("setRunCost");
    expect(state.setRunCost).toBeTypeOf("function");
  });

  it("sets runCost to a number", () => {
    useCanvasStore.getState().setRunCost(0.0035);

    expect(useCanvasStore.getState().runCost).toBe(0.0035);
  });

  it("can accumulate cost by setting a new total", () => {
    useCanvasStore.getState().setRunCost(0.003);
    useCanvasStore.getState().setRunCost(0.007);

    expect(useCanvasStore.getState().runCost).toBe(0.007);
  });

  it("reset clears runCost to 0", () => {
    useCanvasStore.getState().setRunCost(0.05);
    useCanvasStore.getState().reset();

    expect(useCanvasStore.getState().runCost).toBe(0);
  });
});

// ===========================================================================
// 5. SSE event mapping — mapSSEEventToStoreAction
// ===========================================================================

describe("mapSSEEventToStoreAction (RUN-7)", () => {
  // The function should be importable from the canvas feature's useRunStream module
  let mapSSEEventToStoreAction: typeof MapSSEEventToStoreActionFn;

  beforeEach(async () => {
    const mod = await import("../useRunStream");
    mapSSEEventToStoreAction = mod.mapSSEEventToStoreAction;
  });

  it("is exported as a function", () => {
    expect(mapSSEEventToStoreAction).toBeTypeOf("function");
  });

  it("maps 'node_started' event to setNodeStatus with 'running'", () => {
    const result = mapSSEEventToStoreAction("node_started", {
      node_id: "block_1",
      block_type: "linear",
    });

    expect(result).toEqual({
      action: "setNodeStatus",
      nodeId: "block_1",
      status: "running",
    });
  });

  it("maps 'node_completed' event to setNodeStatus with 'completed'", () => {
    const result = mapSSEEventToStoreAction("node_completed", {
      node_id: "block_1",
      duration_s: 1.2,
      cost_usd: 0.003,
    });

    expect(result).toEqual({
      action: "setNodeStatus",
      nodeId: "block_1",
      status: "completed",
    });
  });

  it("maps 'node_failed' event to setNodeStatus with 'failed'", () => {
    const result = mapSSEEventToStoreAction("node_failed", {
      node_id: "block_1",
      error: "Soul invocation timeout",
    });

    expect(result).toEqual({
      action: "setNodeStatus",
      nodeId: "block_1",
      status: "failed",
    });
  });

  it("maps 'run_completed' event to setActiveRunId(null) and setRunCost", () => {
    const result = mapSSEEventToStoreAction("run_completed", {
      run_id: "run-123",
      total_cost_usd: 0.01,
    });

    expect(result).toEqual({
      action: "runCompleted",
      runId: "run-123",
      totalCost: 0.01,
    });
  });

  it("maps 'run_failed' event to runFailed action", () => {
    const result = mapSSEEventToStoreAction("run_failed", {
      run_id: "run-456",
      error: "Workflow execution error",
    });

    expect(result).toEqual({
      action: "runFailed",
      runId: "run-456",
      error: "Workflow execution error",
    });
  });

  it("returns null for unknown event types", () => {
    const result = mapSSEEventToStoreAction("unknown_event", {
      some: "data",
    });

    expect(result).toBeNull();
  });

  it("includes cost_usd in node_completed mapping for per-node cost tracking", () => {
    const result = mapSSEEventToStoreAction("node_completed", {
      node_id: "block_2",
      duration_s: 0.8,
      cost_usd: 0.005,
    });

    expect(result).toHaveProperty("cost", 0.005);
  });
});

// ===========================================================================
// 6. Node status border color mapping — getStatusBorderColor
// ===========================================================================

describe("getStatusBorderColor (RUN-7)", () => {
  let getStatusBorderColor: typeof GetStatusBorderColorFn;

  beforeEach(async () => {
    const mod = await import("../useRunStream");
    getStatusBorderColor = mod.getStatusBorderColor;
  });

  it("is exported as a function", () => {
    expect(getStatusBorderColor).toBeTypeOf("function");
  });

  it("returns a default/gray border class for 'idle'", () => {
    const result = getStatusBorderColor("idle");
    // Should contain a gray/default border indicator
    expect(result).toContain("border");
    // Must NOT contain blue, green, or red
    expect(result).not.toMatch(/blue|green|red/i);
  });

  it("returns a default/gray border class for 'pending'", () => {
    const result = getStatusBorderColor("pending");
    expect(result).toContain("border");
    expect(result).not.toMatch(/blue|green|red/i);
  });

  it("returns a blue border class for 'running'", () => {
    const result = getStatusBorderColor("running");
    expect(result).toMatch(/blue/i);
  });

  it("returns a green border class for 'completed'", () => {
    const result = getStatusBorderColor("completed");
    expect(result).toMatch(/green/i);
  });

  it("returns a red border class for 'failed'", () => {
    const result = getStatusBorderColor("failed");
    expect(result).toMatch(/red/i);
  });

  it("returns a default border class for 'paused'", () => {
    // paused should get a distinguishable style but not red/green/blue for run states
    const result = getStatusBorderColor("paused");
    expect(result).toContain("border");
  });

  it("returns consistent values (pure function, no side effects)", () => {
    const first = getStatusBorderColor("running");
    const second = getStatusBorderColor("running");
    expect(first).toBe(second);
  });

  it("returns different classes for different statuses", () => {
    const idle = getStatusBorderColor("idle");
    const running = getStatusBorderColor("running");
    const completed = getStatusBorderColor("completed");
    const failed = getStatusBorderColor("failed");

    // Each active status should be visually distinct
    expect(running).not.toBe(idle);
    expect(completed).not.toBe(running);
    expect(failed).not.toBe(completed);
    expect(failed).not.toBe(running);
  });
});

// ===========================================================================
// 7. Integration contract: store + SSE mapping work together
// ===========================================================================

describe("Store + SSE integration contract (RUN-7)", () => {
  let mapSSEEventToStoreAction: typeof MapSSEEventToStoreActionFn;

  beforeEach(async () => {
    useCanvasStore.getState().reset();
    const mod = await import("../useRunStream");
    mapSSEEventToStoreAction = mod.mapSSEEventToStoreAction;
  });

  it("node_started event drives setNodeStatus('running') on the store", () => {
    const nodes = [makeNode("block_1"), makeNode("block_2")];
    useCanvasStore.getState().setNodes(nodes, false);

    const mapped = mapSSEEventToStoreAction("node_started", {
      node_id: "block_1",
      block_type: "linear",
    });

    // Apply the mapped action to the store
    if (mapped && mapped.action === "setNodeStatus") {
      useCanvasStore.getState().setNodeStatus(mapped.nodeId, mapped.status);
    }

    const updated = useCanvasStore.getState().nodes as Node<StepNodeData>[];
    expect(updated[0].data.status).toBe("running");
    expect(updated[1].data.status).toBe("idle");
  });

  it("sequence: node_started -> node_completed updates status through the pipeline", () => {
    const nodes = [makeNode("block_1")];
    useCanvasStore.getState().setNodes(nodes, false);

    // First event: node starts
    const started = mapSSEEventToStoreAction("node_started", {
      node_id: "block_1",
      block_type: "linear",
    });
    if (started && started.action === "setNodeStatus") {
      useCanvasStore.getState().setNodeStatus(started.nodeId, started.status);
    }
    expect((useCanvasStore.getState().nodes as Node<StepNodeData>[])[0].data.status).toBe("running");

    // Second event: node completes
    const completed = mapSSEEventToStoreAction("node_completed", {
      node_id: "block_1",
      duration_s: 1.5,
      cost_usd: 0.002,
    });
    if (completed && completed.action === "setNodeStatus") {
      useCanvasStore.getState().setNodeStatus(completed.nodeId, completed.status);
    }
    expect((useCanvasStore.getState().nodes as Node<StepNodeData>[])[0].data.status).toBe("completed");
  });

  it("resetNodeStatuses after a run brings all nodes back to idle", () => {
    const nodes = [
      makeNode("block_1", "completed"),
      makeNode("block_2", "failed"),
    ];
    useCanvasStore.getState().setNodes(nodes, false);
    useCanvasStore.getState().setActiveRunId("run-done");

    // Reset after run ends
    useCanvasStore.getState().resetNodeStatuses();
    useCanvasStore.getState().setActiveRunId(null);

    const updated = useCanvasStore.getState().nodes as Node<StepNodeData>[];
    expect(updated[0].data.status).toBe("idle");
    expect(updated[1].data.status).toBe("idle");
    expect(useCanvasStore.getState().activeRunId).toBeNull();
  });
});
