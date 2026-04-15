import type { Edge, Node } from "@xyflow/react";

import type { PersistedCanvasState } from "@/store/canvas";
import type { StepNodeData } from "@/types/schemas/canvas";

import { parseWorkflowYamlToGraph } from "./yamlParser";

const HORIZONTAL_SPACING = 320;
const VERTICAL_SPACING = 180;
const DEFAULT_VIEWPORT = { x: 0, y: 0, zoom: 1 };

type SurfaceNodeType = "start" | "soul";

function getPersistedPositions(
  canvasState: PersistedCanvasState | null | undefined,
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const rawNodes = canvasState?.nodes;

  if (!Array.isArray(rawNodes)) {
    return positions;
  }

  for (const rawNode of rawNodes) {
    if (typeof rawNode !== "object" || rawNode === null) {
      continue;
    }

    const node = rawNode as {
      id?: unknown;
      position?: { x?: unknown; y?: unknown };
    };
    if (
      typeof node.id === "string"
      && typeof node.position?.x === "number"
      && typeof node.position?.y === "number"
    ) {
      positions.set(node.id, { x: node.position.x, y: node.position.y });
    }
  }

  return positions;
}

function computeNodeDepths(
  nodeIds: string[],
  edges: Edge[],
  entryNodeId?: string,
): Map<string, number> {
  const adjacency = new Map<string, string[]>();
  const incoming = new Map<string, number>();

  for (const nodeId of nodeIds) {
    adjacency.set(nodeId, []);
    incoming.set(nodeId, 0);
  }

  for (const edge of edges) {
    if (!edge.source || !edge.target) {
      continue;
    }
    if (!adjacency.has(edge.source) || !incoming.has(edge.target)) {
      continue;
    }
    adjacency.get(edge.source)?.push(edge.target);
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  }

  const orderedStarts = [
    ...(entryNodeId && nodeIds.includes(entryNodeId) ? [entryNodeId] : []),
    ...nodeIds
      .filter((nodeId) => nodeId !== entryNodeId && (incoming.get(nodeId) ?? 0) === 0)
      .sort(),
  ];

  const depths = new Map<string, number>();
  const queue = [...orderedStarts];

  for (const nodeId of orderedStarts) {
    depths.set(nodeId, 0);
  }

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      continue;
    }

    const currentDepth = depths.get(current) ?? 0;
    for (const target of adjacency.get(current) ?? []) {
      const nextDepth = currentDepth + 1;
      const previousDepth = depths.get(target);
      if (previousDepth == null || nextDepth > previousDepth) {
        depths.set(target, nextDepth);
        queue.push(target);
      }
    }
  }

  let fallbackDepth = depths.size > 0 ? Math.max(...depths.values()) + 1 : 0;
  for (const nodeId of nodeIds) {
    if (!depths.has(nodeId)) {
      depths.set(nodeId, fallbackDepth);
      fallbackDepth += 1;
    }
  }

  return depths;
}

function layoutNodes(
  parsedNodes: Node<StepNodeData>[],
  edges: Edge[],
  entryNodeId?: string,
  canvasState?: PersistedCanvasState | null,
): Array<Node<StepNodeData, SurfaceNodeType>> {
  const positions = getPersistedPositions(canvasState);
  const nodeIds = parsedNodes.map((node) => node.id);
  const depths = computeNodeDepths(nodeIds, edges, entryNodeId);
  const rowsByDepth = new Map<number, number>();

  return parsedNodes.map((node) => {
    const persistedPosition = positions.get(node.id);
    const depth = depths.get(node.id) ?? 0;
    const row = rowsByDepth.get(depth) ?? 0;
    rowsByDepth.set(depth, row + 1);

    return {
      ...node,
      type: node.id === entryNodeId ? "start" : "soul",
      position: persistedPosition ?? {
        x: depth * HORIZONTAL_SPACING,
        y: row * VERTICAL_SPACING,
      },
    };
  });
}

export function hasRenderableCanvasState(
  canvasState: PersistedCanvasState | Record<string, unknown> | null | undefined,
): canvasState is PersistedCanvasState {
  const nodes = (canvasState as PersistedCanvasState | undefined)?.nodes;
  return (
    Array.isArray(nodes)
    && nodes.some((node) => {
      if (typeof node !== "object" || node === null) {
        return false;
      }
      const candidate = node as {
        type?: unknown;
        data?: unknown;
      };
      return typeof candidate.type === "string" && typeof candidate.data === "object";
    })
  );
}

export function buildWorkflowLayout(
  yaml: string,
  canvasState?: PersistedCanvasState | null,
): PersistedCanvasState {
  const parsed = parseWorkflowYamlToGraph(yaml, canvasState);
  const nodes = layoutNodes(
    parsed.nodes,
    parsed.edges,
    parsed.entryNodeId,
    canvasState,
  );

  return {
    nodes: nodes as unknown as Record<string, unknown>[],
    edges: parsed.edges as unknown as Record<string, unknown>[],
    viewport: parsed.viewport ?? canvasState?.viewport ?? DEFAULT_VIEWPORT,
    selected_node_id: canvasState?.selected_node_id ?? null,
    canvas_mode: canvasState?.canvas_mode ?? "dag",
  };
}
