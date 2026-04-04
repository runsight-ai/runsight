import { useCallback } from "react";
import { Link, useNavigate } from "react-router";

import { Button } from "@runsight/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@runsight/ui/tooltip";
import { cn } from "@runsight/ui/utils";
import {
  ChevronLeft,
  ArrowUpRight,
  DollarSign,
  Activity,
  GitFork,
} from "lucide-react";
import type { RunResponse } from "@runsight/shared/zod";

import { useForkWorkflow } from "./useForkWorkflow";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RunDetailHeaderProps {
  run: RunResponse;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunDetailHeader({ run }: RunDetailHeaderProps) {
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
      variant="ghost"
      disabled={forkDisabled || isForking}
      onClick={handleFork}
      aria-label="Fork"
    >
      <GitFork className="w-4 h-4 mr-2" />
      {isForking ? <>Forking...</> : <>Fork</>}
    </Button>
  );

  return (
    <header className="h-12 bg-[var(--surface-secondary)] border-b border-[var(--border-default)] flex items-center justify-between px-4 z-40">
      {/* Left: Breadcrumb */}
      <div className="flex items-center gap-2">
        <Link to="/runs">
          <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Back to runs">
            <ChevronLeft className="w-4 h-4" />
          </Button>
        </Link>
        <span className="text-[var(--text-muted)]">/</span>
        <span className="text-[var(--text-muted)] text-sm">Runs</span>
        <span className="text-[var(--text-muted)]">/</span>
        <span className="text-[var(--text-primary)] text-sm font-medium truncate max-w-[200px]">
          {run.workflow_name} — Run #{run.id.slice(-6)}
        </span>
        <span className={cn("ml-2 px-2 py-0.5 rounded text-xs font-medium", isCompleted ? "bg-success-3 text-[var(--success-9)]" : isFailed ? "bg-danger-3 text-[var(--danger-9)]" : "bg-neutral-3 text-muted")}>
          {isCompleted ? "Completed" : isFailed ? "Failed" : run.status}
        </span>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        <div className="h-6 px-2 rounded bg-[var(--accent-2)] border border-[var(--interactive-default)]/30 flex items-center gap-1.5 text-[11px] font-medium text-[var(--interactive-default)]">
          <Activity className="w-3 h-3" />
          Read-only review
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[var(--surface-raised)] border border-[var(--border-default)]">
          <DollarSign className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs text-[var(--text-muted)]">Total Cost</span>
          <span className="font-mono text-sm text-[var(--text-primary)]">${run.total_cost_usd.toFixed(3)}</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[var(--surface-raised)] border border-[var(--border-default)]">
          <Activity className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs text-[var(--text-muted)]">Tokens</span>
          <span className="font-mono text-sm text-[var(--text-primary)]">{run.total_tokens.toLocaleString()}</span>
        </div>
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
        {run.workflow_id ? (
          <Button
            className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent"
            onClick={handleOpenWorkflow}
          >
            <ArrowUpRight className="w-4 h-4 mr-2" />
            Open Workflow
          </Button>
        ) : null}
      </div>
    </header>
  );
}
