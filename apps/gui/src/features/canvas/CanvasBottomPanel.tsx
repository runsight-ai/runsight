import { useState, useRef, useEffect } from "react";
import { useRunLogs, useRuns } from "@/queries/runs";
import { useCanvasStore } from "@/store/canvas";
import { mapSSEEventToStoreAction } from "./useRunStream";

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface CanvasBottomPanelProps {
  runId?: string;
  workflowId?: string;
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

export function CanvasBottomPanel({ runId: initialRunId, workflowId }: CanvasBottomPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"logs" | "runs">("logs");
  const [selectedRunId, setSelectedRunId] = useState<string | undefined>(initialRunId);
  const logsRef = useRef<HTMLDivElement>(null);
  const [sseEntries, setSseEntries] = useState<LogEntry[]>([]);

  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const setNodeStatus = useCanvasStore((s) => s.setNodeStatus);
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);
  const setRunCost = useCanvasStore((s) => s.setRunCost);

  // Use activeRunId from store as primary, fall back to selectedRunId or prop
  const currentRunId = activeRunId ?? selectedRunId ?? initialRunId;

  const { data: logData } = useRunLogs(currentRunId ?? "", undefined, {
    refetchInterval: undefined,
  });

  const { data: runsData } = useRuns(
    workflowId ? { workflow_id: workflowId } : undefined,
  );

  const entries: LogEntry[] = [
    ...((logData as LogEntry[]) ?? []),
    ...sseEntries,
  ];

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

  const runs = runsData?.items ?? [];

  return (
    <div
      data-testid="canvas-bottom-panel"
      className={isExpanded ? "h-[200px]" : "h-9"}
    >
      <div role="tablist" className="flex items-center h-9 border-t px-2">
        <button
          role="tab"
          aria-selected={activeTab === "logs"}
          onClick={() => {
            setActiveTab("logs");
            setIsExpanded(true);
          }}
        >
          Logs
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "runs"}
          onClick={() => {
            setActiveTab("runs");
            setIsExpanded(true);
          }}
        >
          Runs
        </button>
      </div>
      {isExpanded && activeTab === "logs" && (
        <div ref={logsRef} className="overflow-auto flex-1">
          {entries.map((entry, i) => (
            <div key={i} className="text-xs font-mono px-2 py-0.5">
              <span className="text-muted-foreground">{entry.timestamp}</span>{" "}
              <span className="uppercase">{entry.level}</span>{" "}
              <span>{entry.message}</span>
            </div>
          ))}
        </div>
      )}
      {isExpanded && activeTab === "runs" && (
        <div className="overflow-auto flex-1">
          {runs.map((run) => (
            <div
              key={run.id}
              className="text-xs font-mono px-2 py-1 cursor-pointer hover:bg-muted"
              onClick={() => onRunSelect(run.id)}
            >
              <span className="inline-block w-20">{run.status}</span>
              <span className="inline-block w-20">
                {run.duration_seconds != null
                  ? `${run.duration_seconds.toFixed(1)}s`
                  : "-"}
              </span>
              <span className="inline-block w-20">
                {run.total_cost_usd != null
                  ? `$${run.total_cost_usd.toFixed(4)}`
                  : "-"}
              </span>
              <span className="text-muted-foreground">{run.id}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
