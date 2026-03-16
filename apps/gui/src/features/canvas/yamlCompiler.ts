import { dump } from "js-yaml";
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
}

interface CompiledWorkflow {
  version: string;
  blocks: Record<string, BlockDef>;
  workflow: {
    name: string;
    entry: string;
    transitions: Array<{ from: string; to: string }>;
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
  retry:               ["inner_block_ref", "max_retries", "provide_error_context"],
  workflow:            ["workflow_ref", "max_depth", "inputs", "outputs"],
};

// ---------------------------------------------------------------------------
// Universal fields — emitted on all types if present
// ---------------------------------------------------------------------------

const UNIVERSAL_FIELDS = ["output_conditions", "inputs", "outputs"];

// ---------------------------------------------------------------------------
// camelCase ↔ snake_case mappings
// ---------------------------------------------------------------------------

const CAMEL_TO_SNAKE: Record<string, string> = {
  soulRef:            "soul_ref",
  soulRefs:           "soul_refs",
  soulARef:           "soul_a_ref",
  soulBRef:           "soul_b_ref",
  inputBlockIds:      "input_block_ids",
  innerBlockRef:      "inner_block_ref",
  iterations:         "iterations",
  maxRetries:         "max_retries",
  workflowRef:        "workflow_ref",
  evalKey:            "eval_key",
  extractField:       "extract_field",
  outputPath:         "output_path",
  contentKey:         "content_key",
  provideErrorContext: "provide_error_context",
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
// Runtime fields that must never be emitted
// ---------------------------------------------------------------------------

const RUNTIME_FIELDS = new Set(["status", "cost", "executionCost", "name", "stepId", "stepType"]);

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
      result[snakeField] = value;
    }
  }

  return result as BlockDef;
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
    workflowDocument: compiled,
  };
}
