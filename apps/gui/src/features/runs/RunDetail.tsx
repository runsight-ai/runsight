import { useState, useCallback, useMemo, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useRun, useRunNodes, useRunLogs } from "@/queries/runs";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { cn } from "@/utils/helpers";
import {
  ChevronLeft,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  DollarSign,
  FileText,
  Bot,
  Package,
  ChevronDown,
  ChevronUp,
  ZoomIn,
  ZoomOut,
  Maximize,
  X,
  User,
  Server,
  Layers,
  Mail,
  Layers2,
  Activity,
} from "lucide-react";
import type { LogResponse } from "@/types/schemas/runs";

interface RunNodeData extends Record<string, unknown> {
  name: string;
  stepType?: string;
  soulRef?: string;
  status: "idle" | "pending" | "running" | "completed" | "failed" | "paused";
  cost?: number;
  icon?: string;
  iconColor?: string;
  executionCost?: number;
  duration?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
}

// Read-only Canvas Node Component
function CanvasNodeComponent(props: { data: RunNodeData; selected?: boolean }) {
  const { data, selected } = props;
  const status = data.status || "idle";

  const getNodeIcon = () => {
    const color = data.iconColor || "#9292A0";
    const className = "w-4 h-4";
    switch (data.icon) {
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
  };

  const getBorderStyles = () => {
    switch (status) {
      case "completed":
        return {
          borderColor: "#28A745",
          borderWidth: "2px",
          boxShadow: "none",
        };
      case "failed":
        return {
          borderColor: "#E53935",
          borderWidth: "2px",
          boxShadow: "0 0 0 2px rgba(229,57,53,0.4)",
        };
      case "pending":
        return {
          borderColor: "#9292A0",
          borderWidth: "1px",
          boxShadow: "none",
          opacity: 0.7,
        };
      default:
        return {
          borderColor: selected ? "#5E6AD2" : "#2D2D35",
          borderWidth: selected ? "2px" : "1px",
          boxShadow: selected ? "0 0 0 2px rgba(94,106,210,0.4)" : "none",
        };
    }
  };

  const borderStyles = getBorderStyles();
  const displayCost = data.executionCost !== undefined ? data.executionCost : data.cost;
  const isEstimate = data.executionCost === undefined;

  return (
    <div
      data-testid={`node-${data.name}`}
      className={cn(
        "w-[240px] bg-[#16161C] rounded-md transition-all duration-150",
        status === "pending" && "opacity-70"
      )}
      style={{
        border: `${borderStyles.borderWidth} solid ${borderStyles.borderColor}`,
        boxShadow: borderStyles.boxShadow,
      }}
    >
      {/* Header */}
      <div
        className={cn(
          "h-9 px-3 flex items-center justify-between border-b",
          status === "completed"
            ? "border-[#28A745]/30"
            : status === "failed"
            ? "border-[#E53935]/30"
            : "border-[#2D2D35]"
        )}
      >
        <div className="flex items-center gap-2">
          {getNodeIcon()}
          <span
            className={cn(
              "text-sm font-medium truncate max-w-[120px]",
              status === "pending" ? "text-[#5E5E6B]" : "text-[#EDEDF0]"
            )}
          >
            {data.name}
          </span>
        </div>
        {displayCost !== undefined && (
          <span className="font-mono text-xs text-[#9292A0]">
            {isEstimate ? "~" : ""}${displayCost.toFixed(3)}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="p-3 space-y-2">
        {data.soulRef && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#5E5E6B]">Soul</span>
            <span className="text-xs text-[#9292A0]">{data.soulRef}</span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-xs text-[#5E5E6B]">Status</span>
          <StatusBadge
            status={
              status === "completed"
                ? "success"
                : status === "failed"
                ? "error"
                : status === "pending"
                ? "pending"
                : "pending"
            }
            label={
              status === "completed"
                ? "Completed"
                : status === "failed"
                ? "Failed"
                : status === "pending"
                ? "Pending"
                : "Idle"
            }
          />
        </div>
      </div>

      {/* Footer with metrics */}
      {(data.duration || data.tokens) && (
        <div className="px-3 py-1.5 border-t border-[#2D2D35] text-xs text-[#9292A0]">
          {data.duration ? `${data.duration.toFixed(1)}s` : ""}
          {data.duration && data.tokens ? " • " : ""}
          {data.tokens?.total ? `${data.tokens.total.toLocaleString()} tokens` : ""}
        </div>
      )}

      {/* Error indicator */}
      {status === "failed" && data.error && (
        <div className="px-3 py-2 border-t border-[#2D2D35] bg-[rgba(229,57,53,0.08)]">
          <span className="text-xs text-[#E53935]">{data.error}</span>
        </div>
      )}
    </div>
  );
}

const CanvasNode = CanvasNodeComponent;
const nodeTypes = {
  canvasNode: CanvasNode,
} satisfies NodeTypes;

// Format timestamp helper
function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

// Inspector Panel Component (Read-only)
interface InspectorPanelProps {
  selectedNode: Node<RunNodeData> | null;
  onClose: () => void;
}

function InspectorPanel({ selectedNode, onClose }: InspectorPanelProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "execution">("execution");

  if (!selectedNode) return null;

  const nodeData = selectedNode.data;
  const status = nodeData.status || "idle";

  return (
    <aside data-testid="right-inspector" className="w-[320px] min-w-[280px] max-w-[480px] bg-[#16161C] border-l border-[#2D2D35] flex flex-col z-50 animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="h-12 px-3 border-b border-[#2D2D35] flex items-center justify-between shrink-0">
        <h2 className="text-base font-medium text-[#EDEDF0] truncate">
          {nodeData.name}
        </h2>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onClose}
          aria-label="Close inspector"
          className="w-8 h-8 text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Tab Bar */}
      <div
        role="tablist"
        aria-label="Inspector tabs"
        className="h-9 flex items-center px-2 border-b border-[#2D2D35] gap-1 shrink-0 overflow-x-auto"
      >
        <button
          role="tab"
          aria-selected={activeTab === "execution"}
          aria-controls="inspector-execution-panel"
          id="inspector-execution-tab"
          onClick={() => setActiveTab("execution")}
          className={cn(
            "h-full px-3 text-[12px] font-medium whitespace-nowrap transition-colors border-b-2",
            activeTab === "execution"
              ? "text-[#EDEDF0] border-[#5E6AD2]"
              : "text-[#9292A0] hover:text-[#EDEDF0] border-transparent"
          )}
        >
          Execution
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "overview"}
          aria-controls="inspector-overview-panel"
          id="inspector-overview-tab"
          onClick={() => setActiveTab("overview")}
          className={cn(
            "h-full px-3 text-[12px] font-medium whitespace-nowrap transition-colors border-b-2",
            activeTab === "overview"
              ? "text-[#EDEDF0] border-[#5E6AD2]"
              : "text-[#9292A0] hover:text-[#EDEDF0] border-transparent"
          )}
        >
          Overview
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {activeTab === "execution" && (
          <div role="tabpanel" id="inspector-execution-panel" aria-labelledby="inspector-execution-tab" className="space-y-4">
            {/* Status Banner */}
            <div
              className={cn(
                "mb-4 p-3 rounded-md border",
                status === "completed"
                  ? "bg-[rgba(40,167,69,0.08)] border-[#28A745]/30"
                  : status === "failed"
                  ? "bg-[rgba(229,57,53,0.08)] border-[#E53935]/30"
                  : status === "pending"
                  ? "bg-[#0D0D12] border-[#2D2D35]"
                  : "bg-[#0D0D12] border-[#2D2D35]"
              )}
            >
              <div className="flex items-center gap-2 mb-2">
                {status === "completed" ? (
                  <CheckCircle className="w-4 h-4 text-[#28A745]" />
                ) : status === "failed" ? (
                  <XCircle className="w-4 h-4 text-[#E53935]" />
                ) : (
                  <Clock className="w-4 h-4 text-[#9292A0]" />
                )}
                <span
                  className={cn(
                    "text-sm font-medium",
                    status === "completed"
                      ? "text-[#28A745]"
                      : status === "failed"
                      ? "text-[#E53935]"
                      : "text-[#9292A0]"
                  )}
                >
                  {status === "completed"
                    ? "Completed"
                    : status === "failed"
                    ? "Failed"
                    : status === "pending"
                    ? "Pending"
                    : "Idle"}
                </span>
              </div>
              {nodeData.duration && (
                <div className="font-mono text-xs text-[#9292A0]">
                  Duration: {formatDuration(nodeData.duration)}
                </div>
              )}
            </div>

            {/* Cost */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Cost
              </label>
              <div className="flex items-center justify-between p-2 rounded-md bg-[#0D0D12] border border-[#2D2D35]">
                <span className="font-mono text-sm text-[#EDEDF0]">
                  ${(nodeData.executionCost || 0).toFixed(3)}
                </span>
              </div>
            </div>

            {/* Token Usage */}
            {nodeData.tokens && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Token Usage
                </label>
                <div className="p-3 rounded-md bg-[#0D0D12] border border-[#2D2D35] space-y-2">
                  {nodeData.tokens.input !== undefined && (
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-[#9292A0]">Prompt</span>
                        <span className="font-mono text-[#EDEDF0]">
                          {nodeData.tokens.input.toLocaleString()}
                        </span>
                      </div>
                      <div className="h-1.5 bg-[#2D2D35] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#5E6AD2] rounded-full"
                          style={{
                            width: `${
                              ((nodeData.tokens.input || 0) /
                                (nodeData.tokens.total || 1)) *
                              100
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                  {nodeData.tokens.output !== undefined && (
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-[#9292A0]">Completion</span>
                        <span className="font-mono text-[#EDEDF0]">
                          {nodeData.tokens.output.toLocaleString()}
                        </span>
                      </div>
                      <div className="h-1.5 bg-[#2D2D35] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#5E6AD2] rounded-full"
                          style={{
                            width: `${
                              ((nodeData.tokens.output || 0) /
                                (nodeData.tokens.total || 1)) *
                              100
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                  <div className="flex justify-between text-xs pt-1 border-t border-[#2D2D35]">
                    <span className="text-[#5E5E6B]">Total</span>
                    <span className="font-mono text-[#EDEDF0]">
                      {nodeData.tokens.total?.toLocaleString()} tokens
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Error Message */}
            {status === "failed" && nodeData.error && (
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                  Error
                </label>
                <div className="p-3 rounded-md bg-[rgba(229,57,53,0.08)] border border-[#E53935]/30 font-mono text-xs text-[#E53935] leading-relaxed">
                  {nodeData.error}
                </div>
              </div>
            )}

            {/* Configuration (Read-only) */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Configuration
              </label>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[#9292A0]">Soul</span>
                  <span className="text-[#EDEDF0]">{nodeData.soulRef || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#9292A0]">Model</span>
                  <span className="text-[#EDEDF0]">{nodeData.model || "—"}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "overview" && (
          <div role="tabpanel" id="inspector-overview-panel" aria-labelledby="inspector-overview-tab" className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Name
              </label>
              <div className="p-2 rounded-md bg-[#0D0D12] border border-[#2D2D35] text-sm text-[#EDEDF0]">
                {nodeData.name}
              </div>
            </div>

            {/* Status */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Status
              </label>
              <StatusBadge
                status={
                  status === "completed"
                    ? "success"
                    : status === "failed"
                    ? "error"
                    : status === "pending"
                    ? "pending"
                    : "pending"
                }
                label={
                  status === "completed"
                    ? "Completed"
                    : status === "failed"
                    ? "Failed"
                    : status === "pending"
                    ? "Pending"
                    : "Idle"
                }
              />
            </div>

            {/* Configuration */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] mb-2">
                Configuration
              </label>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[#9292A0]">Soul</span>
                  <span className="text-[#EDEDF0]">{nodeData.soulRef || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#9292A0]">Model</span>
                  <span className="text-[#EDEDF0]">{nodeData.model || "—"}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

// Bottom Panel Component
interface BottomPanelProps {
  logs: LogResponse[];
  executionComplete: boolean;
  executionFailed: boolean;
  finalDuration: number;
}

function BottomPanel({
  logs,
  executionComplete,
  executionFailed,
  finalDuration,
}: BottomPanelProps) {
  const [activeTab, setActiveTab] = useState<"logs" | "agent-feed" | "artifacts">("logs");
  const [isExpanded, setIsExpanded] = useState(true);

  const levelConfig = {
    INFO: { bg: "bg-transparent", text: "text-[#9292A0]" },
    WARN: { bg: "bg-[rgba(245,166,35,0.12)]", text: "text-[#F5A623]" },
    ERROR: { bg: "bg-[rgba(229,57,53,0.12)]", text: "text-[#E53935]" },
    DEBUG: { bg: "bg-transparent", text: "text-[#5E5E6B]" },
  } as const;

  return (
    <div
      data-testid="bottom-panel"
      className={cn(
        "bg-[#16161C] border-t border-[#2D2D35] flex flex-col z-50",
        isExpanded ? "h-[200px]" : "h-[36px]"
      )}
    >
      {/* Tab Bar */}
      <div
        role="tablist"
        aria-label="Bottom panel tabs"
        className="h-9 flex items-center px-4 border-b border-[#2D2D35] justify-between shrink-0"
      >
        <div className="flex items-center gap-1">
          {[
            { id: "logs", label: "Logs", icon: FileText },
            { id: "agent-feed", label: "Agent Feed", icon: Bot },
            { id: "artifacts", label: "Artifacts", icon: Package },
          ].map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`bottom-panel-${tab.id}`}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={cn(
                "h-7 px-3 text-[12px] font-medium flex items-center gap-1.5 border-b-2 transition-colors",
                activeTab === tab.id
                  ? "text-[#EDEDF0] border-[#5E6AD2]"
                  : "text-[#9292A0] hover:text-[#EDEDF0] border-transparent"
              )}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => setIsExpanded(!isExpanded)}
          aria-label={isExpanded ? "Collapse panel" : "Expand panel"}
          className="w-6 h-6 flex items-center justify-center rounded hover:bg-[#22222A] text-[#9292A0]"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronUp className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Tab Content */}
      {isExpanded && (
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Logs Tab */}
          {activeTab === "logs" && (
            <>
              {/* Completion Banner */}
              {executionComplete && (
                <div
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 border-b shrink-0",
                    executionFailed
                      ? "bg-[rgba(229,57,53,0.08)] border-l-[3px] border-l-[#E53935] border-[#2D2D35]"
                      : "bg-[rgba(40,167,69,0.08)] border-l-[3px] border-l-[#28A745] border-[#2D2D35]"
                  )}
                >
                  {executionFailed ? (
                    <>
                      <XCircle className="w-4 h-4 text-[#E53935] shrink-0" />
                      <span className="text-sm text-[#EDEDF0]">Run failed</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4 text-[#28A745] shrink-0" />
                      <span className="text-sm text-[#EDEDF0]">
                        Run completed in {formatDuration(finalDuration)}
                      </span>
                    </>
                  )}
                </div>
              )}
              <div className="flex-1 overflow-y-auto">
                {logs.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-[#5E5E6B] text-sm">
                    No logs available for this run.
                  </div>
                ) : (
                  logs.map((log, index) => {
                    const logLevelKey = log.level?.toUpperCase() as keyof typeof levelConfig;
                    const logLevel = logLevelKey in levelConfig ? logLevelKey : "INFO";
                    const levelStyle = levelConfig[logLevel];
                    return (
                      <div
                        key={log.id}
                        className={cn(
                          "flex items-center gap-3 px-3 font-mono text-xs min-h-[24px]",
                          index % 2 === 1 && "bg-[rgba(255,255,255,0.02)]"
                        )}
                      >
                        <span className="text-[#5E5E6B] w-[80px] shrink-0">
                          {formatTimestamp(log.timestamp)}
                        </span>
                        <span
                          className={cn(
                            "px-1.5 py-0.5 rounded text-[10px] font-medium w-12 text-center shrink-0",
                            levelStyle.bg,
                            levelStyle.text
                          )}
                        >
                          {log.level}
                        </span>
                        {log.node_id && (
                          <span className="text-[#5E5E6B] w-[100px] shrink-0 truncate">
                            [{log.node_id}]
                          </span>
                        )}
                        <span className="text-[#EDEDF0] flex-1 truncate">{log.message}</span>
                      </div>
                    );
                  })
                )}
              </div>
            </>
          )}

          {/* Agent Feed Tab */}
          {activeTab === "agent-feed" && (
            <div className="flex items-center justify-center h-full text-[#5E5E6B] text-sm">
              Agent Feed coming soon
            </div>
          )}

          {/* Artifacts Tab */}
          {activeTab === "artifacts" && (
            <div className="flex items-center justify-center h-full text-[#5E5E6B] text-sm">
              Artifacts coming soon
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Main Run Detail Inner Component
function RunDetailInner() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Fetch run data
  const { data: run, isLoading: isLoadingRun } = useRun(id || "", {
    refetchInterval: false, // Don't refetch for post-execution review
  });

  // Fetch run nodes
  const { data: runNodes, isLoading: isLoadingNodes } = useRunNodes(id || "");

  // Fetch run logs
  const { data: runLogs } = useRunLogs(id || "", undefined, {
    refetchInterval: undefined,
  });

  // Local state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<RunNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<Node<RunNodeData> | null>(null);

  // Convert run data to canvas nodes/edges
  const buildCanvasFromRun = useCallback(() => {
    if (!runNodes) return;

    // Build nodes from run nodes
    const canvasNodes: Node<RunNodeData>[] = runNodes.map((node, index) => ({
      id: node.node_id,
      type: "canvasNode",
      position: { x: 100 + (index % 3) * 300, y: 100 + Math.floor(index / 3) * 200 },
      data: {
        name: node.block_type,
        soulRef: node.block_type,
        model: node.block_type,
        status: mapRunStatus(node.status),
        executionCost: node.cost_usd,
        duration: node.duration_seconds || undefined,
        tokens: node.tokens as { input?: number; output?: number; total?: number } | undefined,
        error: node.error || undefined,
        icon: getIconForBlockType(node.block_type),
      },
    }));

    setNodes(canvasNodes);

    // Create simple edges (sequential for now)
    const canvasEdges: Edge[] = [];
    for (let i = 0; i < canvasNodes.length - 1; i++) {
      const currentNode = canvasNodes[i];
      const nextNode = canvasNodes[i + 1];
      if (currentNode && nextNode) {
        canvasEdges.push({
          id: `e${i}`,
          source: currentNode.id,
          target: nextNode.id,
          style: { stroke: "#2D2D35", strokeWidth: 2 } as React.CSSProperties,
        });
      }
    }
    setEdges(canvasEdges);
  }, [runNodes, setNodes, setEdges]);

  // Build canvas when run nodes load
  useEffect(() => {
    buildCanvasFromRun();
  }, [buildCanvasFromRun]);

  // Map run node status to canvas node status
  function mapRunStatus(status: string): RunNodeData["status"] {
    switch (status) {
      case "completed":
      case "success":
        return "completed";
      case "failed":
      case "error":
        return "failed";
      case "running":
        return "running";
      case "pending":
      default:
        return "pending";
    }
  }

  // Get icon for block type
  function getIconForBlockType(blockType: string): string {
    if (blockType.includes("agent") || blockType.includes("llm")) return "user";
    if (blockType.includes("condition") || blockType.includes("if")) return "layers";
    if (blockType.includes("input") || blockType.includes("output")) return "mail";
    return "server";
  }

  // Handle node click
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node<RunNodeData>) => {
    setSelectedNode(node);
  }, []);

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Handle Run Again
  const handleRunAgain = useCallback(() => {
    if (run?.workflow_id) {
      navigate(`/workflows/${run.workflow_id}`);
    }
  }, [navigate, run?.workflow_id]);

  // Convert logs to array format
  const logs = useMemo(() => {
    return runLogs?.items || [];
  }, [runLogs]);

  if (isLoadingRun || isLoadingNodes) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0D0D12]">
        <div className="flex items-center gap-2 text-[#9292A0]">
          <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Loading run details...
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0D0D12]">
        <div className="text-[#9292A0]">Run not found</div>
      </div>
    );
  }

  const isFailed = run.status === "failed" || run.status === "error";
  const isCompleted = run.status === "completed" || run.status === "success";

  return (
    <div className="flex-1 flex overflow-hidden bg-[#0D0D12]">
      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header Bar */}
        <header className="h-12 bg-[#16161C] border-b border-[#2D2D35] flex items-center justify-between px-4 z-40">
          {/* Left: Breadcrumb */}
          <div className="flex items-center gap-2">
            <Link to="/runs">
              <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Back to runs">
                <ChevronLeft className="w-4 h-4" />
              </Button>
            </Link>
            <span className="text-[#5E5E6B]">/</span>
            <span className="text-[#9292A0] text-sm">Runs</span>
            <span className="text-[#5E5E6B]">/</span>
            <span className="text-[#EDEDF0] text-sm font-medium truncate max-w-[200px]">
              {run.workflow_name} — Run #{run.id.slice(-6)}
            </span>
            <span
              className={cn(
                "ml-2 px-2 py-0.5 rounded text-xs font-medium",
                isCompleted
                  ? "bg-[rgba(40,167,69,0.15)] text-[#28A745]"
                  : isFailed
                  ? "bg-[rgba(229,57,53,0.15)] text-[#E53935]"
                  : "bg-[rgba(146,146,160,0.15)] text-[#9292A0]"
              )}
            >
              {isCompleted ? "Completed" : isFailed ? "Failed" : run.status}
            </span>
          </div>

          {/* Center: Zoom Controls */}
          <div className="flex items-center gap-1" role="group" aria-label="Canvas zoom controls">
            <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Zoom in">
              <ZoomIn className="w-4 h-4" />
            </Button>
            <span className="text-sm text-[#9292A0] min-w-[50px] text-center">100%</span>
            <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Zoom out">
              <ZoomOut className="w-4 h-4" />
            </Button>
            <div className="w-px h-5 bg-[#2D2D35] mx-1" />
            <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Fit to screen" title="Fit to screen">
              <Maximize className="w-4 h-4" />
            </Button>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-3">
            {/* Read-only indicator */}
            <div className="h-6 px-2 rounded bg-[rgba(94,106,210,0.1)] border border-[#5E6AD2]/30 flex items-center gap-1.5 text-[11px] font-medium text-[#5E6AD2]">
              <Activity className="w-3 h-3" />
              Read-only review
            </div>

            {/* Total Cost Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#22222A] border border-[#2D2D35]">
              <DollarSign className="w-3.5 h-3.5 text-[#9292A0]" />
              <span className="text-xs text-[#9292A0]">Total Cost</span>
              <span className="font-mono text-sm text-[#EDEDF0]">
                ${run.total_cost_usd.toFixed(3)}
              </span>
            </div>

            {/* Run Again / Retry Button */}
            <Button
              className={cn(
                "h-9 px-4",
                isFailed
                  ? "bg-[#E53935] hover:bg-[#C62828] text-white"
                  : "bg-[#5E6AD2] hover:bg-[#717EE3] text-white"
              )}
              onClick={handleRunAgain}
            >
              {isFailed ? (
                <>
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  Retry
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Run Again
                </>
              )}
            </Button>
          </div>
        </header>

        {/* Canvas Area with Inspector */}
        <div className="flex-1 flex overflow-hidden">
          {/* Canvas */}
          <div className="flex-1 relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              nodeTypes={nodeTypes}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={true}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.1}
              maxZoom={4}
              className="bg-[#0D0D12]"
            >
              {/* Grid Background */}
              <Background color="#2D2D35" gap={20} size={1} style={{ opacity: 0.3 }} />

              {/* Controls */}
              <Controls className="!bg-[#16161C] !border-[#2D2D35]" />

              {/* MiniMap */}
              <MiniMap
                className="!bg-[#16161C]/90 !border-[#2D2D35]"
                nodeColor={(node) => {
                  const status = (node.data as RunNodeData)?.status;
                  if (status === "completed") return "#28A745";
                  if (status === "failed") return "#E53935";
                  if (status === "pending") return "#9292A0";
                  return "#5E6AD2";
                }}
                maskColor="rgba(13, 13, 18, 0.7)"
              />
            </ReactFlow>
          </div>

          {/* Right Inspector Panel */}
          <InspectorPanel selectedNode={selectedNode} onClose={() => setSelectedNode(null)} />
        </div>

        {/* Bottom Panel */}
        <BottomPanel
          logs={logs}
          executionComplete={true}
          executionFailed={isFailed}
          finalDuration={run.duration_seconds || 0}
        />
      </main>
    </div>
  );
}

// Main export with provider
export function Component() {
  return (
    <ReactFlowProvider>
      <RunDetailInner />
    </ReactFlowProvider>
  );
}

export default Component;
