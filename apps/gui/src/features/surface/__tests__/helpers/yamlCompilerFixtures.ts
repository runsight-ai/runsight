import { compileGraphToWorkflowYaml } from "../../yamlCompiler";
import type {
  CaseDef,
  StepNodeData,
  StepType,
} from "../../../../types/schemas/canvas";
import type { Edge, Node } from "@xyflow/react";

export function mockNode(
  id: string,
  stepType: StepType,
  extraData: Partial<StepNodeData> = {},
): Node<StepNodeData> {
  return {
    id,
    type: "canvasNode",
    position: { x: 0, y: 0 },
    data: {
      stepId: id,
      name: id,
      stepType,
      status: "idle",
      ...extraData,
    },
  };
}

export function compileOne(node: Node<StepNodeData>) {
  const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
  return {
    block: result.workflowDocument.blocks[node.id],
    yaml: result.yaml,
    doc: result.workflowDocument,
  };
}

export const sampleOutputConditions: CaseDef[] = [
  {
    case_id: "approved",
    condition_group: {
      combinator: "and",
      conditions: [{ eval_key: "result.status", operator: "eq", value: "ok" }],
    },
  },
  { case_id: "default", default: true },
];

export function mockNodeWithConditions(
  id: string,
  stepType: StepType,
  cases: string[],
): Node<StepNodeData> {
  return mockNode(id, stepType, {
    soulRef: "test-soul",
    outputConditions: cases.map((c) =>
      c === "default"
        ? { case_id: c, default: true }
        : {
            case_id: c,
            condition_group: {
              combinator: "and",
              conditions: [{ eval_key: "score", operator: "gte", value: 5 }],
            },
          },
    ),
  });
}

export function mockEdge(
  source: string,
  target: string,
  sourceHandle?: string,
): Edge {
  return {
    id: source + "->" + target,
    source,
    target,
    sourceHandle: sourceHandle ?? null,
    targetHandle: null,
  };
}
