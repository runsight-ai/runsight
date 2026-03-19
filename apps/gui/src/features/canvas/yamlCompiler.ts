import { stringify } from "yaml";
import type { Edge, Node, Viewport } from "@xyflow/react";
import type { PersistedCanvasState } from "../../store/canvas";
import type { StepNodeData, StepType, BlockDef, SoulDef } from "../../types/schemas/canvas";

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  viewport?: Viewport;
  selectedNodeId?: string | null;
  canvasMode?: "dag" | "state-machine";
  workflowName?: string;
  souls?: Record<string, SoulDef>;
  config?: Record<string, unknown>;
}

interface CompiledWorkflow {
  version: string;
  config?: Record<string, unknown>;
  souls?: Record<string, SoulDef>;
  blocks: Record<string, BlockDef>;
  workflow: {
    name: string;
    entry: string;
    transitions: Array<{ from: string; to: string }>;
    conditional_transitions?: Array<Record<string, string | null>>;
  };
}

// ---------------------------------------------------------------------------
// Per-type allowed fields (snake_case, from Python per-type models)
// ---------------------------------------------------------------------------

const BLOCK_TYPE_FIELDS: Record<StepType, string[]> = {
  linear:              ["soul_ref"],
  fanout:              ["soul_refs"],
  synthesize:          ["soul_ref", "input_block_ids"],
  debate:              ["soul_a_ref", "soul_b_ref", "iterations"],
  message_bus:         ["soul_refs", "iterations"],
  router:              ["soul_ref", "condition_ref"],
  team_lead:           ["soul_ref", "failure_context_keys"],
  engineering_manager: ["soul_ref"],
  gate:                ["soul_ref", "eval_key", "extract_field"],
  placeholder:         ["description"],
  file_writer:         ["output_path", "content_key"],
  code:                ["code", "timeout_seconds", "allowed_imports"],
  loop:                ["inner_block_refs", "max_rounds", "break_condition", "carry_context"],
  workflow:            ["workflow_ref", "max_depth", "inputs", "outputs"],
};

// ---------------------------------------------------------------------------
// Universal fields — emitted on all types if present
// ---------------------------------------------------------------------------

const UNIVERSAL_FIELDS = ["output_conditions", "inputs", "outputs", "retry_config"];

// ---------------------------------------------------------------------------
// camelCase ↔ snake_case mappings
// ---------------------------------------------------------------------------

const CAMEL_TO_SNAKE: Record<string, string> = {
  soulRef:            "soul_ref",
  soulRefs:           "soul_refs",
  soulARef:           "soul_a_ref",
  soulBRef:           "soul_b_ref",
  inputBlockIds:      "input_block_ids",
  innerBlockRefs:     "inner_block_refs",
  iterations:         "iterations",
  maxRounds:          "max_rounds",
  breakCondition:     "break_condition",
  carryContext:       "carry_context",
  retryConfig:        "retry_config",
  workflowRef:        "workflow_ref",
  evalKey:            "eval_key",
  extractField:       "extract_field",
  outputPath:         "output_path",
  contentKey:         "content_key",
  conditionRef:       "condition_ref",
  failureContextKeys: "failure_context_keys",
  code:               "code",
  timeoutSeconds:     "timeout_seconds",
  allowedImports:     "allowed_imports",
  outputConditions:   "output_conditions",
  inputs:             "inputs",
  outputs:            "outputs",
  description:        "description",
  maxDepth:           "max_depth",
  // WorkflowBlock special mappings
  workflowInputs:     "inputs",
  workflowOutputs:    "outputs",
};

const SNAKE_TO_CAMEL: Record<string, string> = {};
for (const [camel, snake] of Object.entries(CAMEL_TO_SNAKE)) {
  // Don't overwrite — first entry wins (workflowInputs/workflowOutputs are special)
  if (!(snake in SNAKE_TO_CAMEL)) {
    SNAKE_TO_CAMEL[snake] = camel;
  }
}

// ---------------------------------------------------------------------------
// Recursive camelCase → snake_case key conversion for nested objects
// ---------------------------------------------------------------------------

function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (m) => `_${m.toLowerCase()}`);
}

function convertKeysToSnake(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(convertKeysToSnake);
  if (value !== null && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      result[camelToSnake(k)] = convertKeysToSnake(v);
    }
    return result;
  }
  return value;
}

// Fields whose values need recursive key conversion when compiling
const NESTED_OBJECT_FIELDS = new Set(["carry_context", "retry_config", "break_condition"]);

// ---------------------------------------------------------------------------
// toCompiledBlock — full per-type field emission
// ---------------------------------------------------------------------------

function toCompiledBlock(node: Node<StepNodeData>): BlockDef {
  const data = node.data;
  const stepType: StepType = data?.stepType ?? "placeholder";

  const result: Record<string, unknown> = { type: stepType };

  // Collect allowed snake_case fields for this type
  const typeFields = BLOCK_TYPE_FIELDS[stepType] ?? [];
  const allowedSnakeFields = new Set([...typeFields, ...UNIVERSAL_FIELDS]);

  // For workflow type, inputs/outputs come from workflowInputs/workflowOutputs
  const isWorkflow = stepType === "workflow";

  for (const snakeField of allowedSnakeFields) {
    // Determine which camelCase field to read from node.data
    let camelField: string | undefined;

    if (isWorkflow && snakeField === "inputs") {
      camelField = "workflowInputs";
    } else if (isWorkflow && snakeField === "outputs") {
      camelField = "workflowOutputs";
    } else {
      camelField = SNAKE_TO_CAMEL[snakeField] ?? snakeField;
    }

    const value = data[camelField];

    if (value !== undefined && value !== null) {
      result[snakeField] = NESTED_OBJECT_FIELDS.has(snakeField) && typeof value === "object"
        ? convertKeysToSnake(value)
        : value;
    }
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
  // version → config → souls → blocks → workflow
  const compiled: CompiledWorkflow = { version: "1.0" } as CompiledWorkflow;

  if (input.config && Object.keys(input.config).length > 0) {
    compiled.config = input.config;
  }

  if (input.souls && Object.keys(input.souls).length > 0) {
    compiled.souls = input.souls;
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
