import { useState, useCallback, useMemo, useEffect, memo } from "react";
import { useParams } from "react-router";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useRun, useRunNodes, useRunLogs } from "@/queries/runs";
import { CanvasErrorBoundary } from "@/components/shared/ErrorBoundary";
import { mapRunStatus, getIconForBlockType } from "@/utils/colors";

import { RunCanvasNode, CanvasNodeComponent, nodeTypes } from "./RunCanvasNode";
import type { RunNodeData } from "./RunCanvasNode";
import { RunInspectorPanel } from "./RunInspectorPanel";
import { RunBottomPanel } from "./RunBottomPanel";
import { RunDetailHeader } from "./RunDetailHeader";

// Re-export RunCanvasNode for external consumers
export { RunCanvasNode };

// Backward-compat memo wrapper (RUN-241) — nodeTypes uses the RunCanvasNode variant
export const CanvasNode = memo(CanvasNodeComponent, (prev, next) => {
  return prev.data.name === next.data.name
    && prev.data.status === next.data.status
    && prev.data.stepType === next.data.stepType;
});

// ---------------------------------------------------------------------------
// Inner component — owns state & data fetching
// ---------------------------------------------------------------------------

function RunDetailInner() {
  const { id } = useParams<{ id: string }>();

  const { data: run, isLoading: isLoadingRun } = useRun(id || "", {
    refetchInterval: (query) => {
      const status = (query?.state as { data?: { status: string } })?.data?.status;
      if (status === "running" || status === "pending") return 2000;
      return false;
    },
  });

  const { data: runNodes, isLoading: isLoadingNodes } = useRunNodes(id || "");
  const { data: runLogs } = useRunLogs(id || "", undefined, { refetchInterval: undefined });

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<RunNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<Node<RunNodeData> | null>(null);

  const buildCanvasFromRun = useCallback(() => {
    if (!runNodes) return;
    const canvasNodes: Node<RunNodeData>[] = runNodes.map((node, index) => ({
      id: node.node_id,
      type: "canvasNode",
      position: { x: 100 + (index % 3) * 300, y: 100 + Math.floor(index / 3) * 200 },
      data: {
        name: node.block_type,
        soulRef: node.block_type,
        model: node.block_type,
        status: mapRunStatus(node.status),
        executionCost: node.cost_usd,
        duration: node.duration_seconds || undefined,
        tokens: node.tokens as { input?: number; output?: number; total?: number } | undefined,
        error: node.error || undefined,
        icon: getIconForBlockType(node.block_type),
      },
    }));
    setNodes(canvasNodes);

    const canvasEdges: Edge[] = [];
    for (let i = 0; i < canvasNodes.length - 1; i++) {
      const cur = canvasNodes[i];
      const nxt = canvasNodes[i + 1];
      if (cur && nxt) {
        canvasEdges.push({
          id: `e${i}`,
          source: cur.id,
          target: nxt.id,
          style: { stroke: "var(--border-default)", strokeWidth: 2 } as React.CSSProperties,
        });
      }
    }
    setEdges(canvasEdges);
  }, [runNodes, setNodes, setEdges]);

  useEffect(() => { buildCanvasFromRun(); }, [buildCanvasFromRun]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node<RunNodeData>) => { setSelectedNode(node); }, []);
  const onPaneClick = useCallback(() => { setSelectedNode(null); }, []);

  const logs = useMemo(() => runLogs?.items || [], [runLogs]);

  if (isLoadingRun || isLoadingNodes) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--surface-primary)]">
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Loading run details...
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--surface-primary)]">
        <div className="text-[var(--muted-foreground)]">Run not found</div>
      </div>
    );
  }

  const isFailed = run.status === "failed" || run.status === "error";

  return (
    <div className="flex-1 flex overflow-hidden bg-[var(--surface-primary)]">
      <main className="flex-1 flex flex-col min-w-0">
        <RunDetailHeader
          run={run}
          totalCostUsd={run.total_cost_usd}
          totalTokens={run.total_tokens}
        />

        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 relative">
            <CanvasErrorBoundary>
              <ReactFlow
                nodes={nodes} edges={edges}
                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick} onPaneClick={onPaneClick}
                nodeTypes={nodeTypes} nodesDraggable={false} nodesConnectable={false}
                elementsSelectable fitView fitViewOptions={{ padding: 0.2 }}
                minZoom={0.1} maxZoom={4} className="bg-[var(--surface-primary)]"
              >
                <Background color="var(--border-default)" gap={20} size={1} style={{ opacity: 0.3 }} />
                <Controls className="!bg-[var(--surface-secondary)] !border-[var(--border-default)]" />
                <MiniMap
                  className="!bg-[var(--surface-secondary)]/90 !border-[var(--border-default)]"
                  nodeColor={(node) => {
                    const s = (node.data as RunNodeData)?.status;
                    if (s === "completed") return "var(--success-9)";
                    if (s === "failed") return "var(--danger-9)";
                    if (s === "pending") return "var(--muted-foreground)";
                    return "var(--interactive-default)";
                  }}
                  maskColor="var(--background-70)"
                />
              </ReactFlow>
            </CanvasErrorBoundary>
          </div>
          <RunInspectorPanel selectedNode={selectedNode} onClose={() => setSelectedNode(null)} />
        </div>

        <RunBottomPanel logs={logs} executionComplete executionFailed={isFailed} finalDuration={run.duration_seconds || 0} />
      </main>
    </div>
  );
}

export const Component = () => (
  <ReactFlowProvider>
    <RunDetailInner />
  </ReactFlowProvider>
);

export default Component;
