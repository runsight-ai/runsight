import { describe, expect, it } from "vitest";

import type { StepNodeData } from "../../../types/schemas/canvas";
import { getBlock, mockEdge, mockNode, roundTrip } from "./yamlTestBuilders";

describe("generic YAML round trip smoke", () => {
  it("preserves a mixed known and custom workflow through compile, parse, and compile", () => {
    const nodes = [
      mockNode("plan", "linear", { soulRef: "planner" }),
      mockNode("transform", "custom_transform", {
        fooBar: 42,
        nestedPolicy: {
          maxAttempts: 2,
          sourceBlocks: ["plan"],
        },
      } as unknown as Partial<StepNodeData>),
      mockNode("finish", "linear", { inputs: { summary: { from: "transform.result" } } }),
    ];
    const edges = [
      mockEdge("plan", "transform"),
      mockEdge("transform", "finish"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({
      nodes,
      edges,
      workflowName: "generic-smoke",
      config: { max_concurrency: 2 },
    });

    expect(getBlock(doc1, "plan")).toMatchObject({
      type: "linear",
      soul_ref: "planner",
    });
    expect(getBlock(doc1, "transform")).toMatchObject({
      type: "custom_transform",
      foo_bar: 42,
      nested_policy: {
        max_attempts: 2,
        source_blocks: ["plan"],
      },
    });
    expect(getBlock(doc1, "finish")).toMatchObject({
      type: "linear",
      inputs: { summary: { from: "transform.result" } },
    });
    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(doc2.config).toEqual(doc1.config);
    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);
    expect(yaml2).toBe(yaml1);
  });
});
