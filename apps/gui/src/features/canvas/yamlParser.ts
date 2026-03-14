import { load } from "js-yaml";
import type { Edge, Node } from "@xyflow/react";
import type { PersistedCanvasState } from "../../store/canvas";
import type { BlockDef, RunsightWorkflowFile, StepNodeData, StepType } from "../../types/schemas/canvas";

export interface ParseWorkflowResult {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  viewport?: PersistedCanvasState["viewport"];
  error?: { message: string };
}

type ParsedWorkflow = Partial<RunsightWorkflowFile> & {
  blocks?: Record<string, BlockDef>;
  workflow?: {
    entry?: string;
    transitions?: Array<{ from: string; to: string | null }>;
    conditional_transitions?: Array<Record<string, string | null>>;
  };
};

const DEFAULT_STEP_TYPE: StepType = "placeholder";
const DEFAULT_GRID_X = 280;
const DEFAULT_GRID_Y = 160;

function toStepType(value: unknown): StepType {
  if (typeof value !== "string") return DEFAULT_STEP_TYPE;
  return value as StepType;
}

function findPersistedPosition(
  canvasState: PersistedCanvasState | null | undefined,
  nodeId: string,
): { x: number; y: number } | null {
  if (!canvasState?.nodes) return null;
  const rawNodes = canvasState.nodes as unknown;

  // Support both array and map-style persisted formats.
  if (Array.isArray(rawNodes)) {
    const raw = rawNodes.find((n) => typeof n === "object" && n !== null && (n as { id?: unknown }).id === nodeId);
    if (!raw || typeof raw !== "object") return null;

    const position = (raw as { position?: unknown }).position as { x?: unknown; y?: unknown } | null | undefined;
    if (!position) return null;
    if (typeof position.x !== "number" || typeof position.y !== "number") return null;
    return { x: position.x, y: position.y };
  }

  if (typeof rawNodes !== "object" || rawNodes === null) return null;
  const raw = (rawNodes as Record<string, unknown>)[nodeId];
  if (typeof raw !== "object" || raw === null) return null;
  const position = (raw as { position?: unknown }).position as { x?: unknown; y?: unknown } | null;
  if (!position) return null;
  if (typeof position.x !== "number" || typeof position.y !== "number") return null;
  return { x: position.x, y: position.y };
}

export function parseWorkflowYamlToGraph(
  yamlText: string,
  canvasState?: PersistedCanvasState | null,
): ParseWorkflowResult {
  let parsed: ParsedWorkflow;
  try {
    parsed = ((yamlText?.trim() ? load(yamlText) : {}) as ParsedWorkflow | null) ?? {};
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid YAML";
    return {
      nodes: [],
      edges: [],
      viewport: canvasState?.viewport,
      error: { message },
    };
  }

  const blocks = parsed.blocks ?? {};

  const nodeIds = Object.keys(blocks);
  const nodes: Node<StepNodeData>[] = nodeIds.map((nodeId, index) => {
    const block = blocks[nodeId] ?? { type: DEFAULT_STEP_TYPE };
    const persisted = findPersistedPosition(canvasState, nodeId);
    const row = Math.floor(index / 4);
    const col = index % 4;

    return {
      id: nodeId,
      type: "canvasNode",
      position: persisted ?? {
        x: col * DEFAULT_GRID_X,
        y: row * DEFAULT_GRID_Y,
      },
      data: {
        stepId: nodeId,
        name: nodeId,
        stepType: toStepType(block.type),
        status: "idle",
      },
    };
  });

  const edges: Edge[] = [];
  const addEdge = (source: string, target: string | null | undefined, idSuffix: string) => {
    if (!target) return;
    if (!nodeIds.includes(source) || !nodeIds.includes(target)) return;
    edges.push({
      id: `${source}->${target}:${idSuffix}`,
      source,
      target,
      type: "smoothstep",
    });
  };

  const transitions = parsed.workflow?.transitions ?? [];
  transitions.forEach((transition, index) => {
    addEdge(transition.from, transition.to, `t${index}`);
  });

  const conditionalTransitions = parsed.workflow?.conditional_transitions ?? [];
  conditionalTransitions.forEach((conditional, index) => {
    const from = conditional.from;
    if (!from) return;
    Object.entries(conditional).forEach(([key, target]) => {
      if (key === "from") return;
      addEdge(from, target, `c${index}:${key}`);
    });
  });

  return { nodes, edges, viewport: canvasState?.viewport };
}
