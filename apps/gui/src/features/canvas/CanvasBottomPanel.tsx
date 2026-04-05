import { useState, useRef, useEffect, useMemo } from "react";
import { AlertTriangle } from "lucide-react";
import { cn } from "@runsight/ui/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import { useRunLogs, useRuns } from "@/queries/runs";
import { useWorkflowRegressions } from "@/queries/workflows";
import { useCanvasStore } from "@/store/canvas";
import { formatCost, formatDuration, getTimeAgo } from "@/utils/formatting";
import { mapSSEEventToStoreAction } from "./useRunStream";
import { useNavigate } from "react-router";
import { RunStatusDot } from "../runs/RunStatusDot";
import {
  RUN_TABLE_CELL_CLASS,
  RUN_TABLE_CLASS,
  RUN_TABLE_CONTAINER_CLASS,
  RUN_TABLE_HEAD_CLASS,
  RUN_TABLE_HEADER_ROW_CLASS,
  RUN_TABLE_ROW_CLASS,
  RUN_TABLE_STATUS_CELL_CLASS,
  RUN_TABLE_STATUS_HEAD_CLASS,
} from "../runs/runTable.styles";

interface LogEntry {
  timestamp: string | number;
  level: string;
  message: string;
}

interface CanvasBottomPanelProps {
  runId?: string;
  workflowId?: string;
  defaultState?: "collapsed" | "expanded";
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

export function CanvasBottomPanel({ runId: initialRunId, workflowId, defaultState = "collapsed" }: CanvasBottomPanelProps) {
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

  const { data: regressionsData } = useWorkflowRegressions(workflowId ?? "");
  const count = regressionsData?.count ?? 0;
  const regressionsItems = regressionsData?.issues ?? [];

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
        <div ref={logsRef} data-testid="workflow-logs-panel" className="overflow-auto flex-1">
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
      )}
      {isExpanded && activeTab === "runs" && (
        <div data-testid="workflow-runs-panel" className="overflow-auto flex-1">
          {sortedRuns.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted">
              No runs found for this workflow.
            </div>
          ) : (
            <div className={RUN_TABLE_CONTAINER_CLASS}>
              <Table className={RUN_TABLE_CLASS}>
                <TableHeader>
                  <TableRow className={RUN_TABLE_HEADER_ROW_CLASS}>
                    <TableHead className={cn(RUN_TABLE_HEAD_CLASS, RUN_TABLE_STATUS_HEAD_CLASS)}>
                      Status
                    </TableHead>
                    <TableHead className={RUN_TABLE_HEAD_CLASS}>Source</TableHead>
                    <TableHead className={RUN_TABLE_HEAD_CLASS}>Started</TableHead>
                    <TableHead className={RUN_TABLE_HEAD_CLASS}>Duration</TableHead>
                    <TableHead className={RUN_TABLE_HEAD_CLASS}>Cost</TableHead>
                    <TableHead className={RUN_TABLE_HEAD_CLASS}>Eval</TableHead>
                    <TableHead className={RUN_TABLE_HEAD_CLASS}>Run</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedRuns.map((run) => (
                    <TableRow
                      key={run.id}
                      data-testid={`workflow-run-row-${run.id}`}
                      className={cn(
                        RUN_TABLE_ROW_CLASS,
                        currentRunId === run.id && "bg-surface-selected",
                      )}
                      onClick={() => onRunSelect(run.id)}
                    >
                      <TableCell className={RUN_TABLE_STATUS_CELL_CLASS}>
                        <RunStatusDot status={run.status} className="w-full justify-center" />
                      </TableCell>
                      <TableCell data-type="data" className={RUN_TABLE_CELL_CLASS}>{run.source}</TableCell>
                      <TableCell data-type="timestamp" className={RUN_TABLE_CELL_CLASS}>
                        {run.started_at ? getTimeAgo(new Date(run.started_at * 1000).toISOString()) : "—"}
                      </TableCell>
                      <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>{formatDuration(run.duration_seconds)}</TableCell>
                      <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>{formatCost(run.total_cost_usd)}</TableCell>
                      <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>
                        {typeof run.eval_pass_pct === "number"
                          ? `${Math.round(run.eval_pass_pct)}%`
                          : typeof run.eval_score_avg === "number"
                            ? run.eval_score_avg.toFixed(2)
                            : "—"}
                      </TableCell>
                      <TableCell data-type="data" className={RUN_TABLE_CELL_CLASS}>
                        {run.run_number != null ? `#${run.run_number}` : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}
      {isExpanded && activeTab === "regressions" && (
        <div className="overflow-auto flex-1">
          {regressionsItems.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted">
              No regressions detected for this workflow.
            </div>
          ) : (
            regressionsItems.map((regression, i) => (
              <div
                key={i}
                className="flex cursor-pointer items-center gap-3 border-b border-border-subtle px-3 py-2 text-xs font-mono last:border-b-0 hover:bg-surface-hover"
                onClick={() => {
                  if (regression.run_id) {
                    navigate(`/runs/${regression.run_id}`);
                  }
                }}
              >
                <AlertTriangle className="w-3.5 h-3.5 text-[var(--warning-9)] shrink-0" />
                <span className="inline-block min-w-[10rem] text-primary">{regression.node_name}</span>
                <span className="inline-block min-w-[9rem] text-muted">{regression.type.replaceAll("_", " ")}</span>
                <span className="inline-block min-w-[5rem] text-primary">
                  {regression.delta.cost_pct != null
                    ? `+${Number(regression.delta.cost_pct).toFixed(0)}%`
                    : regression.delta.score_delta != null
                      ? `${Number(regression.delta.score_delta).toFixed(2)}`
                      : "—"}
                </span>
                <span className="text-muted-foreground">
                  {regression.run_number != null ? `run #${regression.run_number}` : ""}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
