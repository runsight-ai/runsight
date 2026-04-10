import { useState, useEffect, useRef, useCallback } from "react";
import { Link, useInRouterContext } from "react-router";
import { useWorkflow, useUpdateWorkflow } from "@/queries/workflows";
import { Button } from "@runsight/ui/button";
import { Badge } from "@runsight/ui/badge";
import { RunButton } from "./RunButton";
import { ExecutionMetrics } from "./ExecutionMetrics";
import { useCanvasStore } from "@/store/canvas";
import { useCancelRun, useRun } from "@/queries/runs";
import { Save, X } from "lucide-react";
import { useForkWorkflow } from "./useForkWorkflow";
import { WorkflowTopbar } from "@/components/shared";

interface SurfaceTopbarProps {
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
  backTo?: string;
  backLabel?: string;
  titleOverride?: React.ReactNode;
  titleAfter?: React.ReactNode;
  metricsOverride?: React.ReactNode;
  actionsOverride?: React.ReactNode;
  runId?: string;
  forkConfigOverride?: {
    commitSha?: string;
    workflowPath?: string;
    workflowName?: string;
  };
}

export function SurfaceTopbar({
  workflowId,
  activeTab,
  onValueChange,
  isDirty,
  onSave,
  yamlValid: _yamlValid = true,
  errorCount: _errorCount = 0,
  onAddApiKey,
  metricsVisible = false,
  metricsStyle = "none",
  actionButton,
  nameEditable = true,
  saveButton = "ghost",
  toggleVisibility,
  runStatus,
  forkDisabled: _forkDisabled,
  onForkTransition,
  backTo = "/flows",
  backLabel = "Back to flows",
  titleOverride,
  titleAfter,
  metricsOverride,
  actionsOverride,
  runId,
  forkConfigOverride,
}: SurfaceTopbarProps) {
  const hasRouter = useInRouterContext();
  const { data: workflow } = useWorkflow(workflowId);
  const updateWorkflow = useUpdateWorkflow();
  const cancelRun = useCancelRun();

  const { forkWorkflow, isForking } = useForkWorkflow({
    commitSha: forkConfigOverride?.commitSha ?? workflow?.commit_sha ?? "",
    workflowPath:
      forkConfigOverride?.workflowPath ?? `custom/workflows/${workflowId}.yaml`,
    workflowName:
      forkConfigOverride?.workflowName ?? workflow?.name ?? "Untitled Workflow",
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
  const targetRunId = runId ?? activeRunId ?? null;
  const { data: actionRun } = useRun(targetRunId ?? "", {
    refetchInterval: actionButton?.label === "Cancel" && targetRunId ? 2000 : false,
  });
  const isCancelableRun =
    actionRun?.status === "running" || actionRun?.status === "pending";

  function startEditing() {
    setEditName(workflowName);
    setIsEditing(true);
  }

  function saveName(nextName = editName) {
    setIsEditing(false);
    const trimmed = nextName.trim();
    if (trimmed && trimmed !== workflowName) {
      updateWorkflow.mutate({
        id: workflowId,
        data: {
          name: trimmed,
          yaml: typeof workflow?.yaml === "string" ? workflow.yaml : "",
        },
      });
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      saveName(e.currentTarget?.value ?? editName);
    }
  }

  // Determine if the snapshot is unavailable for fork (historical mode)
  const snapshotUnavailable = !workflow?.commit_sha;

  // Run status badge rendering
  const statusBadge = runStatus ? (
    <Badge
      variant={
        runStatus === "completed" || runStatus === "success"
          ? "success"
          : runStatus === "failed" || runStatus === "error"
            ? "danger"
            : "warning"
      }
    >
      {runStatus}
    </Badge>
  ) : null;

  // Metrics for historical (static) mode: cost, tokens, duration
  const metricsRunId = lastTerminalRunId;

  const titleNode = titleOverride ?? (
    <>
      {nameEditable ? (
        isEditing ? (
          <input
            className="font-sans text-lg font-medium text-heading bg-transparent border border-transparent rounded-sm px-1 py-[2px] outline-none hover:bg-surface-hover focus:border-border-focus"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={(e) => saveName(e?.currentTarget?.value ?? editName)}
            onKeyDown={handleKeyDown}
            data-testid="workflow-name-input"
            autoFocus
          />
        ) : (
          <span
            className="text-lg font-medium text-heading cursor-pointer border border-transparent rounded-sm px-1 py-[2px] hover:bg-surface-hover"
            onClick={startEditing}
            data-testid="workflow-name-display"
          >
            {workflowName}
          </span>
        )
      ) : (
        <span className="text-lg font-medium text-heading px-1 py-[2px]">
          {hasRouter ? (
            <Link to={`/workflows/${workflowId}/edit`} className="hover:underline">
              {workflowName}
            </Link>
          ) : (
            <a href={`/workflows/${workflowId}/edit`} className="hover:underline">
              {workflowName}
            </a>
          )}
        </span>
      )}
      {statusBadge}
    </>
  );

  const metricsNode =
    metricsOverride ??
    (metricsVisible && metricsStyle === "live" ? <ExecutionMetrics runId={metricsRunId} /> : null);

  const actionsNode =
    actionsOverride ??
    (
      <>
        {isDirty ? <span className="h-2 w-2 rounded-full bg-interactive-default" aria-label="unsaved indicator" /> : null}
        {saveButton !== "hidden" && (
          <Button
            variant={saveButton === "primary" || isDirty ? "primary" : "ghost"}
            size="sm"
            onClick={onSave}
            disabled={saveButton === "disabled"}
            data-testid="workflow-save-button"
          >
            <Save className="w-4 h-4" />
            Save
          </Button>
        )}
        {actionButton ? (
          <Button
            variant={actionButton.variant as "primary" | "danger" | "ghost"}
            loading={actionButton.label === "Cancel" ? cancelRun.isPending : false}
            onClick={
              actionButton.label === "Fork"
                ? forkWorkflow
                : actionButton.label === "Cancel"
                  ? () => {
                      if (!targetRunId || !isCancelableRun) return;
                      cancelRun.mutate(targetRunId);
                    }
                  : actionButton.onClick
            }
            disabled={
              ((snapshotUnavailable || isForking) && actionButton.label === "Fork")
              || (actionButton.label === "Cancel" && (!targetRunId || !isCancelableRun))
            }
          >
            {actionButton.label === "Cancel" ? <X className="w-4 h-4" /> : null}
            {actionButton.label === "Fork" && isForking ? "Forking..." : actionButton.label}
          </Button>
        ) : (
          <RunButton
            workflowId={workflowId}
            isCommitted={Boolean(workflow?.commit_sha)}
            onAddApiKey={onAddApiKey}
          />
        )}
      </>
    );

  return (
    <WorkflowTopbar
      backTo={backTo}
      backLabel={backLabel}
      title={titleNode}
      titleAfter={titleAfter}
      metrics={metricsNode}
      actions={actionsNode}
      activeTab={activeTab}
      onValueChange={onValueChange}
      toggleVisibility={toggleVisibility}
    />
  );
}
