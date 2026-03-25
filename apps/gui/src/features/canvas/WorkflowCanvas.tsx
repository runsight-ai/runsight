"use client";

import { useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toast } from "sonner";

import { useWorkflowStore } from "@/store/workflowStore";
import { nodeTypes } from "./nodes";

export function WorkflowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, selectNode } =
    useWorkflowStore();

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  const onSave = async () => {
    try {
      await useWorkflowStore.getState().saveWorkflow();
      toast.success("Workflow saved");
    } catch (error: unknown) {
      toast.error("Failed to save workflow", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      {/* React Flow Canvas - Unified Workflow View (no DAG/State Machine toggle per spec) */}
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          defaultEdgeOptions={{
            style: { stroke: "var(--border-default)", strokeWidth: 1.5 },
            type: "straight",
            markerEnd: {
              type: "arrowclosed",
              width: 10,
              height: 10,
              color: "var(--muted-foreground)",
            },
          }}
          proOptions={{ hideAttribution: true }}
          className="bg-surface"
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={28}
            size={0.8}
            color="var(--muted-foreground)"
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
                  return "var(--muted-foreground)";
                default:
                  return "var(--muted-foreground)";
              }
            }}
            maskColor="rgba(15, 23, 42, 0.7)"
            className="!bg-panel !border-border-default"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
