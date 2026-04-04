import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router";
import { useWorkflow, useUpdateWorkflow } from "@/queries/workflows";
import { Tabs, TabsList, TabsTrigger } from "@runsight/ui/tabs";
import { Button } from "@runsight/ui/button";
import { RunButton } from "./RunButton";
import { ExecutionMetrics } from "./ExecutionMetrics";
import { useCanvasStore } from "@/store/canvas";
import { useRun } from "@/queries/runs";
import { Save } from "lucide-react";
import { cn } from "@runsight/ui/utils";
import { useForkWorkflow } from "../runs/useForkWorkflow";

interface CanvasTopbarProps {
  workflowId: string;
  activeTab: string;
  onValueChange: (value: string) => void;
  isDirty?: boolean;
  onSave?: () => void;
  yamlValid?: boolean;
  errorCount?: number;
  onAddApiKey?: () => void;
  metricsVisible?: boolean;
  metricsStyle?: "live" | "static" | "none";
  actionButton?: { label: string; variant: string; onClick?: () => void };
  nameEditable?: boolean;
  saveButton?: string;
  toggleVisibility?: { canvas: boolean; yaml: boolean };
  runStatus?: string;
  forkDisabled?: boolean;
  onForkTransition?: (newWorkflowId: string) => void;
}

export function CanvasTopbar({ workflowId, activeTab, onValueChange, isDirty, onSave, yamlValid: _yamlValid = true, errorCount: _errorCount = 0, onAddApiKey, metricsVisible = false, metricsStyle = "none", actionButton, nameEditable = true, saveButton = "ghost", toggleVisibility, runStatus, forkDisabled: _forkDisabled, onForkTransition }: CanvasTopbarProps) {
  const { data: workflow } = useWorkflow(workflowId);
  const updateWorkflow = useUpdateWorkflow();

  const { forkWorkflow, isForking } = useForkWorkflow({
    commitSha: workflow?.commit_sha ?? "",
    workflowPath: `custom/workflows/${workflowId}.yaml`,
    workflowName: workflow?.name ?? "Untitled Workflow",
    onTransition: onForkTransition,
  });

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");

  // Track last completed/failed run for metrics display
  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const [lastTerminalRunId, setLastTerminalRunId] = useState<string | null>(null);
  const prevActiveRunId = useRef<string | null>(null);

  const { data: trackedRun } = useRun(prevActiveRunId.current ?? "", {
    refetchInterval: prevActiveRunId.current ? 2000 : false,
  });

  // When activeRunId is set, remember it for post-completion tracking
  useEffect(() => {
    if (activeRunId) {
      prevActiveRunId.current = activeRunId;
    }
  }, [activeRunId]);

  // When tracked run reaches terminal state, surface it for metrics
  useEffect(() => {
    const status = trackedRun?.status;
    if (prevActiveRunId.current && (status === "completed" || status === "failed")) {
      setLastTerminalRunId(prevActiveRunId.current);
    }
  }, [trackedRun?.status]);

  // Global Cmd+S / Ctrl+S shortcut for save
  const handleKeyboardSave = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        onSave?.();
      }
    },
    [onSave],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyboardSave);
    return () => window.removeEventListener("keydown", handleKeyboardSave);
  }, [handleKeyboardSave]);

  const workflowName = workflow?.name ?? "Untitled Workflow";

  function startEditing() {
    setEditName(workflowName);
    setIsEditing(true);
  }

  function saveName() {
    setIsEditing(false);
    const trimmed = editName.trim();
    if (!workflow || typeof workflow.yaml !== "string") {
      return;
    }

    if (trimmed && trimmed !== workflowName) {
      updateWorkflow.mutate({
        id: workflowId,
        data: {
          name: trimmed,
          yaml: workflow.yaml,
        },
      });
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      saveName();
    }
  }

  // Determine if the snapshot is unavailable for fork (historical mode)
  const snapshotUnavailable = !workflow?.commit_sha;

  // Run status badge rendering
  const statusBadge = runStatus ? (
    <span
      className={cn(
        "ml-2 px-2 py-0.5 rounded text-xs font-medium",
        runStatus === "completed" || runStatus === "success"
          ? "bg-success-3 text-success-9"
          : runStatus === "failed" || runStatus === "error"
            ? "bg-danger-3 text-danger-9"
            : "bg-neutral-3 text-muted",
      )}
    >
      {runStatus}
    </span>
  ) : null;

  // Metrics for historical (static) mode: cost, tokens, duration
  const metricsRunId = metricsStyle === "live" ? lastTerminalRunId : lastTerminalRunId;

  return (
    <header
      className="flex items-center h-[var(--header-height)] border-b border-border-subtle px-4"
      style={{ gridColumn: "1 / -1", gridRow: "1" }}
    >
      {/* Left: Workflow name */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {nameEditable ? (
          isEditing ? (
            <input
              className="font-sans text-lg font-medium text-heading bg-transparent border border-transparent rounded-sm px-1 py-[2px] outline-none hover:bg-surface-hover focus:border-border-focus"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onBlur={saveName}
              onKeyDown={handleKeyDown}
              autoFocus
            />
          ) : (
            <span
              className="text-lg font-medium text-heading cursor-pointer border border-transparent rounded-sm px-1 py-[2px] hover:bg-surface-hover"
              onClick={startEditing}
            >
              {workflowName}
            </span>
          )
        ) : (
          <span className="text-lg font-medium text-heading px-1 py-[2px]">
            <Link to={`/workflows/${workflowId}/edit`} className="hover:underline">
              {workflowName}
            </Link>
          </span>
        )}
        {statusBadge}
      </div>

      {/* Center: Canvas | YAML toggle */}
      {toggleVisibility && (toggleVisibility.canvas || toggleVisibility.yaml) && (
        <div className="flex items-center">
          <Tabs value={activeTab} onValueChange={onValueChange}>
            <TabsList variant="contained">
              {toggleVisibility.canvas && (
                <TabsTrigger value="canvas" className="opacity-50">
                  Canvas
                </TabsTrigger>
              )}
              {toggleVisibility.yaml && (
                <TabsTrigger value="yaml">YAML</TabsTrigger>
              )}
            </TabsList>
          </Tabs>
        </div>
      )}

      {/* Right: actions */}
      <div className="flex items-center gap-2 flex-1 justify-end">
        {metricsVisible && metricsStyle === "static" && (
          <div className="flex items-center gap-2 text-xs text-muted">
            <span>cost: —</span>
            <span>tokens: —</span>
            <span>duration: —</span>
          </div>
        )}
        {metricsVisible && metricsStyle === "live" && (
          <ExecutionMetrics runId={metricsRunId} />
        )}
        {isDirty && <span className="h-2 w-2 rounded-full bg-interactive-default" aria-label="unsaved indicator" />}
        {saveButton !== "hidden" && (
          <Button
            variant={saveButton === "primary" || isDirty ? "primary" : "ghost"}
            size="sm"
            onClick={onSave}
            disabled={saveButton === "disabled"}
          >
            <Save className="w-4 h-4" />
            Save
          </Button>
        )}
        {actionButton ? (
          <Button
            variant={actionButton.variant as "primary" | "danger" | "ghost"}
            onClick={actionButton.label === "Fork" ? forkWorkflow : actionButton.onClick}
            disabled={(snapshotUnavailable || isForking) && actionButton.label === "Fork"}
          >
            {actionButton.label === "Fork" && isForking ? "Forking..." : actionButton.label}
          </Button>
        ) : (
          <RunButton
            workflowId={workflowId}
            isCommitted={Boolean(workflow?.commit_sha)}
            onAddApiKey={onAddApiKey}
          />
        )}
      </div>
    </header>
  );
}
