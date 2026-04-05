import { Badge, BadgeDot } from "@runsight/ui/badge";
import { Button } from "@runsight/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@runsight/ui/tooltip";
import { formatCost, formatDuration } from "@/utils/formatting";
import {
  ArrowUpRight,
  GitFork,
} from "lucide-react";
import type { RunResponse } from "@runsight/shared/zod";

import { useForkWorkflow } from "./useForkWorkflow";
import { useCallback } from "react";
import { useNavigate } from "react-router";
import { WorkflowTopbar } from "@/components/shared";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RunDetailHeaderProps {
  run: RunResponse;
  activeTab?: "canvas" | "yaml";
  onTabChange?: (tab: "canvas" | "yaml") => void;
}

function getRunStatusBadgeVariant(status: string) {
  switch (status) {
    case "completed":
    case "success":
      return "success" as const;
    case "failed":
    case "error":
      return "danger" as const;
    default:
      return "warning" as const;
  }
}

function formatTokenCount(totalTokens: number) {
  if (totalTokens >= 1000) {
    return `${(totalTokens / 1000).toFixed(1)}k`;
  }

  return totalTokens.toLocaleString();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunDetailHeader({
  run,
  activeTab = "canvas",
  onTabChange = () => undefined,
}: RunDetailHeaderProps) {
  const navigate = useNavigate();

  const isFailed = run.status === "failed" || run.status === "error";
  const isCompleted = run.status === "completed" || run.status === "success";
  const isActive = run.status === "running" || run.status === "pending";
  const hasSnapshot = !!run.commit_sha;

  const forkDisabled = isActive || !hasSnapshot;

  const { forkWorkflow, isForking } = useForkWorkflow({
    commitSha: run.commit_sha ?? "",
    workflowPath: `custom/workflows/${run.workflow_id}.yaml`,
    workflowName: run.workflow_name,
    onTransition: (newWorkflowId) => navigate(`/workflows/${newWorkflowId}/edit`),
  });

  const handleOpenWorkflow = useCallback(() => {
    if (run.workflow_id) {
      navigate(`/workflows/${run.workflow_id}/edit`);
    }
  }, [navigate, run.workflow_id]);

  const handleFork = useCallback(() => {
    if (forkDisabled || isForking) return;
    forkWorkflow();
  }, [forkDisabled, isForking, forkWorkflow]);

  // Tooltip message for disabled fork states
  let forkTooltip: string | null = null;
  if (isActive) {
    forkTooltip = "Wait for the run to finish before forking";
  } else if (!hasSnapshot) {
    forkTooltip = "Snapshot unavailable";
  }

  const forkButton = (
    <Button
      variant="primary"
      size="sm"
      disabled={forkDisabled || isForking}
      onClick={handleFork}
      aria-label="Fork"
    >
      <GitFork className="w-4 h-4 mr-2" />
      {isForking ? <>Forking...</> : <>Fork</>}
    </Button>
  );

  return (
    <WorkflowTopbar
      backTo="/runs"
      backLabel="Back to runs"
      title={<span className="truncate text-lg font-medium text-heading">{run.workflow_name}</span>}
      titleAfter={
        <Badge variant={getRunStatusBadgeVariant(run.status)}>
          <BadgeDot />
          {isCompleted ? "Completed" : isFailed ? "Failed" : run.status}
        </Badge>
      }
      metrics={
        <div className="flex items-center gap-3 font-mono text-2xs text-muted">
          <Badge variant="warning">Read-only review</Badge>
          <div className="flex items-center gap-3 whitespace-nowrap">
            <span>{formatDuration(run.duration_seconds)}</span>
            <span>{formatTokenCount(run.total_tokens)} tok</span>
            <span className="text-success-11">{formatCost(run.total_cost_usd)}</span>
          </div>
        </div>
      }
      actions={
        <>
          {run.workflow_id ? (
            <Button
              variant="secondary"
              onClick={handleOpenWorkflow}
            >
              <ArrowUpRight className="w-4 h-4 mr-2" />
              Open Workflow
            </Button>
          ) : null}
          {forkTooltip ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger render={forkButton} />
                <TooltipContent>{forkTooltip}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            forkButton
          )}
        </>
      }
      activeTab={activeTab}
      onValueChange={(value) => onTabChange(value as "canvas" | "yaml")}
      toggleVisibility={{ canvas: true, yaml: true }}
    />
  );
}
