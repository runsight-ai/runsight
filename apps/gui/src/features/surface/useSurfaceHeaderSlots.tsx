import { useCallback } from "react";
import type { ReactNode } from "react";
import type { RunResponse } from "@runsight/shared/zod";
import { Badge, BadgeDot } from "@runsight/ui/badge";
import { Button } from "@runsight/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@runsight/ui/tooltip";
import { Save, X } from "lucide-react";

import * as runQueries from "@/queries/runs";
import { useForkWorkflow } from "./useForkWorkflow";
import type { WorkflowSurfaceMode } from "./surfaceContract";
import { formatCost, formatDuration } from "@/utils/formatting";

const useOptionalCancelRun =
  "useCancelRun" in runQueries
    ? (runQueries as { useCancelRun: () => { mutate: (runId: string) => void; isPending: boolean } }).useCancelRun
    : () => ({ mutate: (_runId: string) => undefined, isPending: false });

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

type SurfaceHeaderSlotsArgs = {
  mode: WorkflowSurfaceMode;
  run: RunResponse | null | undefined;
  workflowId: string;
  onForkTransition?: (newWorkflowId: string) => void;
};

type SurfaceHeaderSlots = {
  titleAfter?: ReactNode;
  metricsOverride?: ReactNode;
  actionsOverride?: ReactNode;
};

export function useSurfaceHeaderSlots({
  mode,
  run,
  workflowId,
  onForkTransition,
}: SurfaceHeaderSlotsArgs): SurfaceHeaderSlots {
  const cancelRun = useOptionalCancelRun();
  const forkTransition = useCallback(
    (newWorkflowId: string) => {
      if (!onForkTransition) return;

      if (typeof globalThis.setTimeout === "function") {
        globalThis.setTimeout(() => onForkTransition(newWorkflowId), 0);
        return;
      }

      onForkTransition(newWorkflowId);
    },
    [onForkTransition],
  );

  const { forkWorkflow, isForking } = useForkWorkflow({
    commitSha: run?.commit_sha ?? "",
    workflowPath: `custom/workflows/${workflowId}.yaml`,
    workflowName: run?.workflow_name ?? "Untitled Workflow",
    onTransition: forkTransition,
  });

  const isActive = run?.status === "running" || run?.status === "pending";
  const hasSnapshot = Boolean(run?.commit_sha);
  const forkDisabled = !run || isActive || !hasSnapshot;

  const handleFork = useCallback(() => {
    if (forkDisabled || isForking) return;
    forkWorkflow();
  }, [forkDisabled, isForking, forkWorkflow]);

  const handleCancel = useCallback(() => {
    if (!run || !isActive || cancelRun.isPending) return;
    cancelRun.mutate(run.id);
  }, [cancelRun, isActive, run]);

  if (mode !== "readonly" || !run) {
    return {};
  }

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
      {isForking ? "Forking..." : "Fork"}
    </Button>
  );

  return {
    titleAfter: (
      <Badge variant={getRunStatusBadgeVariant(run.status)}>
        <BadgeDot />
        {run.status === "completed"
          ? "Completed"
          : run.status === "failed"
            ? "Failed"
            : run.status === "pending"
              ? "Pending"
              : "Running"}
      </Badge>
    ),
    metricsOverride: (
      <div className="flex items-center gap-3 font-mono text-2xs text-muted">
        <Badge variant="warning">Read-only review</Badge>
        <div className="flex items-center gap-3 whitespace-nowrap">
          <span>{formatDuration(run.duration_seconds)}</span>
          <span>{formatTokenCount(run.total_tokens)} tok</span>
          <span className="text-success-11">{formatCost(run.total_cost_usd)}</span>
        </div>
      </div>
    ),
    actionsOverride: (
      <>
        <Button variant="ghost" size="sm" disabled data-testid="workflow-save-button">
          <Save className="w-4 h-4" />
          Save
        </Button>
        {isActive ? (
          <Button
            variant="danger"
            loading={cancelRun.isPending}
            onClick={handleCancel}
            aria-label="Cancel"
          >
            <X className="w-4 h-4" />
            Cancel
          </Button>
        ) : null}
        {forkTooltip ? (
          <>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger render={forkButton} />
                <TooltipContent>{forkTooltip}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <span className="sr-only">{forkTooltip}</span>
          </>
        ) : (
          forkButton
        )}
      </>
    ),
  };
}
