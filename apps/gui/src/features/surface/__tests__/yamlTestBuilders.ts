import { dump } from "js-yaml";
import type { Edge, Node } from "@xyflow/react";

import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType } from "../../../types/schemas/canvas";

export type CompileInput = {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  workflowName?: string;
  config?: Record<string, unknown>;
};

export function mockNode(
  id: string,
  stepType: StepType | string,
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

export function mockEdge(source: string, target: string, sourceHandle?: string): Edge {
  return {
    id: `${source}->${target}${sourceHandle ? `:${sourceHandle}` : ""}`,
    source,
    target,
    sourceHandle: sourceHandle ?? null,
    targetHandle: null,
  };
}

export function makeYaml(
  blocks: Record<string, object>,
  opts?: { souls?: object; config?: object },
): string {
  return dump({
    version: "1.0",
    ...(opts?.config ? { config: opts.config } : {}),
    ...(opts?.souls ? { souls: opts.souls } : {}),
    blocks,
    workflow: {
      name: "test",
      entry: Object.keys(blocks)[0] ?? "start",
      transitions: [],
    },
  });
}

export function parseFirst(yaml: string): StepNodeData {
  const result = parseWorkflowYamlToGraph(yaml);
  if (result.nodes.length !== 1) {
    throw new Error(`Expected exactly one parsed node, received ${result.nodes.length}`);
  }

  return result.nodes[0].data;
}

export function roundTrip(input: CompileInput) {
  const { yaml: yaml1, workflowDocument: doc1 } = compileGraphToWorkflowYaml(input);
  const parsed = parseWorkflowYamlToGraph(yaml1);
  const input2: CompileInput = {
    nodes: parsed.nodes,
    edges: parsed.edges,
    config: parsed.config,
    workflowName: input.workflowName,
  };
  const { yaml: yaml2, workflowDocument: doc2 } = compileGraphToWorkflowYaml(input2);

  return { yaml1, yaml2, doc1, doc2, parsed };
}

export function getBlock(
  doc: { blocks: Record<string, unknown> },
  id: string,
): Record<string, unknown> {
  return doc.blocks[id] as Record<string, unknown>;
}
