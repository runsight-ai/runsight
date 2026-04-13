"use client";

import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import type { StepNodeData } from "@/types/schemas/canvas";
import { SurfaceNodeCard } from "./SurfaceNodeCard";

type SoulNodeType = Node<StepNodeData, "soul">;

function SoulNodeComponent({ id, data, selected }: NodeProps<SoulNodeType>) {
  return <SurfaceNodeCard id={id} data={data} selected={selected} kind="soul" />;
}

export const SoulNode = memo(SoulNodeComponent);
