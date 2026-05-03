import { dump } from "js-yaml";
import type { Edge, Node } from "@xyflow/react";

import { compileGraphToWorkflowYaml } from "../../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../../yamlParser";
import type { StepNodeData, StepType } from "../../../../types/schemas/canvas";

export const customThingFields = {
  fooBar: 42,
  bazQux: "hello",
} as const;

export const customThingYamlBlock = {
  type: "custom_thing",
  foo_bar: 42,
  baz_qux: "hello",
} as const;

export const nestedUnknownConfig = {
  firstLevel: {
    secondLevel: {
      thirdLevelValue: "deep",
    },
    arrayOfObjects: [
      { itemName: "one", itemCount: 1 },
      { itemName: "two", itemCount: 2 },
    ],
  },
} as const;

export const nestedUnknownYamlBlock = {
  type: "custom_thing",
  complex_config: {
    first_level: {
      second_level: {
        third_level_value: "deep",
      },
      array_of_objects: [
        { item_name: "one", item_count: 1 },
        { item_name: "two", item_count: 2 },
      ],
    },
  },
} as const;

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
    throw new Error(`Expected exactly one parsed node, received ${result.nodes.length}.`);
  }

  return result.nodes[0]!.data;
}

export function mockNode(
  id: string,
  stepType: string,
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

export function customThingNode(id: string): Node<StepNodeData> {
  return mockNode(
    id,
    "custom_thing",
    customThingFields as unknown as Partial<StepNodeData>,
  );
}

export function nestedUnknownConfigNode(id: string): Node<StepNodeData> {
  return mockNode(
    id,
    "custom_thing",
    { complexConfig: nestedUnknownConfig } as unknown as Partial<StepNodeData>,
  );
}

export function mixedKnownAndUnknownNodes(): Node<StepNodeData>[] {
  return [
    mockNode("plan", "linear", { soulRef: "planner" }),
    customThingNode("transform"),
    mockNode("fetch", "http_request", {
      url: "https://api.example.test/data",
      method: "GET",
      timeoutSeconds: 15,
    }),
  ];
}

export function multipleUnknownTypeNodes(): Node<StepNodeData>[] {
  return [
    mockNode("step1", "data_transform", {
      transformFn: "normalize",
      chunkSize: 100,
    } as unknown as Partial<StepNodeData>),
    mockNode("step2", "ai_validator", {
      modelRef: "gpt-4",
      validationRules: ["not_empty", "is_json"],
    } as unknown as Partial<StepNodeData>),
    mockNode("step3", "webhook_sender", {
      webhookUrl: "https://hooks.example.test/notify",
      payloadTemplate: '{"status": "done"}',
    } as unknown as Partial<StepNodeData>),
  ];
}

export function mockEdge(
  source: string,
  target: string,
  sourceHandle?: string,
): Edge {
  return {
    id: `${source}->${target}${sourceHandle ? `:${sourceHandle}` : ""}`,
    source,
    target,
    sourceHandle: sourceHandle ?? null,
    targetHandle: null,
  };
}

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  workflowName?: string;
  config?: Record<string, unknown>;
}

export function getBlock(
  doc: { blocks: Record<string, unknown> },
  id: string,
): Record<string, unknown> {
  return doc.blocks[id] as Record<string, unknown>;
}

export function compileOne(node: Node<StepNodeData>) {
  const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });

  return {
    block: getBlock(result.workflowDocument, node.id),
    yaml: result.yaml,
    doc: result.workflowDocument,
  };
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
