import { useCallback } from "react";
import { Link, useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/helpers";
import {
  ChevronLeft,
  RefreshCw,
  AlertTriangle,
  DollarSign,
  ZoomIn,
  ZoomOut,
  Maximize,
  Activity,
} from "lucide-react";
import type { RunResponse } from "@/types/schemas/runs";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RunDetailHeaderProps {
  run: RunResponse;
  totalCostUsd?: number;
  totalTokens?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunDetailHeader({ run }: RunDetailHeaderProps) {
  const navigate = useNavigate();

  const isFailed = run.status === "failed" || run.status === "error";
  const isCompleted = run.status === "completed" || run.status === "success";

  const handleRunAgain = useCallback(() => {
    if (run.workflow_id) {
      navigate(`/workflows/${run.workflow_id}`);
    }
  }, [navigate, run.workflow_id]);

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
        <span className="text-[var(--muted-foreground)] text-sm">Runs</span>
        <span className="text-[var(--text-muted)]">/</span>
        <span className="text-[var(--text-primary)] text-sm font-medium truncate max-w-[200px]">
          {run.workflow_name} — Run #{run.id.slice(-6)}
        </span>
        <span className={cn("ml-2 px-2 py-0.5 rounded text-xs font-medium", isCompleted ? "bg-[var(--success-15)] text-[var(--success-9)]" : isFailed ? "bg-[var(--error-15)] text-[var(--danger-9)]" : "bg-[var(--muted-15)] text-[var(--muted-foreground)]")}>
          {isCompleted ? "Completed" : isFailed ? "Failed" : run.status}
        </span>
      </div>

      {/* Center: Zoom Controls */}
      <div className="flex items-center gap-1" role="group" aria-label="Canvas zoom controls">
        <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Zoom in"><ZoomIn className="w-4 h-4" /></Button>
        <span className="text-sm text-[var(--muted-foreground)] min-w-[50px] text-center">100%</span>
        <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Zoom out"><ZoomOut className="w-4 h-4" /></Button>
        <div className="w-px h-5 bg-[var(--border-default)] mx-1" />
        <Button variant="ghost" size="icon-sm" className="w-8 h-8" aria-label="Fit to screen" title="Fit to screen"><Maximize className="w-4 h-4" /></Button>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        <div className="h-6 px-2 rounded bg-[var(--accent-2)] border border-[var(--interactive-default)]/30 flex items-center gap-1.5 text-[11px] font-medium text-[var(--interactive-default)]">
          <Activity className="w-3 h-3" />
          Read-only review
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[var(--surface-raised)] border border-[var(--border-default)]">
          <DollarSign className="w-3.5 h-3.5 text-[var(--muted-foreground)]" />
          <span className="text-xs text-[var(--muted-foreground)]">Total Cost</span>
          <span className="font-mono text-sm text-[var(--text-primary)]">${run.total_cost_usd.toFixed(3)}</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[var(--surface-raised)] border border-[var(--border-default)]">
          <Activity className="w-3.5 h-3.5 text-[var(--muted-foreground)]" />
          <span className="text-xs text-[var(--muted-foreground)]">Tokens</span>
          <span className="font-mono text-sm text-[var(--text-primary)]">{run.total_tokens.toLocaleString()}</span>
        </div>
        <Button className={cn("h-9 px-4", isFailed ? "bg-[var(--danger-9)] hover:bg-[var(--danger-10)] text-white" : "bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-white")} onClick={handleRunAgain}>
          {isFailed ? (<><AlertTriangle className="w-4 h-4 mr-2" />Retry</>) : (<><RefreshCw className="w-4 h-4 mr-2" />Run Again</>)}
        </Button>
      </div>
    </header>
  );
}
