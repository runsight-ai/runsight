"use client";

import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import type { StepNodeData } from "@/types/schemas/canvas";
import { SurfaceNodeCard } from "./SurfaceNodeCard";

type TaskNodeType = Node<StepNodeData, "task">;

function TaskNodeComponent({ id, data, selected }: NodeProps<TaskNodeType>) {
  return <SurfaceNodeCard id={id} data={data} selected={selected} kind="task" />;
}

export const TaskNode = memo(TaskNodeComponent);
