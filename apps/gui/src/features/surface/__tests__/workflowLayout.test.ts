import { describe, expect, it } from "vitest";

import { buildWorkflowLayout, hasRenderableCanvasState } from "../workflowLayout";

describe("workflowLayout", () => {
  const yaml = `
version: "1.0"
blocks:
  research:
    type: linear
    soul_ref: researcher
  review:
    type: gate
    soul_ref: reviewer
workflow:
  name: Review Flow
  entry: research
  transitions:
    - from: research
      to: review
`;

  it("computes renderable surface nodes from YAML when no canvas_state exists", () => {
    const layout = buildWorkflowLayout(yaml, null);

    expect(layout.nodes).toHaveLength(2);
    expect(layout.edges).toHaveLength(1);

    const [research, review] = layout.nodes as Array<{
      id: string;
      type: string;
      position: { x: number; y: number };
    }>;

    expect(research.id).toBe("research");
    expect(research.type).toBe("start");
    expect(review.id).toBe("review");
    expect(review.type).toBe("step");
    expect(review.position.x).toBeGreaterThan(research.position.x);
  });

  it("reuses persisted positions when the sidecar only carries layout coordinates", () => {
    const layout = buildWorkflowLayout(yaml, {
      nodes: [
        { id: "research", position: { x: 40, y: 60 } },
        { id: "review", position: { x: 440, y: 80 } },
      ],
      edges: [],
      viewport: { x: 10, y: 20, zoom: 0.9 },
      selected_node_id: null,
      canvas_mode: "dag",
    });

    const [research, review] = layout.nodes as Array<{
      id: string;
      position: { x: number; y: number };
    }>;

    expect(research.position).toEqual({ x: 40, y: 60 });
    expect(review.position).toEqual({ x: 440, y: 80 });
    expect(layout.viewport).toEqual({ x: 10, y: 20, zoom: 0.9 });
  });

  it("detects whether canvas_state already contains fully renderable nodes", () => {
    expect(
      hasRenderableCanvasState({
        nodes: [{ id: "research", position: { x: 0, y: 0 } }],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      }),
    ).toBe(false);

    expect(
      hasRenderableCanvasState({
        nodes: [
          {
            id: "research",
            type: "task",
            position: { x: 0, y: 0 },
            data: { stepId: "research", name: "Research", stepType: "linear", status: "idle" },
          },
        ],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      }),
    ).toBe(true);
  });
});
