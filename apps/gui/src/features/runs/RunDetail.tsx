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
import { useAttentionItems } from "@/queries/dashboard";
import { CanvasErrorBoundary } from "@/components/shared/ErrorBoundary";
import { Card } from "@runsight/ui/card";
import { Badge } from "@runsight/ui/badge";
import { Button } from "@runsight/ui/button";
import { RunCanvasNode, CanvasNodeComponent, nodeTypes } from "./RunCanvasNode";
import type { RunNodeData } from "./RunCanvasNode";
import { RunInspectorPanel } from "./RunInspectorPanel";
import { RunBottomPanel } from "./RunBottomPanel";
import { RunDetailHeader } from "./RunDetailHeader";
import { getIconForBlockType, mapRunStatus } from "./runDetailUtils";
import { AlertTriangle, Activity } from "lucide-react";

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

  const {
    data: runNodes,
    isLoading: isLoadingNodes,
    isError: isRunNodesError,
    error: runNodesError,
    refetch: refetchRunNodes,
  } = useRunNodes(id || "");
  const { data: runLogs } = useRunLogs(id || "", undefined, { refetchInterval: undefined });
  const { data: attentionData } = useAttentionItems(100);

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
  const attentionItems = useMemo(
    () => (attentionData?.items ?? []).filter((item) => item.run_id === run?.id),
    [attentionData?.items, run?.id],
  );

  if (isLoadingRun || isLoadingNodes) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--surface-primary)]">
        <div className="flex items-center gap-2 text-[var(--text-muted)]">
          <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Loading run details...
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--surface-primary)]">
        <div className="text-[var(--text-muted)]">Run not found</div>
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
        {attentionItems.length > 0 && (
          <div className="border-b border-border-default bg-surface-secondary px-4 py-3">
            <div className="mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning-11" />
              <h2 className="font-mono text-xs uppercase tracking-wider text-muted">
                Attention
              </h2>
            </div>
            <div className="space-y-2">
              {attentionItems.map((item) => {
                const isInfo = item.severity === "info";
                return (
                  <Card key={`${item.run_id}-${item.type}`} className="px-3 py-3">
                    <div className="flex items-start gap-3">
                      <div className={isInfo ? "mt-0.5 text-info-11" : "mt-0.5 text-warning-11"}>
                        {isInfo ? <Activity className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium leading-5 text-heading">{item.title}</p>
                            <p className="mt-1 text-sm leading-5 text-secondary">{item.description}</p>
                          </div>
                          <Badge variant={isInfo ? "info" : "warning"} className="w-fit">
                            {item.type.replaceAll("_", " ")}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 relative">
            {isRunNodesError ? (
              <div className="flex h-full items-center justify-center p-6">
                <Card className="w-full max-w-xl px-6 py-6">
                  <div className="space-y-3">
                    <h2 className="text-lg font-semibold text-heading">Unable to load run graph</h2>
                    <p className="text-sm leading-6 text-secondary">
                      Runsight could not read the node response for this run. Retry to fetch the
                      graph again.
                    </p>
                    {runNodesError instanceof Error ? (
                      <p className="text-sm text-secondary">{runNodesError.message}</p>
                    ) : null}
                    <div className="pt-2">
                      <Button variant="primary" onClick={() => void refetchRunNodes()}>
                        Retry
                      </Button>
                    </div>
                  </div>
                </Card>
              </div>
            ) : (
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
                      if (s === "pending") return "var(--text-muted)";
                      return "var(--interactive-default)";
                    }}
                    maskColor="var(--background-70)"
                  />
                </ReactFlow>
              </CanvasErrorBoundary>
            )}
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
