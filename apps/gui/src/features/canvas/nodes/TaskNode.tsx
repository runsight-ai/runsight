"use client";

import { memo, useCallback } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node } from "@xyflow/react";
import type { StepNodeData } from "@/types/schemas/canvas";
import { useCanvasStore } from "@/store/canvas";

type TaskNodeType = Node<StepNodeData, "task">;

function TaskNodeComponent({ id, data, selected }: NodeProps<TaskNodeType>) {
  const selectNode = useCanvasStore((state) => state.selectNode);

  const handleClick = useCallback(() => {
    selectNode(id);
  }, [id, selectNode]);

  return (
    <div
      onClick={handleClick}
      className={`bg-task/20 border rounded-lg px-4 py-3 text-sm font-medium min-w-[220px] max-w-[260px] shadow-lg cursor-pointer transition-all ${
        selected
          ? "border-task ring-2 ring-task/30"
          : "border-task hover:border-task/80"
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-neutral-9 !border-border-default"
      />

      <div className="flex items-center gap-2 mb-1.5">
        <div className="w-2 h-2 bg-success rounded-full" />
        <span className="text-primary font-medium">{String(data.name ?? data.stepId ?? "Task")}</span>
        <span className="bg-task/30 text-task px-1.5 py-0.5 rounded text-[10px] ml-auto font-medium">
          TASK
        </span>
      </div>
      {typeof data.stepType === "string" && (
        <div className="text-xs text-task/70 leading-relaxed line-clamp-3">
          {data.stepType}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-neutral-9 !border-border-default"
      />
    </div>
  );
}

export const TaskNode = memo(TaskNodeComponent);
