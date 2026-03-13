import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { StatusBadge } from "@/components/shared/StatusBadge";
import {
  User,
  GitBranch,
  MessageSquare,
  Radio,
  GitFork,
  Shield,
  Merge,
  Layers,
  RotateCcw,
  Crown,
  Briefcase,
  Box,
  FileOutput,
} from "lucide-react";
import { cn } from "@/utils/helpers";
import type { StepNodeData, StepType } from "@/types/schemas/canvas";

export type CanvasNodeData = StepNodeData;

const STEP_TYPE_ICONS: Record<StepType, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  linear: User,
  fanout: GitBranch,
  debate: MessageSquare,
  message_bus: Radio,
  router: GitFork,
  gate: Shield,
  synthesize: Merge,
  workflow: Layers,
  retry: RotateCcw,
  team_lead: Crown,
  engineering_manager: Briefcase,
  placeholder: Box,
  file_writer: FileOutput,
};

const statusConfig = {
  idle: { variant: "pending" as const, label: "Idle" },
  pending: { variant: "pending" as const, label: "Pending" },
  running: { variant: "running" as const, label: "Running" },
  completed: { variant: "success" as const, label: "Completed" },
  failed: { variant: "error" as const, label: "Failed" },
  paused: { variant: "warning" as const, label: "Paused" },
};

// CSS keyframes for pulse animation (to be injected)
const pulseKeyframes = `
@keyframes node-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(0,229,255,0.2); }
  50% { box-shadow: 0 0 0 6px rgba(0,229,255,0.5); }
}
`;

// Inject keyframes into document if not already present
if (typeof document !== "undefined") {
  const styleId = "canvas-node-animations";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = pulseKeyframes;
    document.head.appendChild(style);
  }
}

function getStepTypeIcon(stepType: StepType, iconColor: string) {
  const Icon = STEP_TYPE_ICONS[stepType] ?? Box;
  return <Icon className="w-4 h-4" style={{ color: iconColor }} />;
}

function getSoulRefDisplay(data: StepNodeData): string | null {
  if (data.soulARef && data.soulBRef) {
    return `A: ${data.soulARef} / B: ${data.soulBRef}`;
  }
  if (data.soulRef) {
    return data.soulRef;
  }
  if (data.soulRefs?.length) {
    return `Souls: ${data.soulRefs.length}`;
  }
  return null;
}

function CanvasNodeComponent(props: NodeProps) {
  const { data, selected } = props;
  const nodeData = data as StepNodeData;
  const status = nodeData.status || "idle";
  const statusConfigItem = statusConfig[status] ?? statusConfig.idle;
  const iconColor = nodeData.iconColor ?? "#9292A0";
  const stepType = nodeData.stepType ?? "placeholder";
  const displayName = nodeData.name ?? "Step";

  // Determine border styles based on execution state
  const getBorderStyles = () => {
    switch (status) {
      case "running":
        return {
          borderColor: "#00E5FF",
          borderWidth: "2px",
          animation: "node-pulse 2s ease-in-out infinite",
          boxShadow: "0 0 0 4px rgba(0,229,255,0.3)",
        };
      case "completed":
        return {
          borderColor: "#28A745",
          borderWidth: "2px",
          animation: "none",
          boxShadow: "none",
        };
      case "failed":
        return {
          borderColor: "#E53935",
          borderWidth: "2px",
          animation: "none",
          boxShadow: "0 0 0 2px rgba(229,57,53,0.4)",
        };
      case "pending":
        return {
          borderColor: "#9292A0",
          borderWidth: "1px",
          animation: "none",
          boxShadow: "none",
          opacity: 0.7,
        };
      case "paused":
        return {
          borderColor: "#F5A623",
          borderWidth: "2px",
          animation: "none",
          boxShadow: "none",
        };
      default:
        return {
          borderColor: selected ? "#5E6AD2" : "#2D2D35",
          borderWidth: selected ? "2px" : "1px",
          animation: "none",
          boxShadow: selected ? "0 0 0 2px rgba(94,106,210,0.4)" : "none",
        };
    }
  };

  const borderStyles = getBorderStyles();

  // Get header border color based on status
  const getHeaderBorderColor = () => {
    switch (status) {
      case "running":
        return "border-[#00E5FF]/30";
      case "completed":
        return "border-[#28A745]/30";
      case "failed":
        return "border-[#E53935]/30";
      default:
        return "border-[#2D2D35]";
    }
  };

  // Get cost display
  const displayCost = nodeData.executionCost !== undefined
    ? nodeData.executionCost
    : nodeData.cost;

  const isEstimate = nodeData.executionCost === undefined;

  // Get cost color based on status
  const getCostColor = () => {
    switch (status) {
      case "running":
        return "text-[#00E5FF]";
      case "completed":
        return "text-[#9292A0]";
      case "failed":
        return "text-[#E53935]";
      case "pending":
        return "text-[#5E5E6B]";
      default:
        return "text-[#9292A0]";
    }
  };

  const soulDisplay = getSoulRefDisplay(nodeData);

  return (
    <div
      className={cn(
        "w-[240px] bg-[#16161C] rounded-md transition-all duration-150",
        status === "pending" && "opacity-70"
      )}
      style={{
        border: `${borderStyles.borderWidth} solid ${borderStyles.borderColor}`,
        boxShadow: borderStyles.boxShadow,
        animation: borderStyles.animation,
      }}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className={cn(
          "!w-3 !h-3 !bg-[#16161C] !border-2 !rounded-full !transition-all",
          status === "running"
            ? "!border-[#00E5FF] hover:!border-[#00E5FF] hover:!bg-[#00E5FF]"
            : "!border-[#3F3F4A] hover:!border-[#5E6AD2] hover:!bg-[#5E6AD2]"
        )}
        style={{ left: "-6px" }}
      />

      {/* Header */}
      <div
        className={cn(
          "h-9 px-3 flex items-center justify-between border-b",
          getHeaderBorderColor(),
          status === "running" && "bg-[rgba(0,229,255,0.05)]"
        )}
      >
        <div className="flex items-center gap-2 min-w-0">
          {getStepTypeIcon(stepType, iconColor)}
          <div className="flex flex-col min-w-0">
            <span
              className={cn(
                "text-sm font-medium truncate max-w-[120px]",
                status === "pending" ? "text-[#5E5E6B]" : "text-[#EDEDF0]"
              )}
            >
              {displayName}
            </span>
            <span className="text-[10px] text-[#5E5E6B] truncate max-w-[120px]">
              {stepType.replace(/_/g, " ")}
            </span>
          </div>
        </div>
        {displayCost !== undefined && (
          <span className={cn("font-mono text-xs shrink-0", getCostColor())}>
            {isEstimate ? "~" : ""}${displayCost.toFixed(2)}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="p-3 space-y-2">
        {soulDisplay && (
          <div className="flex items-center gap-2">
            {nodeData.soulRef ? (
              <span className={cn("text-xs shrink-0", "text-[#5E5E6B]")}>Soul:</span>
            ) : null}
            <span
              className={cn(
                "text-xs truncate",
                status === "pending" ? "text-[#5E5E6B]" : "text-[#9292A0]"
              )}
            >
              {soulDisplay}
            </span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <StatusBadge
            status={statusConfigItem.variant}
            label={statusConfigItem.label}
            className={status === "running" ? "animate-pulse" : ""}
          />
        </div>
      </div>

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Right}
        className={cn(
          "!w-3 !h-3 !bg-[#16161C] !border-2 !rounded-full !transition-all",
          status === "running"
            ? "!border-[#00E5FF] hover:!border-[#00E5FF] hover:!bg-[#00E5FF]"
            : "!border-[#3F3F4A] hover:!border-[#5E6AD2] hover:!bg-[#5E6AD2]"
        )}
        style={{ right: "-6px" }}
      />
    </div>
  );
}

export const CanvasNode = memo(CanvasNodeComponent);
CanvasNode.displayName = "CanvasNode";

export default CanvasNode;
