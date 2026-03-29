import { useState, useRef, useEffect } from "react";
import { useRunLogs } from "@/queries/runs";

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface CanvasBottomPanelProps {
  runId?: string;
}

export function CanvasBottomPanel({ runId }: CanvasBottomPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const logsRef = useRef<HTMLDivElement>(null);
  const [sseEntries, setSseEntries] = useState<LogEntry[]>([]);

  const { data: logData } = useRunLogs(runId ?? "", undefined, {
    refetchInterval: undefined,
  });

  const entries: LogEntry[] = [
    ...((logData as LogEntry[]) ?? []),
    ...sseEntries,
  ];

  // SSE: EventSource connection to /api/runs/${runId}/stream for real-time log events
  useEffect(() => {
    if (!runId) return;
    const source = new EventSource(`/api/runs/${runId}/stream`);
    source.addEventListener("log_entry", (event) => {
      const entry = JSON.parse(event.data) as LogEntry;
      setSseEntries((prev) => [...prev, entry]);
    });
    return () => source.close();
  }, [runId]);

  // Auto-scroll when new entries arrive
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [entries.length]);

  return (
    <div
      data-testid="canvas-bottom-panel"
      className={isExpanded ? "h-[200px]" : "h-9"}
    >
      <div role="tablist" className="flex items-center h-9 border-t px-2">
        <button
          role="tab"
          onClick={() => setIsExpanded((prev) => !prev)}
          aria-label={isExpanded ? "Collapse panel" : "Expand panel"}
        >
          Logs
        </button>
      </div>
      {isExpanded && (
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
    </div>
  );
}
