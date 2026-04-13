"use client";

import { memo, useCallback } from "react";
import { Handle, Position } from "@xyflow/react";
import { Layers, Layers2, Mail, Server, User } from "lucide-react";

import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCanvasStore } from "@/store/canvas";
import { cn } from "@runsight/ui/utils";
import type { StepNodeData } from "@/types/schemas/canvas";
import { getIconForBlockType } from "../surfaceUtils";

type SurfaceNodeKind = "start" | "task" | "soul";

interface SurfaceNodeCardProps {
  id: string;
  data: StepNodeData;
  selected?: boolean;
  kind: SurfaceNodeKind;
}

function getNodeIcon(icon: string | undefined) {
  const className = "h-4 w-4";
  const color = "var(--text-muted)";

  switch (icon) {
    case "server":
      return <Server className={className} style={{ color }} />;
    case "layers":
      return <Layers className={className} style={{ color }} />;
    case "mail":
      return <Mail className={className} style={{ color }} />;
    case "layers2":
      return <Layers2 className={className} style={{ color }} />;
    case "user":
    default:
      return <User className={className} style={{ color }} />;
  }
}

function getBorderStyles(status: string, selected?: boolean) {
  switch (status) {
    case "completed":
      return {
        borderColor: "var(--success-9)",
        borderWidth: "2px",
        boxShadow: "none",
      };
    case "failed":
      return {
        borderColor: "var(--danger-9)",
        borderWidth: "2px",
        boxShadow: "0 0 0 2px var(--danger-7)",
      };
    case "pending":
      return {
        borderColor: "var(--text-muted)",
        borderWidth: "1px",
        boxShadow: "none",
        opacity: 0.7,
      };
    case "running":
      return {
        borderColor: "var(--info-9)",
        borderWidth: "2px",
        boxShadow: "0 0 0 2px var(--info-7)",
      };
    default:
      return {
        borderColor: selected ? "var(--interactive-default)" : "var(--border-default)",
        borderWidth: selected ? "2px" : "1px",
        boxShadow: selected ? "0 0 0 2px var(--primary-40)" : "none",
      };
  }
}

function mapNodeStatus(status: string) {
  if (status === "completed") return { variant: "success" as const, label: "Completed" };
  if (status === "failed") return { variant: "error" as const, label: "Failed" };
  if (status === "running") return { variant: "running" as const, label: "Running" };
  if (status === "pending") return { variant: "pending" as const, label: "Pending" };
  return { variant: "pending" as const, label: "Idle" };
}

function kindLabel(kind: SurfaceNodeKind) {
  if (kind === "soul") return "SOUL";
  if (kind === "start") return "START";
  return "TASK";
}

function SurfaceNodeCardComponent({
  id,
  data,
  selected,
  kind,
}: SurfaceNodeCardProps) {
  const selectNode = useCanvasStore((state) => state.selectNode);
  const handleClick = useCallback(() => {
    selectNode(id);
  }, [id, selectNode]);

  const status = typeof data.status === "string" ? data.status : "idle";
  const borderStyles = getBorderStyles(status, selected);
  const displayCost =
    typeof data.executionCost === "number"
      ? data.executionCost
      : typeof data.cost === "number"
        ? data.cost
        : undefined;
  const isEstimate = typeof data.executionCost !== "number" && typeof displayCost === "number";
  const { variant, label } = mapNodeStatus(status);
  const icon = getNodeIcon(getIconForBlockType(String(data.stepType ?? kind)));
  const title = String(data.name ?? data.stepId ?? "Untitled");
  const tokens =
    typeof data.tokens === "object" && data.tokens !== null
      ? (data.tokens as { total?: number })
      : undefined;

  return (
    <div
      onClick={handleClick}
      data-testid={`node-${title}`}
      className={cn(
        "relative w-[240px] cursor-pointer rounded-md bg-[var(--surface-secondary)] transition-all duration-150",
        status === "pending" && "opacity-70",
      )}
      style={{
        border: `${borderStyles.borderWidth} solid ${borderStyles.borderColor}`,
        boxShadow: borderStyles.boxShadow,
        opacity: borderStyles.opacity,
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2.5 !w-2.5 !border-border-default !bg-neutral-9"
      />

      <div
        className={cn(
          "flex h-9 items-center justify-between border-b px-3",
          status === "completed"
            ? "border-[var(--success-9)]/30"
            : status === "failed"
              ? "border-[var(--danger-9)]/30"
              : status === "running"
                ? "border-[var(--info-9)]/30"
                : "border-[var(--border-default)]",
        )}
      >
        <div className="flex items-center gap-2">
          {icon}
          <span
            className={cn(
              "max-w-[120px] truncate text-sm font-medium",
              status === "pending" ? "text-[var(--text-muted)]" : "text-[var(--text-primary)]",
            )}
          >
            {title}
          </span>
        </div>
        <span className="text-[10px] font-medium text-[var(--text-muted)]">
          {kindLabel(kind)}
        </span>
      </div>

      <div className="space-y-2 p-3">
        {displayCost !== undefined ? (
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-muted)]">Cost</span>
            <span className="font-mono text-xs text-[var(--text-muted)]">
              {isEstimate ? "~" : ""}${displayCost.toFixed(3)}
            </span>
          </div>
        ) : null}
        {(typeof data.soulRef === "string" || kind === "soul") && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-[var(--text-muted)]">Soul</span>
            <span className="truncate text-xs text-[var(--text-muted)]">
              {typeof data.soulRef === "string" ? data.soulRef : "\u2014"}
            </span>
          </div>
        )}
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-[var(--text-muted)]">Status</span>
          <StatusBadge status={variant} label={label} />
        </div>
      </div>

      {(typeof data.duration === "number" || tokens) && (
        <div className="border-t border-[var(--border-default)] px-3 py-1.5 text-xs text-[var(--text-muted)]">
          {typeof data.duration === "number" ? `${data.duration.toFixed(1)}s` : ""}
          {typeof data.duration === "number" && tokens ? " • " : ""}
          {typeof tokens?.total === "number"
            ? `${tokens.total.toLocaleString()} tokens`
            : ""}
        </div>
      )}

      {status === "failed" && typeof data.error === "string" && data.error.length > 0 ? (
        <div className="border-t border-[var(--border-default)] bg-danger-3 px-3 py-2">
          <span className="text-xs text-[var(--danger-9)]">{data.error}</span>
        </div>
      ) : null}

      <Handle
        type="source"
        position={Position.Right}
        className="!h-2.5 !w-2.5 !border-border-default !bg-neutral-9"
      />
    </div>
  );
}

export const SurfaceNodeCard = memo(SurfaceNodeCardComponent, (prev, next) => {
  return (
    prev.kind === next.kind
    && prev.selected === next.selected
    && prev.data.status === next.data.status
    && prev.data.executionCost === next.data.executionCost
    && prev.data.duration === next.data.duration
    && prev.data.error === next.data.error
  );
});
