import { beforeEach, describe, expect, it } from "vitest";

import type { mapSSEEventToStoreAction as MapSSEEventToStoreActionFn } from "../useRunStream";

describe("run stream event mapping", () => {
  let mapSSEEventToStoreAction: typeof MapSSEEventToStoreActionFn;

  beforeEach(async () => {
    const mod = await import("../useRunStream");
    mapSSEEventToStoreAction = mod.mapSSEEventToStoreAction;
  });

  it("maps node lifecycle events to node status actions", () => {
    expect(
      mapSSEEventToStoreAction("node_started", {
        node_id: "block_1",
        block_type: "linear",
      }),
    ).toEqual({
      action: "setNodeStatus",
      nodeId: "block_1",
      status: "running",
    });
    expect(
      mapSSEEventToStoreAction("node_completed", {
        node_id: "block_1",
        duration_s: 1.2,
        cost_usd: 0.003,
      }),
    ).toEqual({
      action: "setNodeStatus",
      nodeId: "block_1",
      status: "completed",
    });
    expect(
      mapSSEEventToStoreAction("node_failed", {
        node_id: "block_1",
        error: "Soul invocation timeout",
      }),
    ).toEqual({
      action: "setNodeStatus",
      nodeId: "block_1",
      status: "failed",
    });
  });

  it("maps run terminal events to run completion actions", () => {
    expect(
      mapSSEEventToStoreAction("run_completed", {
        run_id: "run-live-canvas-primary",
        total_cost_usd: 0.01,
      }),
    ).toEqual({
      action: "runCompleted",
      runId: "run-live-canvas-primary",
      totalCost: 0.01,
    });
    expect(
      mapSSEEventToStoreAction("run_failed", {
        run_id: "run-live-canvas-secondary",
        error: "Workflow execution error",
      }),
    ).toEqual({
      action: "runFailed",
      runId: "run-live-canvas-secondary",
      error: "Workflow execution error",
    });
  });

  it("returns null for unknown events and includes node completion cost when present", () => {
    expect(mapSSEEventToStoreAction("unknown_event", { some: "data" })).toBeNull();
    expect(
      mapSSEEventToStoreAction("node_completed", {
        node_id: "block_2",
        duration_s: 0.8,
        cost_usd: 0.005,
      }),
    ).toHaveProperty("cost", 0.005);
  });
});
