import { dump } from "js-yaml";
import type { Edge, Node, Viewport } from "@xyflow/react";
import type { PersistedCanvasState } from "@/store/canvas";
import type { StepNodeData } from "@/types/schemas/canvas";

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  viewport?: Viewport;
  selectedNodeId?: string | null;
  canvasMode?: "dag" | "state-machine";
  workflowName?: string;
}

interface CompiledWorkflow {
  version: string;
  blocks: Record<string, { type: string }>;
  workflow: {
    name: string;
    entry: string;
    transitions: Array<{ from: string; to: string }>;
  };
}

function toCompiledBlock(node: Node<StepNodeData>) {
  const stepType = node.data?.stepType ?? "placeholder";
  return {
    type: String(stepType),
  };
}

function toTransitions(edges: Edge[]) {
  return edges
    .filter((edge) => Boolean(edge.source) && Boolean(edge.target))
    .map((edge) => ({
      from: edge.source,
      to: edge.target,
    }));
}

function toPersistedCanvasState({
  nodes,
  edges,
  viewport,
  selectedNodeId,
  canvasMode,
}: CompileInput): PersistedCanvasState {
  return {
    nodes: nodes as unknown as Record<string, unknown>[],
    edges: edges as unknown as Record<string, unknown>[],
    viewport: viewport ?? { x: 0, y: 0, zoom: 1 },
    selected_node_id: selectedNodeId ?? null,
    canvas_mode: canvasMode ?? "dag",
  };
}

export function compileGraphToWorkflowYaml(input: CompileInput): {
  yaml: string;
  canvasState: PersistedCanvasState;
} {
  const nodes = input.nodes ?? [];
  const edges = input.edges ?? [];
  const entry = nodes[0]?.id ?? "start";

  const blocks = nodes.reduce<Record<string, { type: string }>>((acc, node) => {
    acc[node.id] = toCompiledBlock(node);
    return acc;
  }, {});

  const compiled: CompiledWorkflow = {
    version: "1.0",
    blocks,
    workflow: {
      name: input.workflowName ?? "Workflow",
      entry,
      transitions: toTransitions(edges),
    },
  };

  return {
    yaml: dump(compiled, { noRefs: true, lineWidth: 120 }),
    canvasState: toPersistedCanvasState(input),
  };
}
