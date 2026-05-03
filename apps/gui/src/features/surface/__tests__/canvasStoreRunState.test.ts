/**
 * Live canvas node status update coverage.
 *
 * These tests verify:
 * 1. Canvas store exposes `setNodeStatus(nodeId, status)` to update a single node's data.status
 * 2. Canvas store exposes `resetNodeStatuses()` to reset all nodes to "idle"
 * 3. Canvas store exposes `activeRunId` / `setActiveRunId` for tracking the current run
 * 4. Canvas store exposes `runCost` / `setRunCost` for tracking total run cost
 * 5. A pure function `mapSSEEventToStoreAction` maps SSE event types to store action calls
 * 6. A pure function `getStatusBorderColor(status)` returns the correct CSS class per status
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useCanvasStore } from "../../../store/canvas";
import type { RunStatus, StepNodeData } from "../../../types/schemas/canvas";
import type { Node } from "@xyflow/react";

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

describe("useCanvasStore — setNodeStatus", () => {
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

describe("useCanvasStore — resetNodeStatuses", () => {
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

describe("useCanvasStore — activeRunId", () => {
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
    useCanvasStore.getState().setActiveRunId("run-live-active");

    expect(useCanvasStore.getState().activeRunId).toBe("run-live-active");
  });

  it("clears activeRunId when set to null", () => {
    useCanvasStore.getState().setActiveRunId("run-live-active");
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

describe("useCanvasStore — runCost", () => {
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
