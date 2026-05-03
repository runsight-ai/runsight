/**
 * Placeholder block parser/compiler boundary coverage.
 *
 * `placeholder` is not a reserved built-in block in the surface YAML pipeline.
 * It follows the same generic unknown-block path as any custom block type.
 */

import { describe, expect, it } from "vitest";
import { dump } from "js-yaml";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { Node } from "@xyflow/react";
import type { StepNodeData, StepType } from "../../../types/schemas/canvas";

function makeYaml(blocks: Record<string, object>): string {
  return dump({
    version: "1.0",
    blocks,
    workflow: {
      name: "placeholder-boundary",
      entry: Object.keys(blocks)[0] ?? "start",
      transitions: [],
    },
  });
}

function mockNode(
  id: string,
  stepType: StepType | undefined,
  extraData: Partial<StepNodeData> = {},
): Node<StepNodeData> {
  return {
    id,
    type: "canvasNode",
    position: { x: 0, y: 0 },
    data: {
      stepId: id,
      name: id,
      stepType: stepType as StepType,
      status: "idle",
      ...extraData,
    },
  };
}

describe("Parser placeholder boundary", () => {
  it("parses placeholder through the generic unknown-block path", () => {
    const result = parseWorkflowYamlToGraph(
      makeYaml({
        step1: {
          type: "placeholder",
          description: "legacy note",
          output_path: "./draft.md",
        },
      }),
    );

    expect(result.error).toBeUndefined();
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].data.stepType).toBe("placeholder");
    expect(result.nodes[0].data.description).toBe("legacy note");
    expect((result.nodes[0].data as Record<string, unknown>).outputPath).toBe("./draft.md");
  });

  it("does not coerce other unknown block types to placeholder", () => {
    const result = parseWorkflowYamlToGraph(
      makeYaml({
        step1: { type: "custom_thing", description: "custom note" },
      }),
    );

    expect(result.error).toBeUndefined();
    expect(result.nodes[0].data.stepType).toBe("custom_thing");
  });

  it("reports a missing type without silently creating a placeholder block", () => {
    const result = parseWorkflowYamlToGraph(
      makeYaml({
        step1: { description: "missing type" },
      }),
    );

    expect(result.error?.message).toBeTruthy();
    expect(result.nodes.some((node) => node.data.stepType === "placeholder")).toBe(false);
  });
});

describe("Compiler placeholder boundary", () => {
  it("emits placeholder as a generic unknown block with arbitrary fields", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [
        mockNode("step1", "placeholder" as StepType, {
          description: "legacy note",
          outputPath: "./draft.md",
          nestedConfig: { innerValue: 7 },
        } as unknown as Partial<StepNodeData>),
      ],
      edges: [],
    });

    const block = result.workflowDocument.blocks.step1 as Record<string, unknown>;
    expect(block.type).toBe("placeholder");
    expect(block.description).toBe("legacy note");
    expect(block.output_path).toBe("./draft.md");
    expect((block.nested_config as Record<string, unknown>).inner_value).toBe(7);
  });

  it("does not coerce a missing node stepType to placeholder", () => {
    const node = mockNode("step1", undefined);

    let block: Record<string, unknown> | undefined;
    let threw = false;
    try {
      const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
      block = result.workflowDocument.blocks.step1 as Record<string, unknown> | undefined;
    } catch {
      threw = true;
    }

    expect(threw || block?.type !== "placeholder").toBe(true);
  });
});

describe("Placeholder round-trip boundary", () => {
  it("round-trips placeholder fields without special-case loss", () => {
    const sourceYaml = makeYaml({
      step1: {
        type: "placeholder",
        description: "legacy note",
        output_path: "./draft.md",
      },
    });

    const parsed = parseWorkflowYamlToGraph(sourceYaml);
    const compiled = compileGraphToWorkflowYaml({
      nodes: parsed.nodes,
      edges: parsed.edges,
      workflowName: "placeholder-boundary",
    });
    const block = compiled.workflowDocument.blocks.step1 as Record<string, unknown>;

    expect(block).toEqual({
      type: "placeholder",
      description: "legacy note",
      output_path: "./draft.md",
    });
  });
});
