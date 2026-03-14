import { beforeEach, describe, expect, it } from "vitest";
import type { Edge, Node } from "@xyflow/react";
import { useCanvasStore } from "./canvas";

function makeNode(id: string, x = 0, y = 0): Node {
  return {
    id,
    position: { x, y },
    data: {},
    type: "canvasNode",
  };
}

function makeEdge(id: string, source: string, target: string): Edge {
  return {
    id,
    source,
    target,
    type: "smoothstep",
  };
}

describe("useCanvasStore", () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
  });

  it("hydrates from persisted state and keeps isDirty false", () => {
    useCanvasStore.getState().hydrateFromPersisted({
      nodes: [makeNode("n1", 11, 22) as unknown as Record<string, unknown>],
      edges: [makeEdge("e1", "n1", "n2") as unknown as Record<string, unknown>],
      viewport: { x: 5, y: 6, zoom: 0.7 },
      selected_node_id: "n1",
      canvas_mode: "state-machine",
    });

    const state = useCanvasStore.getState();
    expect(state.nodes).toHaveLength(1);
    expect(state.edges).toHaveLength(1);
    expect(state.viewport).toEqual({ x: 5, y: 6, zoom: 0.7 });
    expect(state.selectedNodeId).toBe("n1");
    expect(state.canvasMode).toBe("state-machine");
    expect(state.isDirty).toBe(false);
  });

  it("marks dirty on node and edge changes", () => {
    useCanvasStore.getState().setNodes([makeNode("n1")], false);
    useCanvasStore.getState().setEdges([makeEdge("e1", "n1", "n2")], false);
    expect(useCanvasStore.getState().isDirty).toBe(false);

    useCanvasStore.getState().onNodesChange([
      { id: "n1", type: "position", position: { x: 40, y: 80 }, dragging: false },
    ]);
    expect(useCanvasStore.getState().isDirty).toBe(true);

    useCanvasStore.getState().markSaved();
    expect(useCanvasStore.getState().isDirty).toBe(false);

    useCanvasStore.getState().onEdgesChange([{ id: "e1", type: "remove" }]);
    expect(useCanvasStore.getState().isDirty).toBe(true);
  });

  it("serializes persisted shape with snake_case fields", () => {
    const store = useCanvasStore.getState();
    store.setNodes([makeNode("n1", 10, 20)], false);
    store.setEdges([makeEdge("e1", "n1", "n2")], false);
    store.setViewport({ x: 1, y: 2, zoom: 0.75 }, false);
    store.selectNode("n1");
    store.setCanvasMode("dag");
    store.markSaved();

    const persisted = useCanvasStore.getState().toPersistedState();
    expect(persisted.selected_node_id).toBe("n1");
    expect(persisted.canvas_mode).toBe("dag");
    expect(persisted.viewport.zoom).toBe(0.75);
    expect(persisted.nodes).toHaveLength(1);
    expect(persisted.edges).toHaveLength(1);
  });

  it("markSaved clears dirty flag without dropping graph data", () => {
    const store = useCanvasStore.getState();
    store.setNodes([makeNode("n1", 1, 2)], true);
    store.setEdges([makeEdge("e1", "n1", "n2")], true);
    expect(useCanvasStore.getState().isDirty).toBe(true);

    store.markSaved();
    const after = useCanvasStore.getState();
    expect(after.isDirty).toBe(false);
    expect(after.nodes).toHaveLength(1);
    expect(after.edges).toHaveLength(1);
  });
});
