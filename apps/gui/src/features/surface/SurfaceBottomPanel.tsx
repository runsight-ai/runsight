import { useState, useRef, useEffect, useMemo } from "react";
import { useRunLogs, useRunRegressions, useRuns } from "@/queries/runs";
import { useWorkflowRegressions } from "@/queries/workflows";
import { useCanvasStore } from "@/store/canvas";
import { mapSSEEventToStoreAction } from "./useRunStream";
import { useNavigate } from "react-router";
import { Badge } from "@runsight/ui/badge";
import { cn } from "@runsight/ui/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@runsight/ui/tooltip";
import { AlertTriangle } from "lucide-react";
import type { RunResponse } from "@runsight/shared/zod";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import { RegressionTooltipBody } from "@/components/shared/RegressionTooltipBody";
import { formatCost, formatDuration, getTimeAgo } from "@/utils/formatting";

interface LogEntry {
  timestamp: string | number;
  level: string;
  message: string;
}

interface SurfaceBottomPanelProps {
  runId?: string;
  workflowId?: string;
  defaultState?: "collapsed" | "expanded";
  executionSummary?: {
    tone: "success" | "danger";
    text: string;
  };
}

type RegressionsData = {
  count?: number;
  issues?: Array<Record<string, unknown>>;
};

type SurfaceBottomPanelContentProps = SurfaceBottomPanelProps & {
  regressionsData?: RegressionsData;
};

const SURFACE_RUNS_TABLE_CONTAINER_CLASS = "overflow-hidden rounded-lg bg-surface-primary";
const SURFACE_RUNS_TABLE_CLASS = "text-sm";
const SURFACE_RUNS_TABLE_HEADER_ROW_CLASS = "hover:bg-transparent";
const SURFACE_RUNS_TABLE_HEAD_CLASS =
  "h-9 border-b border-border-subtle px-2.5 text-2xs font-medium uppercase tracking-wider text-muted";
const SURFACE_RUNS_TABLE_STATUS_HEAD_CLASS =
  "w-9 border-b border-border-subtle px-0 text-center";
const SURFACE_RUNS_TABLE_ROW_CLASS =
  "h-[var(--control-height-lg)] cursor-pointer hover:bg-surface-hover";
const SURFACE_RUNS_TABLE_CELL_CLASS = "border-b-0 px-2.5 py-0";
const SURFACE_RUNS_TABLE_STATUS_CELL_CLASS =
  "relative w-9 border-b-0 px-0 py-0 text-center";
const SURFACE_RUNS_TABLE_REGRESSION_STRIPE_CLASS =
  "before:absolute before:bottom-0 before:left-0 before:top-0 before:w-[3px] before:rounded-r-sm before:bg-warning-9";

function getRunStatusTone(status: string) {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return "success";
    case "failed":
    case "error":
      return "danger";
    case "running":
    case "pending":
      return "running";
    case "partial":
    case "paused":
    case "stalled":
      return "info";
    default:
      return "neutral";
  }
}

function SurfaceRunStatusDot({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const tone = getRunStatusTone(status);

  return (
    <span className={cn("inline-flex items-center", className)} title={status}>
      <span
        aria-hidden="true"
        className={cn(
          "size-2 rounded-full",
          tone === "success" && "bg-success-9",
          tone === "danger" && "bg-danger-9",
          tone === "neutral" && "bg-neutral-7",
          tone === "info" && "bg-info-9",
          tone === "running" && "bg-warning-9 animate-[pulse_2s_ease-in-out_infinite]",
        )}
      />
      <span className="sr-only">{status}</span>
    </span>
  );
}

function getSourceVariant(source: RunResponse["source"]) {
  switch (source) {
    case "manual":
      return "neutral";
    case "webhook":
      return "info";
    case "schedule":
      return "accent";
    case "simulation":
      return "warning";
    default:
      return "neutral";
  }
}

function SurfaceRegressionCell({
  runId,
  regressionCount,
}: {
  runId: string;
  regressionCount: number | null | undefined;
}) {
  const { data: regressionData } = useRunRegressions(regressionCount ? runId : "");

  if (!regressionCount) {
    return <span className="text-muted">—</span>;
  }

  const tooltip = regressionData?.issues?.length
    ? formatRegressionTooltip(regressionData.issues)
    : {
        header: `${regressionCount} ${regressionCount === 1 ? "regression" : "regressions"}`,
        lines: ["Regression detected"],
      };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          render={
            <span className="inline-flex items-center gap-1" style={{ color: "var(--warning-11)" }}>
              <AlertTriangle className="h-3.5 w-3.5" />
              {regressionCount}
            </span>
          }
        />
        <TooltipContent className="max-w-[320px] whitespace-normal px-3 py-3">
          <RegressionTooltipBody header={tooltip.header} lines={tooltip.lines} />
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function SurfaceRunsTable({
  runs,
  currentRunId,
  onRowClick,
}: {
  runs: RunResponse[];
  currentRunId?: string;
  onRowClick: (runId: string) => void;
}) {
  if (runs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        No runs found for this workflow.
      </div>
    );
  }

  return (
    <div className={SURFACE_RUNS_TABLE_CONTAINER_CLASS}>
      <Table className={SURFACE_RUNS_TABLE_CLASS}>
        <TableHeader>
          <TableRow className={SURFACE_RUNS_TABLE_HEADER_ROW_CLASS}>
            <TableHead className={cn(SURFACE_RUNS_TABLE_HEAD_CLASS, SURFACE_RUNS_TABLE_STATUS_HEAD_CLASS)}>
              <span className="sr-only">Status</span>
            </TableHead>
            <TableHead className={SURFACE_RUNS_TABLE_HEAD_CLASS}>Run</TableHead>
            <TableHead className={SURFACE_RUNS_TABLE_HEAD_CLASS}>Source</TableHead>
            <TableHead className={SURFACE_RUNS_TABLE_HEAD_CLASS}>Started</TableHead>
            <TableHead className={SURFACE_RUNS_TABLE_HEAD_CLASS}>Duration</TableHead>
            <TableHead className={SURFACE_RUNS_TABLE_HEAD_CLASS}>Cost</TableHead>
            <TableHead className={SURFACE_RUNS_TABLE_HEAD_CLASS}>Eval</TableHead>
            <TableHead className={SURFACE_RUNS_TABLE_HEAD_CLASS}>Regr</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => {
            const rowHasRegression = (run.regression_count ?? 0) > 0;

            return (
              <TableRow
                key={run.id}
                className={cn(
                  SURFACE_RUNS_TABLE_ROW_CLASS,
                  currentRunId === run.id && "bg-surface-selected",
                )}
                onClick={() => onRowClick(run.id)}
              >
                <TableCell
                  className={cn(
                    SURFACE_RUNS_TABLE_STATUS_CELL_CLASS,
                    rowHasRegression && SURFACE_RUNS_TABLE_REGRESSION_STRIPE_CLASS,
                  )}
                >
                  <SurfaceRunStatusDot status={run.status} className="w-full justify-center" />
                </TableCell>
                <TableCell data-type="data" className={cn(SURFACE_RUNS_TABLE_CELL_CLASS, "text-muted")}>
                  {run.run_number != null ? `#${run.run_number}` : "—"}
                </TableCell>
                <TableCell data-type="data" className={SURFACE_RUNS_TABLE_CELL_CLASS}>
                  <Badge variant={getSourceVariant(run.source)}>{run.source}</Badge>
                </TableCell>
                <TableCell data-type="timestamp" className={cn(SURFACE_RUNS_TABLE_CELL_CLASS, "text-muted")}>
                  {run.started_at ? getTimeAgo(new Date(run.started_at * 1000).toISOString()) : "—"}
                </TableCell>
                <TableCell data-type="metric" className={cn(SURFACE_RUNS_TABLE_CELL_CLASS, "text-secondary")}>
                  {formatDuration(run.duration_seconds)}
                </TableCell>
                <TableCell data-type="metric" className={cn(SURFACE_RUNS_TABLE_CELL_CLASS, "text-success-11")}>
                  {formatCost(run.total_cost_usd)}
                </TableCell>
                <TableCell data-type="metric" className={SURFACE_RUNS_TABLE_CELL_CLASS}>
                  {typeof run.eval_pass_pct === "number"
                    ? `${Math.round(run.eval_pass_pct)}%`
                    : typeof run.eval_score_avg === "number"
                      ? run.eval_score_avg.toFixed(2)
                      : <span className="text-muted">—</span>}
                </TableCell>
                <TableCell data-type="metric" className={SURFACE_RUNS_TABLE_CELL_CLASS}>
                  <SurfaceRegressionCell
                    runId={run.id}
                    regressionCount={run.regression_count}
                  />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function sseEventToLogEntry(
  eventType: string,
  data: Record<string, unknown>,
): LogEntry | null {
  const ts = new Date().toISOString();
  switch (eventType) {
    case "node_started":
      return {
        timestamp: ts,
        level: "info",
        message: `Node ${data.node_id as string} started`,
      };
    case "node_completed":
      return {
        timestamp: ts,
        level: "info",
        message: `Node ${data.node_id as string} completed${data.cost_usd != null ? ` ($${(data.cost_usd as number).toFixed(4)})` : ""}`,
      };
    case "node_failed":
      return {
        timestamp: ts,
        level: "error",
        message: `Node ${data.node_id as string} failed: ${(data.error as string) ?? "unknown error"}`,
      };
    case "run_completed":
      return {
        timestamp: ts,
        level: "info",
        message: `Run completed. Total cost: $${((data.total_cost_usd as number) ?? 0).toFixed(4)}`,
      };
    case "run_failed":
      return {
        timestamp: ts,
        level: "error",
        message: `Run failed: ${(data.error as string) ?? "unknown error"}`,
      };
    default:
      return null;
  }
}

function SurfaceBottomPanelContent({
  runId: initialRunId,
  workflowId,
  defaultState = "collapsed",
  executionSummary,
  regressionsData,
}: SurfaceBottomPanelContentProps) {
  const [isExpanded, setIsExpanded] = useState(defaultState === "expanded");
  const [activeTab, setActiveTab] = useState<"logs" | "runs" | "regressions">("logs");
  const [selectedRunId, setSelectedRunId] = useState<string | undefined>(initialRunId);
  const logsRef = useRef<HTMLDivElement>(null);
  const [sseEntries, setSseEntries] = useState<LogEntry[]>([]);
  const navigate = useNavigate();

  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const setNodeStatus = useCanvasStore((s) => s.setNodeStatus);
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);
  const setRunCost = useCanvasStore((s) => s.setRunCost);

  const { data: runsData } = useRuns(
    workflowId ? { workflow_id: workflowId } : undefined,
  );
  const sortedRuns = useMemo(() => {
    const items = runsData?.items ?? [];
    return [...items].sort((left, right) => {
      const leftTime = left.started_at ?? left.created_at ?? 0;
      const rightTime = right.started_at ?? right.created_at ?? 0;
      return rightTime - leftTime;
    });
  }, [runsData?.items]);

  useEffect(() => {
    const fallbackRunId = activeRunId ?? selectedRunId ?? initialRunId ?? sortedRuns[0]?.id;
    if (fallbackRunId && fallbackRunId !== selectedRunId) {
      setSelectedRunId(fallbackRunId);
    }
  }, [activeRunId, initialRunId, selectedRunId, sortedRuns]);

  const currentRunId = activeRunId ?? selectedRunId ?? initialRunId ?? sortedRuns[0]?.id;

  const { data: logData } = useRunLogs(currentRunId ?? "", undefined, {
    refetchInterval: undefined,
  });

  const count = regressionsData?.count ?? 0;
  const regressionsItems = regressionsData?.issues ?? [];
  const regressionEmptyMessage = initialRunId
    ? "No regressions detected for this run."
    : "No regressions detected for this workflow.";

  const entries: LogEntry[] = [...(logData?.items ?? []), ...sseEntries];

  // SSE: EventSource connection to /api/runs/${runId}/stream for real-time log events
  useEffect(() => {
    if (!currentRunId) return;
    const source = new EventSource(`/api/runs/${currentRunId}/stream`);

    const EVENT_TYPES = [
      "log_entry",
      "node_started",
      "node_completed",
      "node_failed",
      "run_completed",
      "run_failed",
    ] as const;

    for (const eventType of EVENT_TYPES) {
      source.addEventListener(eventType, (event) => {
        const data = JSON.parse((event as MessageEvent).data) as Record<string, unknown>;

        if (eventType === "log_entry") {
          const entry = data as unknown as LogEntry;
          setSseEntries((prev) => [...prev, entry]);
          return;
        }

        // Map SSE event to store action for canvas node status updates
        const storeAction = mapSSEEventToStoreAction(eventType, data);
        if (storeAction) {
          switch (storeAction.action) {
            case "setNodeStatus":
              setNodeStatus(storeAction.nodeId, storeAction.status);
              break;
            case "runCompleted":
              setRunCost(storeAction.totalCost);
              setActiveRunId(null);
              break;
            case "runFailed":
              setActiveRunId(null);
              break;
          }
        }

        // Convert node lifecycle events to log entries
        const logEntry = sseEventToLogEntry(eventType, data);
        if (logEntry) {
          setSseEntries((prev) => [...prev, logEntry]);
        }

        // Close EventSource on terminal events
        if (eventType === "run_completed" || eventType === "run_failed") {
          source.close();
        }
      });
    }

    return () => source.close();
  }, [currentRunId, setNodeStatus, setActiveRunId, setRunCost]);

  // Auto-scroll when new entries arrive
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [entries.length]);

  const onRunSelect = (runId: string) => {
    setSelectedRunId(runId);
    setActiveTab("logs");
  };

  return (
    <div
      data-testid="canvas-bottom-panel"
      className="bg-surface-secondary border-t border-border-subtle flex flex-col overflow-hidden"
      style={{
        gridColumn: "1 / -1",
        gridRow: "3",
        minHeight: "37px",
        height: isExpanded ? "200px" : undefined,
      }}
    >
      <div role="tablist" className="flex items-center h-9 px-3 gap-3 shrink-0">
        <button
          data-testid="workflow-logs-tab"
          role="tab"
          aria-label="Expand logs panel"
          aria-selected={activeTab === "logs"}
          onClick={() => {
            setActiveTab("logs");
            setIsExpanded(true);
          }}
          className={`font-mono text-2xs uppercase bg-transparent border-none cursor-pointer py-1 tracking-wide ${activeTab === "logs" ? "text-heading" : "text-muted hover:text-primary"}`}
        >
          Logs
        </button>
        <button
          data-testid="workflow-runs-tab"
          role="tab"
          aria-label="Expand runs panel"
          aria-selected={activeTab === "runs"}
          onClick={() => {
            setActiveTab("runs");
            setIsExpanded(true);
          }}
          className={`font-mono text-2xs uppercase bg-transparent border-none cursor-pointer py-1 tracking-wide ${activeTab === "runs" ? "text-heading" : "text-muted hover:text-primary"}`}
        >
          Runs
        </button>
        <button
          data-testid="workflow-regressions-tab"
          role="tab"
          aria-label="Expand regressions panel"
          aria-selected={activeTab === "regressions"}
          onClick={() => {
            setActiveTab("regressions");
            setIsExpanded(true);
          }}
          className={`font-mono text-2xs uppercase bg-transparent border-none cursor-pointer py-1 tracking-wide ${activeTab === "regressions" ? "text-heading" : "text-muted hover:text-primary"}`}
        >
          Regressions{count > 0 ? ` (${count})` : ""}
        </button>
        <button
          type="button"
          aria-label={isExpanded ? "Collapse panel" : "Expand panel"}
          data-testid="workflow-bottom-panel-toggle"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="ml-auto bg-transparent border-none text-muted cursor-pointer text-sm hover:text-primary"
        >
          {isExpanded ? "\u25BC" : "\u25B2"}
        </button>
      </div>
      {isExpanded && activeTab === "logs" && (
        <div data-testid="workflow-logs-panel" className="flex flex-1 flex-col overflow-hidden">
          {executionSummary ? (
            <div
              role="status"
              data-testid="execution-summary-banner"
              data-tone={executionSummary.tone}
              className={`border-b px-3 py-2 text-sm ${
                executionSummary.tone === "success"
                  ? "bg-success-3 border-success-7 text-success-11"
                  : "bg-danger-3 border-danger-7 text-danger-11"
              }`}
            >
              {executionSummary.text}
            </div>
          ) : null}
          <div ref={logsRef} className="overflow-auto flex-1">
            {!currentRunId ? (
              <div className="flex h-full items-center justify-center text-sm text-muted">
                Select a run to inspect logs.
              </div>
            ) : entries.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-muted">
                No logs captured for this run yet.
              </div>
            ) : (
              entries.map((entry, i) => (
                <div key={i} className="border-b border-border-subtle px-3 py-1.5 text-xs font-mono last:border-b-0">
                  <span className="text-muted-foreground">{entry.timestamp}</span>{" "}
                  <span className="uppercase text-muted">{entry.level}</span>{" "}
                  <span>{entry.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
      {isExpanded && activeTab === "runs" && (
        <div data-testid="workflow-runs-panel" className="overflow-auto flex-1">
          <SurfaceRunsTable
            runs={sortedRuns}
            currentRunId={currentRunId}
            onRowClick={onRunSelect}
          />
        </div>
      )}
      {isExpanded && activeTab === "regressions" && (
        <div className="overflow-auto flex-1">
          {regressionsItems.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted">
              {regressionEmptyMessage}
            </div>
          ) : (
            <div className="px-3 py-3">
              <RegressionTooltipBody
                header={formatRegressionTooltip(regressionsItems).header}
                lines={formatRegressionTooltip(regressionsItems).lines}
                action={{
                  label: "View runs \u2192",
                  onClick: () => navigate(`/runs?workflow=${encodeURIComponent(workflowId ?? "")}`),
                }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RunScopedSurfaceBottomPanel(props: SurfaceBottomPanelProps & { runId: string }) {
  const { data: regressionsData } = useRunRegressions(props.runId);

  return <SurfaceBottomPanelContent {...props} regressionsData={regressionsData} />;
}

function WorkflowScopedSurfaceBottomPanel(props: SurfaceBottomPanelProps) {
  const { data: regressionsData } = useWorkflowRegressions(props.workflowId ?? "");

  return <SurfaceBottomPanelContent {...props} regressionsData={regressionsData} />;
}

export function SurfaceBottomPanel(props: SurfaceBottomPanelProps) {
  if (props.runId) {
    return <RunScopedSurfaceBottomPanel {...props} runId={props.runId} />;
  }

  return <WorkflowScopedSurfaceBottomPanel {...props} />;
}
