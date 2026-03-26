"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { StartNodeData } from "@/types/workflow";
import type { Node } from "@xyflow/react";

type StartNodeType = Node<StartNodeData, "start">;

function StartNodeComponent({ data }: NodeProps<StartNodeType>) {
  return (
    <div className="bg-panel border border-border-default rounded-full px-3 h-7 flex items-center justify-center gap-1.5 shadow-lg cursor-pointer hover:border-muted-foreground/50 transition-colors">
      <div className="w-1.5 h-1.5 bg-success rounded-full" />
      <span className="text-muted text-xs font-medium">{data.label}</span>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-1.5 !h-1.5 !bg-neutral-9 !border-border-default"
      />
    </div>
  );
}

export const StartNode = memo(StartNodeComponent);
