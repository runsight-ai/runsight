import { stringify } from "yaml";
import type { Edge, Node, Viewport } from "@xyflow/react";
import type { PersistedCanvasState } from "../../store/canvas";
import type { StepNodeData, StepType, BlockDef } from "../../types/schemas/canvas";

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  viewport?: Viewport;
  selectedNodeId?: string | null;
  canvasMode?: "dag" | "state-machine";
  workflowName?: string;
  config?: Record<string, unknown>;
}

interface CompiledWorkflow {
  version: string;
  config?: Record<string, unknown>;
  blocks: Record<string, BlockDef>;
  workflow: {
    name: string;
    entry: string;
    transitions: Array<{ from: string; to: string }>;
    conditional_transitions?: Array<Record<string, string | null>>;
  };
}

// ---------------------------------------------------------------------------
// Recursive camelCase → snake_case key conversion for nested objects
// ---------------------------------------------------------------------------

function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (m) => `_${m.toLowerCase()}`);
}

function isCamelCase(str: string): boolean {
  return /[a-z][A-Z]/.test(str);
}

function convertKeysToSnake(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(convertKeysToSnake);
  if (value !== null && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      // Only convert keys that look like camelCase (e.g., sourceBlocks, injectAs).
      // Preserve keys that use other conventions (e.g., HTTP headers: Content-Type).
      const key = isCamelCase(k) ? camelToSnake(k) : k;
      result[key] = convertKeysToSnake(v);
    }
    return result;
  }
  return value;
}

// ---------------------------------------------------------------------------
// toCompiledBlock — generic field emission for all block types
// ---------------------------------------------------------------------------

// Runtime/meta fields that must never be emitted in compiled blocks
const RUNTIME_FIELDS = new Set(["stepId", "name", "stepType", "status", "cost", "executionCost"]);

function toCompiledBlock(node: Node<StepNodeData>): BlockDef {
  const data = node.data;
  if (!data?.stepType) {
    throw new Error(`Node "${node.id}" has no stepType — cannot compile to YAML`);
  }
  const stepType: StepType = data.stepType;

  const result: Record<string, unknown> = { type: stepType };

  // For workflow type, workflowInputs/workflowOutputs map to inputs/outputs
  const isWorkflow = stepType === "workflow";

  for (const [camelField, value] of Object.entries(data)) {
    if (RUNTIME_FIELDS.has(camelField)) continue;
    if (value === undefined || value === null) continue;

    // Workflow special case: workflowInputs → inputs, workflowOutputs → outputs
    if (isWorkflow && camelField === "workflowInputs") {
      result["inputs"] = typeof value === "object" ? convertKeysToSnake(value) : value;
      continue;
    }
    if (isWorkflow && camelField === "workflowOutputs") {
      result["outputs"] = typeof value === "object" ? convertKeysToSnake(value) : value;
      continue;
    }

    const snakeField = camelToSnake(camelField);

    // Skip fields already emitted (e.g. from workflow special case)
    if (result[snakeField] !== undefined) continue;

    result[snakeField] = typeof value === "object" ? convertKeysToSnake(value) : value;
  }

  return result as unknown as BlockDef;
}

// ---------------------------------------------------------------------------
// Build set of node IDs that have output_conditions
// ---------------------------------------------------------------------------

function getConditionedNodeIds(nodes: Node<StepNodeData>[]): Set<string> {
  return new Set(
    nodes
      .filter((n) => n.data?.outputConditions && n.data.outputConditions.length > 0)
      .map((n) => n.id),
  );
}

// ---------------------------------------------------------------------------
// toTransitions — plain edges only (excludes edges from conditioned nodes)
// ---------------------------------------------------------------------------

function toTransitions(edges: Edge[], conditionedNodeIds: Set<string>) {
  return edges
    .filter((edge) => Boolean(edge.source) && Boolean(edge.target))
    .filter((edge) => !conditionedNodeIds.has(edge.source))
    .map((edge) => ({
      from: edge.source,
      to: edge.target,
    }));
}

// ---------------------------------------------------------------------------
// toConditionalTransitions — edges from nodes with outputConditions
// ---------------------------------------------------------------------------

function toConditionalTransitions(
  edges: Edge[],
  conditionedNodeIds: Set<string>,
): Record<string, string | null>[] {
  const conditionalEdges = edges.filter(
    (e) => Boolean(e.source) && Boolean(e.target) && conditionedNodeIds.has(e.source),
  );

  const grouped = new Map<string, Record<string, string | null>>();
  for (const edge of conditionalEdges) {
    if (!grouped.has(edge.source)) {
      grouped.set(edge.source, { from: edge.source });
    }
    const entry = grouped.get(edge.source)!;
    const key = edge.sourceHandle ?? "default";
    entry[key] = edge.target;
  }

  return Array.from(grouped.values());
}

function toPersistedCanvasState({
  nodes,
  edges,
  viewport,
  selectedNodeId,
  canvasMode,
}: CompileInput): PersistedCanvasState {
  const minimalNodes = nodes.map((node) => ({
    id: node.id,
    position: {
      x: node.position.x,
      y: node.position.y,
    },
  }));

  const minimalEdges = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle ?? null,
    targetHandle: edge.targetHandle ?? null,
  }));

  return {
    nodes: minimalNodes as unknown as Record<string, unknown>[],
    edges: minimalEdges as unknown as Record<string, unknown>[],
    viewport: viewport ?? { x: 0, y: 0, zoom: 1 },
    selected_node_id: selectedNodeId ?? null,
    canvas_mode: canvasMode ?? "dag",
  };
}

export function compileGraphToWorkflowYaml(input: CompileInput): {
  yaml: string;
  canvasState: PersistedCanvasState;
  workflowDocument: CompiledWorkflow;
} {
  const nodes = input.nodes ?? [];
  const edges = input.edges ?? [];
  const entry = nodes[0]?.id ?? "start";

  const blocks = nodes.reduce<Record<string, BlockDef>>((acc, node) => {
    acc[node.id] = toCompiledBlock(node);
    return acc;
  }, {});

  // Build compiled object with keys in Python schema order:
  // version → config → blocks → workflow
  const compiled: CompiledWorkflow = { version: "1.0" } as CompiledWorkflow;

  if (input.config && Object.keys(input.config).length > 0) {
    compiled.config = input.config;
  }

  compiled.blocks = blocks;

  const conditionedNodeIds = getConditionedNodeIds(nodes);
  const conditionalTransitions = toConditionalTransitions(edges, conditionedNodeIds);

  compiled.workflow = {
    name: input.workflowName ?? "Workflow",
    entry,
    transitions: toTransitions(edges, conditionedNodeIds),
  };

  if (conditionalTransitions.length > 0) {
    compiled.workflow.conditional_transitions = conditionalTransitions;
  }

  return {
    yaml: stringify(compiled, { lineWidth: 120, aliasDuplicateObjects: false }),
    canvasState: toPersistedCanvasState(input),
    workflowDocument: compiled,
  };
}
