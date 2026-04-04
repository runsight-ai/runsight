"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node } from "@xyflow/react";
import type { StepNodeData } from "@/types/schemas/canvas";

type StartNodeType = Node<StepNodeData, "start">;

function StartNodeComponent({ data }: NodeProps<StartNodeType>) {
  return (
    <div className="bg-panel border border-border-default rounded-full px-3 h-7 flex items-center justify-center gap-1.5 shadow-lg cursor-pointer hover:border-border-subtle transition-colors">
      <div className="w-1.5 h-1.5 bg-success rounded-full" />
      <span className="text-muted text-xs font-medium">{String(data.name ?? data.stepId ?? "Start")}</span>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-1.5 !h-1.5 !bg-neutral-9 !border-border-default"
      />
    </div>
  );
}

export const StartNode = memo(StartNodeComponent);
