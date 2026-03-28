import { memo } from "react";
import type { NodeTypes } from "@xyflow/react";

import { StatusBadge } from "@/components/shared/StatusBadge";
import { cn } from "@/utils/helpers";
import {
  Server,
  Layers,
  Mail,
  Layers2,
  User,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RunNodeData extends Record<string, unknown> {
  name: string;
  stepType?: string;
  soulRef?: string;
  model?: string;
  status: "idle" | "pending" | "running" | "completed" | "failed" | "paused";
  cost?: number;
  icon?: string;
  iconColor?: string;
  executionCost?: number;
  duration?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
}

// ---------------------------------------------------------------------------
// Node icon helper
// ---------------------------------------------------------------------------

function getNodeIcon(icon: string | undefined, iconColor: string | undefined) {
  const color = iconColor || "var(--text-muted)";
  const className = "w-4 h-4";
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

// ---------------------------------------------------------------------------
// Border style helper
// ---------------------------------------------------------------------------

function getBorderStyles(status: string, selected?: boolean) {
  switch (status) {
    case "completed":
      return { borderColor: "var(--success-9)", borderWidth: "2px", boxShadow: "none" };
    case "failed":
      return { borderColor: "var(--danger-9)", borderWidth: "2px", boxShadow: "0 0 0 2px var(--danger-7)" };
    case "pending":
      return { borderColor: "var(--text-muted)", borderWidth: "1px", boxShadow: "none", opacity: 0.7 };
    default:
      return {
        borderColor: selected ? "var(--interactive-default)" : "var(--border-default)",
        borderWidth: selected ? "2px" : "1px",
        boxShadow: selected ? "0 0 0 2px var(--primary-40)" : "none",
      };
  }
}

// ---------------------------------------------------------------------------
// Status mapper for StatusBadge
// ---------------------------------------------------------------------------

function mapNodeStatus(status: string): { variant: "success" | "error" | "pending"; label: string } {
  if (status === "completed") return { variant: "success", label: "Completed" };
  if (status === "failed") return { variant: "error", label: "Failed" };
  if (status === "pending") return { variant: "pending", label: "Pending" };
  return { variant: "pending", label: "Idle" };
}

// ---------------------------------------------------------------------------
// Canvas Node Component
// ---------------------------------------------------------------------------

export function CanvasNodeComponent(props: { data: RunNodeData; selected?: boolean }) {
  const { data, selected } = props;
  const status = data.status || "idle";
  const borderStyles = getBorderStyles(status, selected);
  const displayCost = data.executionCost !== undefined ? data.executionCost : data.cost;
  const isEstimate = data.executionCost === undefined;
  const { variant, label } = mapNodeStatus(status);

  return (
    <div
      data-testid={`node-${data.name}`}
      className={cn("w-[240px] bg-[var(--surface-secondary)] rounded-md transition-all duration-150", status === "pending" && "opacity-70")}
      style={{ border: `${borderStyles.borderWidth} solid ${borderStyles.borderColor}`, boxShadow: borderStyles.boxShadow }}
    >
      <div className={cn("h-9 px-3 flex items-center justify-between border-b", status === "completed" ? "border-[var(--success-9)]/30" : status === "failed" ? "border-[var(--danger-9)]/30" : "border-[var(--border-default)]")}>
        <div className="flex items-center gap-2">
          {getNodeIcon(data.icon, data.iconColor)}
          <span className={cn("text-sm font-medium truncate max-w-[120px]", status === "pending" ? "text-[var(--text-muted)]" : "text-[var(--text-primary)]")}>{data.name}</span>
        </div>
        {displayCost !== undefined && (
          <span className="font-mono text-xs text-[var(--text-muted)]">{isEstimate ? "~" : ""}${displayCost.toFixed(3)}</span>
        )}
      </div>
      <div className="p-3 space-y-2">
        {data.soulRef && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-muted)]">Soul</span>
            <span className="text-xs text-[var(--text-muted)]">{data.soulRef}</span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-xs text-[var(--text-muted)]">Status</span>
          <StatusBadge status={variant} label={label} />
        </div>
      </div>
      {(data.duration || data.tokens) && (
        <div className="px-3 py-1.5 border-t border-[var(--border-default)] text-xs text-[var(--text-muted)]">
          {data.duration ? `${data.duration.toFixed(1)}s` : ""}
          {data.duration && data.tokens ? " • " : ""}
          {data.tokens?.total ? `${data.tokens.total.toLocaleString()} tokens` : ""}
        </div>
      )}
      {status === "failed" && data.error && (
        <div className="px-3 py-2 border-t border-[var(--border-default)] bg-danger-3">
          <span className="text-xs text-[var(--danger-9)]">{data.error}</span>
        </div>
      )}
    </div>
  );
}

export const RunCanvasNode = memo(CanvasNodeComponent, (prev, next) => {
  return (
    prev.data.status === next.data.status &&
    prev.data.executionCost === next.data.executionCost &&
    prev.data.duration === next.data.duration &&
    prev.selected === next.selected
  );
});

export const nodeTypes = {
  canvasNode: RunCanvasNode,
} satisfies NodeTypes;
