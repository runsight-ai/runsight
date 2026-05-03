import { describe, expect, it } from "vitest";

import {
  compileOne,
  makeYaml,
  mockNode,
  parseFirst,
  roundTrip,
} from "./helpers/genericBlockRoundTripHelpers";

describe("Workflow special case preserved", () => {
  it("workflow block inputs/outputs still remap to workflowInputs/workflowOutputs on parse", () => {
    const yaml = makeYaml({
      sub: {
        type: "workflow",
        workflow_ref: "sub.yaml",
        max_depth: 3,
        inputs: { query: "parent.user_query" },
        outputs: { summary: "child.result.summary" },
      },
    });
    const data = parseFirst(yaml);

    expect(data.stepType).toBe("workflow");
    expect(data.workflowRef).toBe("sub.yaml");
    expect(data.maxDepth).toBe(3);
    expect(data.workflowInputs).toEqual({ query: "parent.user_query" });
    expect(data.workflowOutputs).toEqual({ summary: "child.result.summary" });
    expect(data.inputs).toBeUndefined();
    expect(data.outputs).toBeUndefined();
  });

  it("workflow block workflowInputs/workflowOutputs compile back to inputs/outputs", () => {
    const node = mockNode("sub", "workflow", {
      workflowRef: "sub.yaml",
      maxDepth: 3,
      workflowInputs: { query: "parent.user_query" },
      workflowOutputs: { summary: "child.result.summary" },
    });

    const { block } = compileOne(node);

    expect(block.type).toBe("workflow");
    expect(block.workflow_ref).toBe("sub.yaml");
    expect(block.max_depth).toBe(3);
    expect(block.inputs).toEqual({ query: "parent.user_query" });
    expect(block.outputs).toEqual({ summary: "child.result.summary" });
  });

  it("workflow block round-trips with inputs/outputs correctly", () => {
    const node = mockNode("sub", "workflow", {
      workflowRef: "sub.yaml",
      maxDepth: 3,
      workflowInputs: { query: "parent.user_query" },
      workflowOutputs: { summary: "child.result.summary" },
    });

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["sub"]).toEqual(doc1.blocks["sub"]);
    expect(yaml2).toBe(yaml1);
  });
});
