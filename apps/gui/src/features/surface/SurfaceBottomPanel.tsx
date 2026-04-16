import { useState, useRef, useEffect, useMemo } from "react";
import { ContextAuditEventV1Schema } from "@runsight/shared/zod";
import {
  useRunContextAudit,
  useRunContextAuditStream,
  useRunLogs,
  useRunRegressions,
  useRuns,
} from "@/queries/runs";
import { useWorkflowRegressions } from "@/queries/workflows";
import { useCanvasStore } from "@/store/canvas";
import { mapSSEEventToStoreAction } from "./useRunStream";
import { useNavigate } from "react-router";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import { RegressionTooltipBody } from "@/components/shared/RegressionTooltipBody";
import { SurfaceRunsTable } from "./SurfaceRunsTable";
import type { WorkflowRegression } from "@/types/schemas/regressions";
import { useContextAuditStore } from "@/store/contextAudit";

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
  issues?: WorkflowRegression[];
};

type SurfaceBottomPanelContentProps = SurfaceBottomPanelProps & {
  regressionsData?: RegressionsData;
};

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
  const appendContextAuditEvents = useContextAuditStore((s) => s.appendEvents);

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
  useRunContextAudit(currentRunId ?? "", { page_size: 100 });
  useRunContextAuditStream(currentRunId, { enabled: false });

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

    source.addEventListener("context_resolution", (event) => {
      try {
        const auditEvent = ContextAuditEventV1Schema.parse(
          JSON.parse((event as MessageEvent).data),
        );
        if (auditEvent.run_id === currentRunId) {
          appendContextAuditEvents(currentRunId, [auditEvent]);
        }
      } catch {
        return;
      }
    });

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
  }, [appendContextAuditEvents, currentRunId, setNodeStatus, setActiveRunId, setRunCost]);

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
