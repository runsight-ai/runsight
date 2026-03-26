"use client";

import { memo, useCallback } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { SoulNodeData } from "@/types/workflow";
import type { Node } from "@xyflow/react";
import { useWorkflowStore } from "@/store/workflowStore";

type SoulNodeType = Node<SoulNodeData, "soul">;

function SoulNodeComponent({ id, data, selected }: NodeProps<SoulNodeType>) {
  const selectNode = useWorkflowStore((s) => s.selectNode);

  const handleClick = useCallback(() => {
    selectNode(id);
  }, [id, selectNode]);

  return (
    <div
      onClick={handleClick}
      className={`bg-soul/20 border rounded-lg px-4 py-3 text-sm font-medium min-w-[180px] shadow-lg cursor-pointer transition-all ${
        selected
          ? "border-soul ring-2 ring-soul/30"
          : "border-soul hover:border-soul/80"
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-neutral-9 !border-border-default"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="w-2 h-2 bg-success rounded-full" />
        <span className="text-primary font-medium">{data.label}</span>
        <span className="bg-soul/30 text-soul px-1.5 py-0.5 rounded text-[10px] ml-auto font-medium">
          SOUL
        </span>
      </div>
      <div className="text-xs text-soul/70">
        {data.model} • tools: {data.toolCount}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-neutral-9 !border-border-default"
      />
    </div>
  );
}

export const SoulNode = memo(SoulNodeComponent);
