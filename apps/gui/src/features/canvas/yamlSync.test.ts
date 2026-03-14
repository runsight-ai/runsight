import { describe, expect, it } from "vitest";
import type { Edge, Node } from "@xyflow/react";
import type { StepNodeData } from "../../types/schemas/canvas";
import { compileGraphToWorkflowYaml } from "./yamlCompiler";
import { parseWorkflowYamlToGraph } from "./yamlParser";

const BASIC_YAML = `
version: "1.0"
blocks:
  step_a:
    type: linear
  step_b:
    type: linear
workflow:
  name: Demo
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
`;

describe("yamlParser", () => {
  it("merges persisted node positions and viewport", () => {
    const result = parseWorkflowYamlToGraph(BASIC_YAML, {
      nodes: [
        { id: "step_a", position: { x: 120, y: 240 } },
        { id: "step_b", position: { x: 400, y: 240 } },
      ],
      edges: [],
      viewport: { x: 10, y: 20, zoom: 0.8 },
      selected_node_id: "step_a",
      canvas_mode: "dag",
    });

    expect(result.error).toBeUndefined();
    expect(result.nodes.find((n) => n.id === "step_a")?.position).toEqual({ x: 120, y: 240 });
    expect(result.nodes.find((n) => n.id === "step_b")?.position).toEqual({ x: 400, y: 240 });
    expect(result.viewport).toEqual({ x: 10, y: 20, zoom: 0.8 });
    expect(result.edges).toHaveLength(1);
  });

  it("returns error object (no throw) for invalid yaml", () => {
    const result = parseWorkflowYamlToGraph(":\n  - bad yaml");
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
    expect(result.error?.message.length).toBeGreaterThan(0);
  });
});

describe("yamlCompiler", () => {
  it("strips visual metadata from YAML while returning minimal canvasState", () => {
    const nodes: Array<Node<StepNodeData>> = [
      {
        id: "step_a",
        type: "canvasNode",
        position: { x: 10, y: 20 },
        data: {
          stepId: "step_a",
          name: "Step A",
          stepType: "linear",
          status: "idle",
          cost: 1.23,
        },
        selected: true,
      },
      {
        id: "step_b",
        type: "canvasNode",
        position: { x: 250, y: 20 },
        data: {
          stepId: "step_b",
          name: "Step B",
          stepType: "fanout",
          status: "idle",
        },
        width: 300,
      },
    ];

    const edges: Edge[] = [
      {
        id: "e-step_a-step_b",
        source: "step_a",
        target: "step_b",
        sourceHandle: "out-0",
        targetHandle: "in-0",
        selected: true,
      },
    ];

    const compiled = compileGraphToWorkflowYaml({
      nodes,
      edges,
      viewport: { x: 11, y: 12, zoom: 0.9 },
      selectedNodeId: "step_a",
      canvasMode: "dag",
      workflowName: "Demo",
    });

    expect(compiled.yaml).toContain("blocks:");
    expect(compiled.yaml).toContain("step_a:");
    expect(compiled.yaml).toContain("type: linear");
    expect(compiled.yaml).not.toContain("position:");
    expect(compiled.yaml).not.toContain("selected:");
    expect(compiled.yaml).not.toContain("width:");
    expect(compiled.canvasState.nodes).toEqual([
      { id: "step_a", position: { x: 10, y: 20 } },
      { id: "step_b", position: { x: 250, y: 20 } },
    ]);
    expect(compiled.canvasState.viewport.zoom).toBe(0.9);
    expect(compiled.canvasState.selected_node_id).toBe("step_a");
  });
});
