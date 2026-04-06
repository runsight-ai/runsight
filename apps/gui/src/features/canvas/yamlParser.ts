import { parse } from "yaml";
import type { Edge, Node } from "@xyflow/react";
import type { PersistedCanvasState } from "../../store/canvas";
import type { BlockDef, RunsightWorkflowFile, StepNodeData, StepType } from "../../types/schemas/canvas";

export interface ParseWorkflowResult {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  viewport?: PersistedCanvasState["viewport"];
  error?: { message: string };
  config?: Record<string, unknown>;
}

type ParsedWorkflow = Partial<RunsightWorkflowFile> & {
  blocks?: Record<string, BlockDef>;
  workflow?: {
    entry?: string;
    transitions?: Array<{ from: string; to: string | null }>;
    conditional_transitions?: Array<Record<string, string | null>>;
  };
  /** RUN-748: inline souls are valid shorthand — field is parsed and available, no warning emitted */
  souls?: Record<string, unknown>;
};

const DEFAULT_GRID_X = 280;
const DEFAULT_GRID_Y = 160;

function toStepType(value: unknown): { type?: StepType; error?: string } {
  if (typeof value !== "string") return { type: "linear" as StepType, error: `Invalid block type: expected string, got ${typeof value}` };
  return { type: value as StepType };
}

// ---------------------------------------------------------------------------
// Recursive snake_case → camelCase key conversion for nested objects
// ---------------------------------------------------------------------------

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

function convertKeysToCamel(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(convertKeysToCamel);
  if (value !== null && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      result[snakeToCamel(k)] = convertKeysToCamel(v);
    }
    return result;
  }
  return value;
}

/**
 * Build StepNodeData from a block ID and its YAML BlockDef.
 * Uses a single generic path for all block types — no hardcoded field lists.
 */
function buildNodeData(nodeId: string, block: BlockDef): { data?: StepNodeData; error?: string } {
  const stepTypeResult = toStepType(block.type);
  if (!stepTypeResult.type) {
    return { error: stepTypeResult.error ?? `Unsupported block type for "${nodeId}"` };
  }

  const data: StepNodeData = {
    stepId: nodeId,
    name: nodeId,
    stepType: stepTypeResult.type,
    status: "idle",
  };

  const isWorkflow = block.type === "workflow";

  for (const [key, value] of Object.entries(block as Record<string, unknown>)) {
    if (key === "type") continue;
    if (value === undefined || value === null) continue;

    // Workflow special case: inputs → workflowInputs, outputs → workflowOutputs
    if (isWorkflow && key === "inputs") {
      data.workflowInputs = value as Record<string, string>;
      continue;
    }
    if (isWorkflow && key === "outputs") {
      data.workflowOutputs = value as Record<string, string>;
      continue;
    }

    const camelKey = snakeToCamel(key);
    // Apply recursive key conversion only to plain objects (config objects like
    // carry_context, retry_config, auth_config). Arrays (like output_conditions,
    // inner_block_refs) are passed through as-is to preserve their schema structure.
    if (typeof value === "object" && !Array.isArray(value)) {
      data[camelKey] = convertKeysToCamel(value);
    } else {
      data[camelKey] = value;
    }
  }

  return { data, error: stepTypeResult.error };
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
    const raw = yamlText?.trim() ? parse(yamlText) : {};
    if (raw !== null && typeof raw === "object" && !Array.isArray(raw) && "" in (raw as Record<string, unknown>)) {
      throw new Error("Invalid YAML: empty key at top level");
    }
    parsed = (raw as ParsedWorkflow | null) ?? {};
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

  const blockIds = Object.keys(blocks);
  const buildErrors: string[] = [];
  const nodes: Node<StepNodeData>[] = [];

  blockIds.forEach((nodeId) => {
    const block = blocks[nodeId] ?? ({ type: "linear" } as BlockDef);
    const persisted = findPersistedPosition(canvasState, nodeId);
    const built = buildNodeData(nodeId, block);
    if (built.error) {
      buildErrors.push(`Block "${nodeId}": ${built.error}`);
      if (!built.data) return;
    }
    if (!built.data) return;

    const positionIndex = nodes.length;
    const row = Math.floor(positionIndex / 4);
    const col = positionIndex % 4;

    nodes.push({
      id: nodeId,
      type: "canvasNode",
      position: persisted ?? {
        x: col * DEFAULT_GRID_X,
        y: row * DEFAULT_GRID_Y,
      },
      data: built.data,
    });
  });
  const nodeIds = new Set(nodes.map((node) => node.id));

  const edges: Edge[] = [];
  const addEdge = (
    source: string,
    target: string | null | undefined,
    idSuffix: string,
    sourceHandle?: string | null,
  ) => {
    if (!target) return;
    if (!nodeIds.has(source) || !nodeIds.has(target)) return;
    edges.push({
      id: `${source}->${target}:${idSuffix}`,
      source,
      target,
      sourceHandle: sourceHandle ?? null,
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
      // Set sourceHandle to the decision key so the compiler can reconstruct
      // conditional_transitions correctly. "default" key maps to sourceHandle
      // null (the compiler treats null as "default").
      const handle = key === "default" ? null : key;
      addEdge(from, target, `c${index}:${key}`, handle);
    });
  });

  const result: ParseWorkflowResult = { nodes, edges, viewport: canvasState?.viewport };
  if (buildErrors.length > 0) result.error = { message: buildErrors.join("; ") };
  if (parsed.config !== undefined) result.config = parsed.config;
  return result;
}
