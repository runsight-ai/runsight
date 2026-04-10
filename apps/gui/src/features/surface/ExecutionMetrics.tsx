import { useState, useEffect, useRef } from "react";
import { useRun } from "@/queries/runs";
import { useCanvasStore } from "@/store/canvas";
import { CheckCircle, AlertCircle, Clock, Coins, Hash } from "lucide-react";

interface ExecutionMetricsProps {
  /** The run ID to display metrics for. Typically the last completed/failed run. */
  runId: string | null;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "--";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs.toFixed(0)}s`;
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`;
}

function formatTokens(total_tokens: number): string {
  if (total_tokens >= 1000) {
    return `${(total_tokens / 1000).toFixed(1)}k`;
  }
  return String(total_tokens);
}

export function ExecutionMetrics({ runId }: ExecutionMetricsProps) {
  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const [visible, setVisible] = useState(false);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: run } = useRun(runId ?? "", {
    refetchInterval: false,
  });

  const status = run?.status;
  const isTerminal = status === "completed" || status === "failed";

  // Show metrics when a run reaches a terminal state
  useEffect(() => {
    if (runId && isTerminal && runId !== lastRunId) {
      setVisible(true);
      setLastRunId(runId);

      // Clear any existing timer
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      // Auto-hide after 5 seconds
      timerRef.current = setTimeout(() => {
        setVisible(false);
      }, 5000);
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [runId, isTerminal, lastRunId]);

  // Hide when a new run starts
  useEffect(() => {
    if (activeRunId) {
      setVisible(false);
    }
  }, [activeRunId]);

  if (!visible || !run || !isTerminal) {
    return null;
  }

  const isFailed = status === "failed";

  return (
    <div
      className={`flex items-center gap-3 px-3 py-1 rounded-md text-xs transition-opacity ${
        isFailed
          ? "bg-danger-2 text-danger-11"
          : "bg-success-2 text-success-11"
      }`}
      role="status"
      aria-label={`Run ${status}: cost ${formatCost(run.total_cost_usd)}, ${formatTokens(run.total_tokens)} tokens, duration ${formatDuration(run.duration_seconds)}`}
      aria-live="polite"
    >
      {isFailed ? (
        <AlertCircle className="w-3.5 h-3.5 text-danger-9" />
      ) : (
        <CheckCircle className="w-3.5 h-3.5 text-success-9" />
      )}

      <span className="flex items-center gap-1">
        <Coins className="w-3 h-3 opacity-60" />
        {formatCost(run.total_cost_usd)}
      </span>

      <span className="flex items-center gap-1">
        <Hash className="w-3 h-3 opacity-60" />
        {formatTokens(run.total_tokens)} tokens
      </span>

      <span className="flex items-center gap-1">
        <Clock className="w-3 h-3 opacity-60" />
        {formatDuration(run.duration_seconds)}
      </span>
    </div>
  );
}
