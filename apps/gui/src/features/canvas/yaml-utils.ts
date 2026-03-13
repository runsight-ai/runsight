import yaml from "js-yaml";
import type { Node, Edge } from "@xyflow/react";
import type {
  StepNodeData,
  StepType,
  RunsightWorkflowFile,
  BlockDef,
  TransitionDef,
  ConditionalTransitionDef,
} from "@/types/schemas/canvas";
import type { CanvasNodeData } from "./CanvasNode";

/** Parse result: nodes/edges are in React Flow format for direct use */
export interface ParseResult {
  success: boolean;
  data?: {
    nodes: Node<StepNodeData>[];
    edges: Edge[];
    workflow?: { name: string; entry?: string };
  };
  errors: string[];
  nodeCount: number;
  edgeCount: number;
}

/** Workflow metadata passed to serializer */
export interface WorkflowMetaInput {
  id?: string;
  name?: string;
  description?: string;
}

/** Normalize node data to StepNodeData (fills defaults for incomplete data) */
function normalizeToStepData(
  nodeId: string,
  data: StepNodeData
): StepNodeData {
  if (data.stepId && data.stepType) return data;
  return {
    stepId: nodeId,
    name: data.name ?? nodeId,
    stepType: data.stepType ?? "linear",
    soulRef: data.soulRef,
    status: data.status ?? "idle",
    cost: data.cost,
    executionCost: data.executionCost,
  };
}

/**
 * Convert StepNodeData to BlockDef for YAML serialization
 */
function nodeDataToBlockDef(data: StepNodeData): BlockDef {
  const block: BlockDef = {
    type: data.stepType,
  };

  if (data.soulRef) block.soul_ref = data.soulRef;
  if (data.soulRefs?.length) block.soul_refs = data.soulRefs;
  if (data.soulARef) block.soul_a_ref = data.soulARef;
  if (data.soulBRef) block.soul_b_ref = data.soulBRef;
  if (data.iterations !== undefined) block.iterations = data.iterations;
  if (data.workflowRef) block.workflow_ref = data.workflowRef;
  if (data.evalKey) block.eval_key = data.evalKey;
  if (data.extractField) block.extract_field = data.extractField;
  if (data.innerBlockRef) block.inner_block_ref = data.innerBlockRef;
  if (data.maxRetries !== undefined) block.max_retries = data.maxRetries;
  if (data.inputBlockIds?.length) block.input_block_ids = data.inputBlockIds;
  if (data.outputPath) block.output_path = data.outputPath;
  if (data.contentKey) block.content_key = data.contentKey;
  if (data.failureContextKeys?.length) block.failure_context_keys = data.failureContextKeys;

  return block;
}

/**
 * Serialize React Flow nodes and edges to RunsightWorkflowFile YAML format.
 * Accepts StepNodeData node shapes.
 */
export function serializeToYAML(
  nodes: Node<CanvasNodeData>[],
  edges: Edge[],
  workflowData?: WorkflowMetaInput
): string {
  const blocks: Record<string, BlockDef> = {};
  const transitions: TransitionDef[] = [];
  const canvasPositions: Record<string, { x: number; y: number }> = {};

  const sourceIds = new Set(edges.map((e) => e.source));
  const outgoingBySource = new Map<string, Edge[]>();
  for (const edge of edges) {
    const list = outgoingBySource.get(edge.source) ?? [];
    list.push(edge);
    outgoingBySource.set(edge.source, list);
  }

  for (const node of nodes) {
    const data = normalizeToStepData(node.id, node.data as StepNodeData);
    const stepId = data.stepId ?? node.id;
    blocks[stepId] = nodeDataToBlockDef(data);
    canvasPositions[stepId] = { x: node.position.x, y: node.position.y };
  }

  const entryBlockId =
    nodes.find((n) => !sourceIds.has(n.id))?.id ??
    nodes[0]?.id ??
    "";

  for (const edge of edges) {
    if (edge.target) {
      transitions.push({
        from: edge.source,
        to: edge.target,
      });
    }
  }

  for (const node of nodes) {
    const outgoing = outgoingBySource.get(node.id) ?? [];
    if (outgoing.length === 0) {
      transitions.push({
        from: node.id,
        to: null,
      });
    }
  }

  const conditionalTransitions: ConditionalTransitionDef[] = [];
  const conditionalEdges = edges.filter((e) => e.sourceHandle);
  if (conditionalEdges.length > 0) {
    const bySource = new Map<string, ConditionalTransitionDef>();
    for (const edge of conditionalEdges) {
      let ct = bySource.get(edge.source);
      if (!ct) {
        ct = { from: edge.source };
        bySource.set(edge.source, ct);
      }
      const key = edge.sourceHandle ?? "default";
      if (edge.target) {
        ct[key] = edge.target;
      } else {
        ct.default = null;
      }
    }
    conditionalTransitions.push(...bySource.values());
  }

  const workflowName =
    workflowData?.name ?? "Untitled Workflow";

  const doc: RunsightWorkflowFile = {
    version: "1.0",
    config: {
      ...(workflowData?.id && { workflow_id: workflowData.id }),
      canvas_positions: canvasPositions,
    },
    souls: {},
    blocks,
    workflow: {
      name: workflowName,
      entry: entryBlockId,
      transitions,
      ...(conditionalTransitions.length > 0 && {
        conditional_transitions: conditionalTransitions,
      }),
    },
  };

  return yaml.dump(doc, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
  });
}

/**
 * Parse RunsightWorkflowFile YAML string to React Flow nodes and edges
 */
export function parseYAML(yamlString: string): ParseResult {
  const errors: string[] = [];
  const nodes: Node<StepNodeData>[] = [];
  const edges: Edge[] = [];

  try {
    const parsed = yaml.load(yamlString) as unknown;
    if (!parsed || typeof parsed !== "object") {
      return {
        success: false,
        errors: ["Invalid YAML: expected object"],
        nodeCount: 0,
        edgeCount: 0,
      };
    }

    const doc = parsed as Record<string, unknown>;
    const blocks = doc.blocks as Record<string, Record<string, unknown>> | undefined;
    const workflow = doc.workflow as Record<string, unknown> | undefined;
    const config = doc.config as Record<string, unknown> | undefined;
    const canvasPositions = config?.canvas_positions as Record<
      string,
      { x: number; y: number }
    > | undefined;

    if (!blocks || typeof blocks !== "object") {
      errors.push("Missing or invalid 'blocks'");
    }
    if (!workflow || typeof workflow !== "object") {
      errors.push("Missing or invalid 'workflow'");
    }

    if (errors.length > 0) {
      return {
        success: false,
        errors,
        nodeCount: 0,
        edgeCount: 0,
      };
    }

    const blocksRecord = blocks as Record<string, Record<string, unknown>>;
    const blockIds = Object.keys(blocksRecord);
    const posByBlock = canvasPositions ?? {};
    let y = 0;
    const defaultSpacing = 100;

    for (const blockId of blockIds) {
      const block = blocksRecord[blockId] as Record<string, unknown>;
      const type = (block?.type as StepType) ?? "placeholder";
      const pos = posByBlock[blockId] ?? { x: 0, y: y * defaultSpacing };
      y += 1;

      const stepData: StepNodeData = {
        stepId: blockId,
        name: blockId,
        stepType: type,
        status: "idle",
      };

      if (block?.soul_ref) stepData.soulRef = block.soul_ref as string;
      if (block?.soul_refs) stepData.soulRefs = block.soul_refs as string[];
      if (block?.soul_a_ref) stepData.soulARef = block.soul_a_ref as string;
      if (block?.soul_b_ref) stepData.soulBRef = block.soul_b_ref as string;
      if (block?.iterations !== undefined) stepData.iterations = block.iterations as number;
      if (block?.workflow_ref) stepData.workflowRef = block.workflow_ref as string;
      if (block?.eval_key) stepData.evalKey = block.eval_key as string;
      if (block?.extract_field) stepData.extractField = block.extract_field as string;
      if (block?.inner_block_ref) stepData.innerBlockRef = block.inner_block_ref as string;
      if (block?.max_retries !== undefined) stepData.maxRetries = block.max_retries as number;
      if (block?.input_block_ids) stepData.inputBlockIds = block.input_block_ids as string[];
      if (block?.output_path) stepData.outputPath = block.output_path as string;
      if (block?.content_key) stepData.contentKey = block.content_key as string;
      if (block?.failure_context_keys)
        stepData.failureContextKeys = block.failure_context_keys as string[];

      nodes.push({
        id: blockId,
        type: "canvasNode",
        position: pos,
        data: stepData,
      });
    }

    const transitions = (workflow?.transitions as Array<{ from: string; to: string | null }>) ?? [];
    let edgeId = 0;
    for (const t of transitions) {
      if (t.to) {
        edges.push({
          id: `e${edgeId++}`,
          source: t.from,
          target: t.to,
        });
      }
    }

    const conditionalTransitions =
      (workflow?.conditional_transitions as Array<Record<string, unknown>>) ?? [];
    for (const ct of conditionalTransitions) {
      const from = ct.from as string;
      for (const [key, target] of Object.entries(ct)) {
        if (key === "from" || target === undefined) continue;
        const targetStr = target as string | null;
        if (targetStr) {
          edges.push({
            id: `e${edgeId++}`,
            source: from,
            target: targetStr,
            sourceHandle: key,
            data: { condition: key },
          });
        }
      }
    }

    const workflowName = (workflow?.name as string) ?? "";
    const entry = (workflow?.entry as string) ?? blockIds[0];

    return {
      success: errors.length === 0,
      data: {
        nodes,
        edges,
        workflow: { name: workflowName, entry },
      },
      errors,
      nodeCount: nodes.length,
      edgeCount: edges.length,
    };
  } catch (err) {
    return {
      success: false,
      errors: [`Parse error: ${err instanceof Error ? err.message : String(err)}`],
      nodeCount: 0,
      edgeCount: 0,
    };
  }
}

/**
 * Convert parsed nodes to React Flow nodes (identity when using new format)
 */
export function yamlNodesToFlowNodes(
  parsedNodes: Node<StepNodeData>[]
): Node<StepNodeData>[] {
  return parsedNodes;
}

/**
 * Convert parsed edges to React Flow edges (identity when using new format)
 */
export function yamlEdgesToFlowEdges(parsedEdges: Edge[]): Edge[] {
  return parsedEdges;
}

/**
 * Validate YAML against RunsightWorkflowFile structure
 */
export function validateYAML(yamlString: string): {
  isValid: boolean;
  errors: string[];
} {
  const result = parseYAML(yamlString);
  return {
    isValid: result.success,
    errors: result.errors,
  };
}
