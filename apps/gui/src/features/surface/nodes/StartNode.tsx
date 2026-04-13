"use client";

import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import type { StepNodeData } from "@/types/schemas/canvas";
import { SurfaceNodeCard } from "./SurfaceNodeCard";

type StartNodeType = Node<StepNodeData, "start">;

function StartNodeComponent({ id, data, selected }: NodeProps<StartNodeType>) {
  return <SurfaceNodeCard id={id} data={data} selected={selected} kind="start" />;
}

export const StartNode = memo(StartNodeComponent);
