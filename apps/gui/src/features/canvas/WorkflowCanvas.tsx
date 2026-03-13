import { useCallback, useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  ReactFlowProvider,
  useReactFlow,
  Panel,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useWorkflow, useUpdateWorkflow, useGitStatus, useCommitWorkflow, useAiSuggestCommit } from "@/queries/workflows";
import { CommitModal } from "./CommitModal";
import { UncommittedChangesBadge } from "./UncommittedChangesBadge";
import { cn } from "@/utils/helpers";
import { CanvasSidebar, type PaletteItem } from "./CanvasSidebar";
import { CanvasNode } from "./CanvasNode";
import type { StepNodeData, StepType } from "@/types/schemas/canvas";
import { InspectorPanel } from "./InspectorPanel";
import { BottomPanel, type LogEntry, type LogLevel } from "./BottomPanel";
import { SummaryToast } from "./SummaryToast";
import { YAMLEditor } from "./YAMLEditor";
import { ViewToggle, type ViewMode } from "./ViewToggle";
import {
  serializeToYAML,
  parseYAML,
  yamlNodesToFlowNodes,
  yamlEdgesToFlowEdges,
  validateYAML,
} from "./yaml-utils";
import { Button } from "@/components/ui/button";
import {
  Play,
  Settings,
  ChevronLeft,
  Edit3,
  ZoomIn,
  ZoomOut,
  Maximize,
  ArrowRight,
  Zap,
  LayoutGrid,
  Upload,
  Loader2,
  AlertCircle,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";

// Initial empty canvas position
const defaultViewport = { x: 0, y: 0, zoom: 1 };

interface WorkflowCanvasInnerProps {
  workflowId: string;
}

function WorkflowCanvasInner({ workflowId }: WorkflowCanvasInnerProps) {
  const { data: workflow, isLoading } = useWorkflow(workflowId);
  const updateWorkflow = useUpdateWorkflow();
  const { data: gitStatus } = useGitStatus(workflowId);
  const commitWorkflow = useCommitWorkflow();
  const aiSuggestCommit = useAiSuggestCommit();
  const reactFlowInstance = useReactFlow();

  // Node and edge states
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<StepNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<Node<StepNodeData> | null>(null);

  // UI states
  const [isEditingName, setIsEditingName] = useState(false);
  const [workflowName, setWorkflowName] = useState("");
  const [pulseSidebar, setPulseSidebar] = useState(false);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // View mode state (Visual | Code toggle)
  const [viewMode, setViewMode] = useState<ViewMode>("visual");

  // YAML Editor states
  const [yamlValue, setYamlValue] = useState<string>("");
  const [originalYaml, setOriginalYaml] = useState<string>("");
  const [yamlErrors, setYamlErrors] = useState<string[]>([]);
  const [isYamlValid, setIsYamlValid] = useState(true);
  const [yamlNodeCount, setYamlNodeCount] = useState(0);
  const [yamlEdgeCount, setYamlEdgeCount] = useState(0);
  const [isYamlDirty, setIsYamlDirty] = useState(false);
  const [isYamlSynced, setIsYamlSynced] = useState(false);
  const [showYamlSyncedToast, setShowYamlSyncedToast] = useState(false);

  // Execution states
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionLogs, setExecutionLogs] = useState<LogEntry[]>([]);
  const [totalCost, setTotalCost] = useState(0);
  const [executionStartTime, setExecutionStartTime] = useState<number | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const executionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingExecutionRef = useRef<boolean>(false);

  // Post-execution states
  const [executionComplete, setExecutionComplete] = useState(false);
  const [executionFailed, setExecutionFailed] = useState(false);
  const [finalDuration, setFinalDuration] = useState(0);
  const [finalCost, setFinalCost] = useState(0);
  const [showSummaryToast, setShowSummaryToast] = useState(false);

  // Commit modal states
  const [isCommitModalOpen, setIsCommitModalOpen] = useState(false);
  const [commitSuccess, setCommitSuccess] = useState<{ hash: string; message: string } | null>(null);
  const [commitError, setCommitError] = useState<string | null>(null);

  // Initialize from workflow data
  useEffect(() => {
    if (workflow) {
      setWorkflowName(workflow.name || "Untitled Workflow");

      // Convert workflow blocks to StepNodeData nodes (spec §3.1)
      let workflowNodes: Node<StepNodeData>[] = [];
      if (workflow.blocks && Object.keys(workflow.blocks).length > 0) {
        workflowNodes = Object.entries(workflow.blocks).map(
          ([id, block]: [string, unknown], index) => {
            const b = block as Record<string, unknown>;
            const stepData: StepNodeData = {
              stepId: id,
              name: (b.name as string) || id,
              stepType: (b.type as StepType) || "placeholder",
              soulRef: (b.soul_ref ?? b.soul_id) as string | undefined,
              soulRefs: b.soul_refs as string[] | undefined,
              soulARef: b.soul_a_ref as string | undefined,
              soulBRef: b.soul_b_ref as string | undefined,
              iterations: b.iterations as number | undefined,
              workflowRef: b.workflow_ref as string | undefined,
              evalKey: b.eval_key as string | undefined,
              extractField: b.extract_field as string | undefined,
              innerBlockRef: b.inner_block_ref as string | undefined,
              maxRetries: b.max_retries as number | undefined,
              inputBlockIds: b.input_block_ids as string[] | undefined,
              outputPath: b.output_path as string | undefined,
              contentKey: b.content_key as string | undefined,
              failureContextKeys: b.failure_context_keys as string[] | undefined,
              status: "idle",
              cost: 0.04,
            };
            return {
              id,
              type: "canvasNode",
              position: { x: (b.x as number) || 140 + index * 380, y: (b.y as number) || 140 + (index % 2) * 80 },
              data: stepData,
            };
          }
        );
        setNodes(workflowNodes);
      }

      // Convert workflow edges
      let workflowEdges: Edge[] = [];
      if (workflow.edges && workflow.edges.length > 0) {
        workflowEdges = workflow.edges.map((edge: unknown, index) => {
          const e = edge as { source?: string; target?: string; source_handle?: string; target_handle?: string };
          return {
            id: `e${index}`,
            source: e.source || "",
            target: e.target || "",
            sourceHandle: e.source_handle,
            targetHandle: e.target_handle,
          };
        });
        setEdges(workflowEdges);
      }

      // Generate initial YAML from canvas data
      const yaml = serializeToYAML(workflowNodes, workflowEdges, {
        id: workflow.id ?? undefined,
        name: workflow.name ?? undefined,
        description: workflow.description ?? undefined,
      });
      setYamlValue(yaml);
      setOriginalYaml(yaml);
      setYamlNodeCount(workflowNodes.length);
      setYamlEdgeCount(workflowEdges.length);
    }
  }, [workflow, setNodes, setEdges]);

  // Enable sidebar pulse after 3 seconds if canvas is empty
  useEffect(() => {
    if (nodes.length === 0) {
      setPulseSidebar(true);
    }
  }, [nodes.length]);

  // Execution timer
  useEffect(() => {
    if (isExecuting && executionStartTime) {
      executionTimerRef.current = setInterval(() => {
        setElapsedTime(Date.now() - executionStartTime);
      }, 100);
    } else {
      if (executionTimerRef.current) {
        clearInterval(executionTimerRef.current);
        executionTimerRef.current = null;
      }
    }

    return () => {
      if (executionTimerRef.current) {
        clearInterval(executionTimerRef.current);
      }
    };
  }, [isExecuting, executionStartTime]);

  // Helper: Add log entry
  const addLog = useCallback((level: LogLevel, message: string, nodeId?: string, nodeName?: string) => {
    const newLog: LogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      level,
      message,
      nodeId,
      nodeName,
    };
    setExecutionLogs((prev) => [...prev, newLog]);
  }, []);

  // Helper: Update node status
  const updateNodeStatus = useCallback((nodeId: string, status: StepNodeData["status"], executionCost?: number) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          return {
            ...node,
            data: {
              ...node.data,
              status,
              ...(executionCost !== undefined && { executionCost }),
            },
          };
        }
        return node;
      })
    );
    // Update selectedNode if this is the currently selected node
    setSelectedNode((prev) => {
      if (prev && prev.id === nodeId) {
        return {
          ...prev,
          data: {
            ...prev.data,
            status,
            ...(executionCost !== undefined && { executionCost }),
          },
        };
      }
      return prev;
    });
  }, [setNodes]);

  // Handle Run - simulate execution
  const handleRun = useCallback(async () => {
    if (nodes.length === 0 || isExecuting || pendingExecutionRef.current) return;

    // Reset post-execution states when running again
    setExecutionComplete(false);
    setExecutionFailed(false);
    setShowSummaryToast(false);

    pendingExecutionRef.current = true;
    setIsExecuting(true);
    setExecutionStartTime(Date.now());
    setElapsedTime(0);
    setExecutionLogs([]);
    setTotalCost(0);

    addLog("INFO", "Workflow execution started");

    // Reset all nodes to pending
    nodes.forEach((node) => {
      updateNodeStatus(node.id, "pending");
    });

    // Process nodes sequentially
    let currentCost = 0;
    let hasFailure = false;
    const nodeSequence = [...nodes]; // Copy nodes array
    const runStartTime = Date.now();

    for (let i = 0; i < nodeSequence.length; i++) {
      const node = nodeSequence[i];
      if (!node) continue; // Skip if node is undefined

      const estimatedCost = node.data.cost || 0.04;

      // Update to running
      updateNodeStatus(node.id, "running");
      const nodeName = (node.data as StepNodeData).name;
      addLog("INFO", `Node "${nodeName}" execution started`, node.id, nodeName);

      // Simulate processing time (2 seconds)
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Randomly succeed or fail (90% success rate)
      const isSuccess = Math.random() > 0.1;

      if (isSuccess) {
        const nodeCost = estimatedCost * (0.9 + Math.random() * 0.2); // +/- 10% variation
        currentCost += nodeCost;
        updateNodeStatus(node.id, "completed", nodeCost);
        addLog(
          "INFO",
          `Node "${nodeName}" completed successfully (cost: $${nodeCost.toFixed(4)})`,
          node.id,
          nodeName
        );
        setTotalCost(currentCost);
      } else {
        hasFailure = true;
        updateNodeStatus(node.id, "failed");
        addLog(
          "ERROR",
          `Node "${nodeName}" execution failed`,
          node.id,
          nodeName
        );
        // Continue to next nodes even if one fails (as per typical workflow behavior)
      }
    }

    const runDuration = Date.now() - runStartTime;

    addLog("INFO", `Workflow execution completed. Total cost: $${currentCost.toFixed(4)}`);

    // Set post-execution states
    setExecutionComplete(true);
    setExecutionFailed(hasFailure);
    setFinalDuration(runDuration);
    setFinalCost(currentCost);
    setShowSummaryToast(true);

    setIsExecuting(false);
    setExecutionStartTime(null);
    pendingExecutionRef.current = false;
  }, [nodes, isExecuting, addLog, updateNodeStatus]);

  // Handle Pause (placeholder)
  const handlePause = useCallback(() => {
    console.log("Pause execution - not yet implemented");
    addLog("WARN", "Pause execution requested (not yet implemented)");
  }, [addLog]);

  // Handle Kill (placeholder)
  const handleKill = useCallback(() => {
    console.log("Kill execution - not yet implemented");
    addLog("WARN", "Kill execution requested (not yet implemented)");
    setIsExecuting(false);
    setExecutionStartTime(null);
    pendingExecutionRef.current = false;
  }, [addLog]);

  // Handle Restart (placeholder)
  const handleRestart = useCallback(() => {
    console.log("Restart execution - not yet implemented");
    addLog("INFO", "Restart execution requested");
    handleRun();
  }, [addLog, handleRun]);

  // Commit modal handlers
  const handleOpenCommitModal = useCallback(() => {
    setIsCommitModalOpen(true);
  }, []);

  const handleCloseCommitModal = useCallback(() => {
    setIsCommitModalOpen(false);
    setCommitError(null);
  }, []);

  const handleCommit = useCallback(
    async (message: string) => {
      try {
        const result = await commitWorkflow.mutateAsync({
          id: workflowId,
          message,
        });

        if (result.success) {
          setCommitSuccess({
            hash: result.commitHash,
            message: result.message,
          });
          setCommitError(null);
          setIsCommitModalOpen(false);

          // Hide commit success toast after 5 seconds
          setTimeout(() => {
            setCommitSuccess(null);
          }, 5000);
        }
      } catch (err) {
        setCommitError(err instanceof Error ? err.message : "Commit failed");
      }
    },
    [commitWorkflow, workflowId]
  );

  const handleAiSuggest = useCallback(async () => {
    const changedFiles = gitStatus?.changedFiles ?? [];
    if (changedFiles.length === 0) return "Update workflow";

    const suggestion = await aiSuggestCommit.mutateAsync({
      id: workflowId,
      changedFiles,
    });

    return suggestion;
  }, [aiSuggestCommit, workflowId, gitStatus?.changedFiles]);

  const handleViewFullDiff = useCallback(() => {
    // TODO: Open Monaco diff viewer
    console.log("View full diff - Monaco diff viewer not yet implemented");
  }, []);

  // Check for uncommitted changes
  const hasUncommittedChanges = gitStatus?.hasUncommitted ?? false;
  const changedFiles = gitStatus?.changedFiles ?? [];
  const uncommittedCount = changedFiles.length;

  // Handle connections
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds));
    },
    [setEdges]
  );

  // Handle node selection
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node<StepNodeData>) => {
    setSelectedNode(node);
  }, []);

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Handle drag over for drop
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }, []);

  // Handle drop from sidebar
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (!reactFlowWrapper.current || !reactFlowInstance) return;

      const data = event.dataTransfer.getData("application/json");
      if (!data) return;

      const item: PaletteItem = JSON.parse(data);

      // Get drop position relative to canvas
      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });

      // Create StepNodeData node (spec §3.1)
      const stepId = `${item.type}-${Date.now()}`;
      const newNode: Node<StepNodeData> = {
        id: stepId,
        type: "canvasNode",
        position,
        data: {
          stepId,
          name: item.name,
          stepType: item.type as StepType,
          status: "idle",
          cost: 0.04,
        },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [reactFlowInstance, setNodes]
  );

  // Handle workflow name update
  const handleNameSubmit = useCallback(() => {
    if (workflow && workflowName !== workflow.name) {
      updateWorkflow.mutate({
        id: workflowId,
        data: { name: workflowName },
      });
    }
    setIsEditingName(false);
  }, [workflow, workflowName, workflowId, updateWorkflow]);

  // Handle key press in name input
  const handleNameKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        handleNameSubmit();
      } else if (e.key === "Escape") {
        setWorkflowName(workflow?.name || "Untitled Workflow");
        setIsEditingName(false);
      }
    },
    [handleNameSubmit, workflow]
  );

  // Check if workflow has blocks/nodes
  const hasNodes = nodes.length > 0;
  const isEmpty = !isLoading && !hasNodes;

  // Handle node update from inspector
  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Partial<StepNodeData>) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: { ...node.data, ...data },
            };
          }
          return node;
        })
      );
      // Also update selectedNode if this is the currently selected node
      setSelectedNode((prev) =>
        prev && prev.id === nodeId ? { ...prev, data: { ...prev.data, ...data } } : prev
      );
    },
    [setNodes, setSelectedNode]
  );

  // Handle YAML changes
  const handleYAMLChange = useCallback(
    (newValue: string) => {
      setYamlValue(newValue);
      setIsYamlDirty(newValue !== originalYaml);

      // Validate YAML
      const { isValid, errors } = validateYAML(newValue);
      setIsYamlValid(isValid);
      setYamlErrors(errors);

      // Update node/edge counts from parsed YAML
      const parseResult = parseYAML(newValue);
      setYamlNodeCount(parseResult.nodeCount);
      setYamlEdgeCount(parseResult.edgeCount);
    },
    [originalYaml]
  );

  // Handle YAML save
  const handleYAMLSave = useCallback(() => {
    setOriginalYaml(yamlValue);
    setIsYamlDirty(false);

    // Parse and apply to canvas if valid
    const result = parseYAML(yamlValue);
    if (result.success && result.data) {
      const flowNodes = yamlNodesToFlowNodes(result.data.nodes);
      const flowEdges = yamlEdgesToFlowEdges(result.data.edges);
      setNodes(flowNodes);
      setEdges(flowEdges);
    }
  }, [yamlValue, setNodes, setEdges]);

  // Handle view mode switch
  const handleViewModeChange = useCallback(
    (newMode: ViewMode) => {
      if (newMode === "visual" && viewMode === "code") {
        // Switching from Code to Visual
        // Check if YAML is valid first
        if (!isYamlValid) {
          // Don't switch if YAML has errors
          return;
        }

        // Parse YAML and update canvas
        const result = parseYAML(yamlValue);
        if (result.success && result.data) {
          const flowNodes = yamlNodesToFlowNodes(result.data.nodes);
          const flowEdges = yamlEdgesToFlowEdges(result.data.edges);
          setNodes(flowNodes);
          setEdges(flowEdges);
          if (result.data.workflow?.name) {
            setWorkflowName(result.data.workflow.name);
          }

          // Show sync toast
          setShowYamlSyncedToast(true);
          setTimeout(() => setShowYamlSyncedToast(false), 3000);
        }
      } else if (newMode === "code" && viewMode === "visual") {
        // Switching from Visual to Code
        // Serialize current canvas to YAML
        const yaml = serializeToYAML(nodes, edges, {
          id: workflow?.id ?? undefined,
          name: workflow?.name || workflowName,
          description: workflow?.description ?? undefined,
        });
        setYamlValue(yaml);
        setOriginalYaml(yaml);
        setIsYamlDirty(false);
        setIsYamlSynced(true);

        // Validate the new YAML
        const { isValid, errors } = validateYAML(yaml);
        setIsYamlValid(isValid);
        setYamlErrors(errors);
        setYamlNodeCount(nodes.length);
        setYamlEdgeCount(edges.length);
      }

      setViewMode(newMode);
    },
    [viewMode, isYamlValid, yamlValue, nodes, edges, workflow, workflowName, setNodes, setEdges]
  );

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0D0D12]">
        <div className="flex items-center gap-2 text-[#9292A0]">
          <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Loading workflow...
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex overflow-hidden bg-[#0D0D12]">
      {/* Left Sidebar - Hidden in Code mode per epic §4.6 */}
      {viewMode === "visual" && (
        <CanvasSidebar
          onDragStart={() => {}}
          pulseAnimation={pulseSidebar}
          isCollapsed={isExecuting}
        />
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header Bar */}
        <header className="h-12 bg-[#16161C] border-b border-[#2D2D35] flex items-center justify-between px-4 z-40">
          {/* Left: Read-only banner (when executing) + Back + Workflow Name + View Toggle */}
          <div className="flex items-center gap-3">
            {isExecuting && (
              <div className="h-6 px-2 rounded bg-[rgba(245,166,35,0.1)] border border-[#F5A623]/30 flex items-center gap-1.5 text-[11px] font-medium text-[#F5A623]">
                <AlertCircle className="w-3 h-3" />
                Read-only during execution
              </div>
            )}
            <Link to="/" aria-label="Back to workflows">
              <Button
                variant="ghost"
                size="icon-sm"
                className="w-8 h-8"
                disabled={isExecuting}
                aria-label="Back to workflows"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <span className="text-[#5E5E6B]">/</span>
              {isEditingName ? (
                <input
                  type="text"
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  onBlur={handleNameSubmit}
                  onKeyDown={handleNameKeyDown}
                  autoFocus
                  className="bg-transparent border-b border-[#5E6AD2] text-base font-medium text-[#EDEDF0] focus:outline-none"
                  aria-label="Edit workflow name"
                />
              ) : (
                <>
                  <h1 className="text-base font-medium tracking-tight text-[#EDEDF0]">
                    {workflowName}
                  </h1>
                  <button
                    onClick={() => setIsEditingName(true)}
                    className="w-6 h-6 flex items-center justify-center rounded hover:bg-[#22222A] text-[#5E5E6B] hover:text-[#9292A0] transition-colors"
                    disabled={isExecuting}
                    aria-label="Edit workflow name"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                </>
              )}
            </div>

            {/* Visual | Code Toggle */}
            <div className="ml-4">
              <ViewToggle
                mode={viewMode}
                onChange={handleViewModeChange}
                disabled={isExecuting}
                disableReason="Cannot switch views during execution"
              />
            </div>
          </div>

          {/* Center: Zoom Controls (hidden during execution, show live cost instead) */}
          {isExecuting ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#22222A] border border-[#2D2D35]">
              <span className="text-xs text-[#9292A0]">Total Cost</span>
              <span className="font-mono text-sm text-[#00E5FF]">${totalCost.toFixed(3)}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon-sm" className="w-8 h-8">
                <ZoomIn className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="sm" className="h-8 px-2 text-sm">
                100%
              </Button>
              <Button variant="ghost" size="icon-sm" className="w-8 h-8">
                <ZoomOut className="w-4 h-4" />
              </Button>
              <div className="w-px h-5 bg-[#2D2D35] mx-1" />
              <Button variant="ghost" size="icon-sm" className="w-8 h-8">
                <Maximize className="w-4 h-4" />
              </Button>
            </div>
          )}

          {/* Right: Actions */}
          <div className="flex items-center gap-3">
            {/* Uncommitted Changes Badge */}
            {hasUncommittedChanges && !isExecuting && (
              <UncommittedChangesBadge
                count={uncommittedCount}
                onClick={handleOpenCommitModal}
                disabled={isExecuting}
              />
            )}

            {/* Cost Badge - shows live cost during execution, final cost after */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#22222A] border border-[#2D2D35]">
              <span className="text-xs text-[#9292A0]">Total Cost</span>
              <span className={cn(
                "font-mono text-sm",
                isExecuting ? "text-[#00E5FF]" : "text-[#EDEDF0]"
              )}>
                ${(executionComplete ? finalCost : totalCost).toFixed(3)}
              </span>
            </div>

            {/* Run / Run Again / Retry Button */}
            <Button
              className={cn(
                "h-9 px-4 disabled:opacity-60 disabled:cursor-not-allowed",
                executionFailed
                  ? "bg-[#E53935] hover:bg-[#C62828] text-white"
                  : "bg-[#5E6AD2] hover:bg-[#717EE3] text-white"
              )}
              disabled={!hasNodes || isExecuting}
              onClick={handleRun}
            >
              {isExecuting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Running...
                </>
              ) : executionComplete ? (
                executionFailed ? (
                  <>
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Retry
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Run Again
                  </>
                )
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" fill="currentColor" />
                  Run
                </>
              )}
            </Button>
            <Button variant="ghost" size="icon-sm" className="w-8 h-8">
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        </header>

        {/* Content Area - Canvas or YAML Editor */}
        {viewMode === "visual" ? (
          <>
            {/* Canvas Area */}
            <div className="flex-1 relative" ref={reactFlowWrapper}>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={isExecuting ? undefined : onNodesChange}
                onEdgesChange={isExecuting ? undefined : onEdgesChange}
                onConnect={isExecuting ? undefined : onConnect}
                onNodeClick={onNodeClick}
                onPaneClick={onPaneClick}
                onDragOver={isExecuting ? undefined : onDragOver}
                onDrop={isExecuting ? undefined : onDrop}
                nodeTypes={nodeTypes}
                nodesDraggable={!isExecuting}
                nodesConnectable={!isExecuting}
                elementsSelectable={true}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                defaultViewport={defaultViewport}
                minZoom={0.1}
                maxZoom={4}
                snapToGrid
                snapGrid={[20, 20]}
                className="bg-[#0D0D12]"
              >
                {/* Grid Background */}
                <Background
                  color="#2D2D35"
                  gap={20}
                  size={1}
                  style={{ opacity: 0.3 }}
                />

                {/* Empty State Overlay */}
                {isEmpty && (
                  <Panel position="top-center" className="!bg-transparent !border-0 !top-1/2 !-translate-y-1/2">
                    <div className="flex flex-col items-center">
                      {/* Ghost Rectangle */}
                      <div className="relative w-[480px] h-[280px] border border-dashed border-[#3F3F4A] rounded-lg mb-6 flex items-center justify-center">
                        {/* Ghost Node 1 */}
                        <div className="absolute left-16 top-1/2 -translate-y-1/2 w-[140px] h-[80px] bg-[rgba(34,34,42,0.3)] border border-dashed border-[#3F3F4A] rounded-md flex flex-col p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <div className="w-3 h-3 rounded-full bg-[#5E5E6B]/30" />
                            <div className="h-3 w-20 bg-[#5E5E6B]/20 rounded" />
                          </div>
                          <div className="h-2 w-16 bg-[#5E5E6B]/15 rounded mt-auto" />
                        </div>

                        {/* Connection Line */}
                        <div className="absolute left-[156px] top-1/2 w-16 h-0.5 border-t-2 border-dashed border-[#3F3F4A]/50" />
                        <div className="absolute left-[172px] top-1/2 -translate-y-1/2">
                          <ArrowRight className="w-4 h-4 text-[#3F3F4A] opacity-50" />
                        </div>

                        {/* Ghost Node 2 */}
                        <div className="absolute right-16 top-1/2 -translate-y-1/2 w-[140px] h-[80px] bg-[rgba(34,34,42,0.3)] border border-dashed border-[#3F3F4A] rounded-md flex flex-col p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <div className="w-3 h-3 rounded-full bg-[#5E5E6B]/30" />
                            <div className="h-3 w-20 bg-[#5E5E6B]/20 rounded" />
                          </div>
                          <div className="h-2 w-16 bg-[#5E5E6B]/15 rounded mt-auto" />
                        </div>
                      </div>

                      {/* Hint Text */}
                      <p className="text-sm text-[#9292A0] mb-6">
                        Drag a Step from the sidebar to build your workflow
                      </p>

                      {/* CTAs */}
                      <div className="flex items-center gap-3">
                        <Button
                          className="h-9 px-4 bg-[#5E6AD2] hover:bg-[#717EE3] text-white"
                          disabled
                        >
                          <Zap className="w-4 h-4 mr-2" />
                          Generate workflow with AI
                          <span className="ml-2 text-[10px] font-semibold uppercase opacity-70">Soon</span>
                        </Button>
                        <Button
                          variant="outline"
                          className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A] text-[#EDEDF0]"
                          disabled
                        >
                          <LayoutGrid className="w-4 h-4 mr-2" />
                          From Template
                          <span className="ml-2 text-[10px] font-semibold uppercase opacity-70">Soon</span>
                        </Button>
                        <Button
                          variant="outline"
                          className="h-9 px-4 border-dashed border-[#2D2D35] bg-transparent text-[#9292A0] hover:border-[#5E6AD2] hover:text-[#5E6AD2]"
                          disabled
                        >
                          <Upload className="w-4 h-4 mr-2" />
                          Import YAML
                        </Button>
                      </div>
                    </div>
                  </Panel>
                )}

                {/* Controls */}
                <Controls className="!bg-[#16161C] !border-[#2D2D35]" />

                {/* MiniMap */}
                <MiniMap
                  className="!bg-[#16161C]/90 !border-[#2D2D35]"
                  nodeColor={() => "#5E6AD2"}
                  maskColor="rgba(13, 13, 18, 0.7)"
                />
              </ReactFlow>
            </div>

            {/* Bottom Panel */}
            <BottomPanel
              logs={executionLogs}
              isExecuting={isExecuting}
              executionComplete={executionComplete}
              executionFailed={executionFailed}
              finalDuration={finalDuration}
            />
          </>
        ) : (
          /* YAML Editor View */
          <YAMLEditor
            value={yamlValue}
            onChange={handleYAMLChange}
            onSave={handleYAMLSave}
            isValid={isYamlValid}
            errors={yamlErrors}
            nodeCount={yamlNodeCount}
            edgeCount={yamlEdgeCount}
            isDirty={isYamlDirty}
            isSynced={isYamlSynced}
          />
        )}

        {/* YAML Synced Toast */}
        {showYamlSyncedToast && (
          <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50">
            <div className="flex items-center gap-2 px-4 py-2 bg-[#22222A] border border-[#2D2D35] rounded-lg shadow-lg">
              <CheckCircle className="w-4 h-4 text-[#28A745]" />
              <span className="text-sm text-[#EDEDF0]">Canvas synced from YAML</span>
            </div>
          </div>
        )}

        {/* Summary Toast */}
        <SummaryToast
          isOpen={showSummaryToast}
          duration={formatDuration(finalDuration)}
          cost={finalCost}
          status={executionFailed ? "failed" : "success"}
          onClose={() => setShowSummaryToast(false)}
        />

        {/* Commit Modal */}
        <CommitModal
          isOpen={isCommitModalOpen}
          onClose={handleCloseCommitModal}
          workflowName={workflowName}
          changedFiles={changedFiles}
          onCommit={handleCommit}
          onAiSuggest={handleAiSuggest}
          onViewFullDiff={handleViewFullDiff}
          isCommitting={commitWorkflow.isPending}
          errorMessage={commitError}
        />

        {/* Commit Success Toast */}
        {commitSuccess && (
          <div
            className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50"
            data-testid="commit-success-toast"
          >
            <div className="flex items-center gap-2 px-4 py-2 bg-[#22222A] border border-[#28A745]/30 rounded-lg shadow-lg">
              <CheckCircle className="w-4 h-4 text-[#28A745]" />
              <span className="text-sm text-[#EDEDF0]">
                Committed: {commitSuccess.hash.substring(0, 7)} — {commitSuccess.message.split("\n")[0]}
              </span>
            </div>
          </div>
        )}
      </main>

      {/* Right Inspector Panel (shown when node selected) */}
      {selectedNode && (
        <InspectorPanel
          selectedNode={selectedNode}
          onClose={() => setSelectedNode(null)}
          onNodeUpdate={handleNodeUpdate}
          isExecuting={isExecuting}
          executionComplete={executionComplete}
          elapsedTime={elapsedTime}
          finalDuration={finalDuration}
          executionLogs={executionLogs}
          onPause={handlePause}
          onKill={handleKill}
          onRestart={handleRestart}
          workflowNodes={nodes.map(n => ({ id: n.id, name: (n.data as StepNodeData).name ?? n.id }))}
        />
      )}
    </div>
  );
}

// Helper function to format duration for toast
function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${seconds}s`;
}

// Node types definition — CanvasNode satisfies NodeProps; satisfies ensures type safety without cast
const nodeTypes = {
  canvasNode: CanvasNode,
} satisfies NodeTypes;

// Main export with provider
export function Component() {
  const { id } = useParams<{ id: string }>();

  if (!id) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0D0D12]">
        <div className="text-[#9292A0]">No workflow ID provided</div>
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner workflowId={id} />
    </ReactFlowProvider>
  );
}

export default Component;
