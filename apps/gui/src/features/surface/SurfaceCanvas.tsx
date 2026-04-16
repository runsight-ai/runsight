"use client";

import { useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  type Edge,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useCanvasStore } from "@/store/canvas";
import { selectContextAuditEdges, useContextAuditStore } from "@/store/contextAudit";
import { nodeTypes } from "./nodes";

interface SurfaceCanvasProps {
  isDraggable?: boolean;
  connectionsAllowed?: boolean;
  deletionAllowed?: boolean;
  runId?: string;
  onNodeClick?: (nodeId: string) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
  onPaneClick?: () => void;
}

export function SurfaceCanvas({
  isDraggable = true,
  connectionsAllowed = true,
  deletionAllowed = true,
  onNodeClick: onNodeClickProp,
  onNodeDoubleClick: onNodeDoubleClickProp,
  onPaneClick: onPaneClickProp,
  runId,
}: SurfaceCanvasProps) {
  const { nodes, edges, onNodesChange, onEdgesChange, selectNode } =
    useCanvasStore();
  const namespace = "results";
  const contextOverlayEdges = useContextAuditStore((state) =>
    runId
      ? selectContextAuditEdges(runId)(state)
          .filter((edge) => edge.namespace === namespace && edge.source !== "workflow")
          .map<Edge>((edge) => ({
            id: `context-overlay:${edge.id}`,
            source: edge.source,
            target: edge.target,
            type: "straight",
            className: "context-overlay",
            label: edge.inputName ?? "context",
            style: {
              stroke: "var(--info-9)",
              strokeDasharray: "4 4",
              strokeWidth: 1.5,
            },
            data: { context: true, namespace: edge.namespace },
          }))
      : [],
  );

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      selectNode(node.id);
      onNodeClickProp?.(node.id);
    },
    [selectNode, onNodeClickProp]
  );

  const handleNodeDoubleClick: NodeMouseHandler = useCallback(
    (_, node) => {
      onNodeDoubleClickProp?.(node.id);
    },
    [onNodeDoubleClickProp]
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
    onPaneClickProp?.();
  }, [selectNode, onPaneClickProp]);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      {/* React Flow Canvas - Unified Workflow View (no DAG/State Machine toggle per spec) */}
      <div className="h-full min-h-0 flex-1">
        <ReactFlow
          nodes={nodes}
          edges={[...edges, ...contextOverlayEdges]}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          nodesDraggable={isDraggable}
          nodesConnectable={connectionsAllowed}
          deleteKeyCode={deletionAllowed ? "Backspace" : null}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          defaultEdgeOptions={{
            style: { stroke: "var(--border-default)", strokeWidth: 1.5 },
            type: "straight",
            markerEnd: {
              type: "arrowclosed",
              width: 10,
              height: 10,
              color: "var(--text-muted)",
            },
          }}
          proOptions={{ hideAttribution: true }}
          className="h-full bg-surface"
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={28}
            size={0.8}
            color="var(--text-muted)"
            className="opacity-20"
          />
          <Controls
            showInteractive={false}
            className="!bg-panel !border-border-default !shadow-lg [&_button]:!bg-surface-tertiary [&_button]:!border-border-default [&_button]:!text-primary [&_button:hover]:!bg-surface-tertiary/80"
          />
          <MiniMap
            nodeColor={(node) => {
              switch (node.type) {
                case "soul":
                  return "var(--soul)";
                case "task":
                  return "var(--task)";
                case "start":
                  return "var(--text-muted)";
                default:
                  return "var(--text-muted)";
              }
            }}
            maskColor="var(--surface-primary)"
            className="!bg-panel !border-border-default"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
