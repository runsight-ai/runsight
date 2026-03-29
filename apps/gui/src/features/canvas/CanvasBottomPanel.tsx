import { useState, useRef, useEffect } from "react";
import { useRunLogs, useRuns } from "@/queries/runs";

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface CanvasBottomPanelProps {
  runId?: string;
  workflowId?: string;
}

export function CanvasBottomPanel({ runId: initialRunId, workflowId }: CanvasBottomPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"logs" | "runs">("logs");
  const [selectedRunId, setSelectedRunId] = useState<string | undefined>(initialRunId);
  const logsRef = useRef<HTMLDivElement>(null);
  const [sseEntries, setSseEntries] = useState<LogEntry[]>([]);

  const currentRunId = selectedRunId ?? initialRunId;

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
    source.addEventListener("log_entry", (event) => {
      const entry = JSON.parse(event.data) as LogEntry;
      setSseEntries((prev) => [...prev, entry]);
    });
    return () => source.close();
  }, [currentRunId]);

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
