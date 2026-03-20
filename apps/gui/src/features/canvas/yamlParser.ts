import { parse } from "yaml";
import type { Edge, Node } from "@xyflow/react";
import type { PersistedCanvasState } from "../../store/canvas";
import type { BlockDef, RunsightWorkflowFile, SoulDef, StepNodeData, StepType } from "../../types/schemas/canvas";

export interface ParseWorkflowResult {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  viewport?: PersistedCanvasState["viewport"];
  error?: { message: string };
  souls?: Record<string, SoulDef>;
  config?: Record<string, unknown>;
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

const VALID_STEP_TYPES = new Set<string>([
  "linear", "fanout", "router", "gate",
  "synthesize", "workflow", "loop", "team_lead", "engineering_manager",
  "placeholder", "file_writer", "code",
]);

function toStepType(value: unknown): StepType {
  if (typeof value !== "string") return DEFAULT_STEP_TYPE;
  if (!VALID_STEP_TYPES.has(value)) return DEFAULT_STEP_TYPE;
  return value as StepType;
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
 * Only sets fields that are actually defined in the block (no undefined pollution).
 */
function buildNodeData(nodeId: string, block: BlockDef): StepNodeData {
  const data: StepNodeData = {
    stepId: nodeId,
    name: nodeId,
    stepType: toStepType(block.type),
    status: "idle",
  };

  // Snake-case → camelCase field mappings (only set if defined)
  if (block.soul_ref !== undefined) data.soulRef = block.soul_ref;
  if (block.soul_refs !== undefined) data.soulRefs = block.soul_refs;
  if (block.workflow_ref !== undefined) data.workflowRef = block.workflow_ref;
  if (block.eval_key !== undefined) data.evalKey = block.eval_key;
  if (block.extract_field !== undefined) data.extractField = block.extract_field;
  if (block.inner_block_refs !== undefined) data.innerBlockRefs = block.inner_block_refs;
  if (block.max_rounds !== undefined) data.maxRounds = block.max_rounds;
  if (block.break_condition !== undefined) data.breakCondition = block.break_condition as StepNodeData["breakCondition"];
  if (block.carry_context !== undefined) data.carryContext = convertKeysToCamel(block.carry_context) as Record<string, unknown>;
  if (block.retry_config !== undefined) data.retryConfig = convertKeysToCamel(block.retry_config) as Record<string, unknown>;
  if (block.input_block_ids !== undefined) data.inputBlockIds = block.input_block_ids;
  if (block.output_path !== undefined) data.outputPath = block.output_path;
  if (block.content_key !== undefined) data.contentKey = block.content_key;
  if (block.failure_context_keys !== undefined) data.failureContextKeys = block.failure_context_keys;
  if (block.condition_ref !== undefined) data.conditionRef = block.condition_ref;
  if (block.code !== undefined) data.code = block.code;
  if (block.timeout_seconds !== undefined) data.timeoutSeconds = block.timeout_seconds;
  if (block.allowed_imports !== undefined) data.allowedImports = block.allowed_imports;
  if (block.output_conditions !== undefined) data.outputConditions = block.output_conditions;
  if (block.description !== undefined) data.description = block.description;
  if (block.max_depth !== undefined) data.maxDepth = block.max_depth;

  // WorkflowBlock uses inputs/outputs as string maps → workflowInputs/workflowOutputs
  if (block.type === "workflow") {
    if (block.inputs !== undefined) data.workflowInputs = block.inputs as Record<string, string>;
    if (block.outputs !== undefined) data.workflowOutputs = block.outputs;
  } else {
    if (block.inputs !== undefined) data.inputs = block.inputs as StepNodeData["inputs"];
    if (block.outputs !== undefined) data.outputs = block.outputs;
  }

  return data;
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
      data: buildNodeData(nodeId, block),
    };
  });

  const edges: Edge[] = [];
  const addEdge = (
    source: string,
    target: string | null | undefined,
    idSuffix: string,
    sourceHandle?: string | null,
  ) => {
    if (!target) return;
    if (!nodeIds.includes(source) || !nodeIds.includes(target)) return;
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
  if (parsed.souls !== undefined) result.souls = parsed.souls;
  if (parsed.config !== undefined) result.config = parsed.config;
  return result;
}
