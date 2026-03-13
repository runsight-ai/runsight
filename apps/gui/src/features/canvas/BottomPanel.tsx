import { useState, useRef, useEffect } from "react";
import { cn } from "@/utils/helpers";
import { ChevronDown, ChevronUp, Play, Pause, CheckCircle, XCircle } from "lucide-react";

type TabId = "logs" | "agent-feed" | "artifacts";

export type LogLevel = "INFO" | "WARN" | "ERROR" | "DEBUG";

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  nodeId?: string;
  nodeName?: string;
  message: string;
}

interface BottomPanelProps {
  logs: LogEntry[];
  isExecuting?: boolean;
  executionComplete?: boolean;
  executionFailed?: boolean;
  finalDuration?: number;
  className?: string;
}

const levelConfig: Record<LogLevel, { bg: string; text: string }> = {
  INFO: { bg: "bg-transparent", text: "text-[#9292A0]" },
  WARN: { bg: "bg-[rgba(245,166,35,0.12)]", text: "text-[#F5A623]" },
  ERROR: { bg: "bg-[rgba(229,57,53,0.12)]", text: "text-[#E53935]" },
  DEBUG: { bg: "bg-transparent", text: "text-[#5E5E6B]" },
};

export function BottomPanel({
  logs,
  isExecuting = false,
  executionComplete = false,
  executionFailed = false,
  finalDuration = 0,
  className,
}: BottomPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("logs");
  const [isExpanded, setIsExpanded] = useState(true);
  const [height, setHeight] = useState(200);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const [isResizing, setIsResizing] = useState(false);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const resizeStartY = useRef<number>(0);
  const resizeStartHeight = useRef<number>(200);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isAutoScroll && isExpanded && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs, isAutoScroll, isExpanded]);

  // Handle resize
  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    resizeStartY.current = e.clientY;
    resizeStartHeight.current = height;
  };

  useEffect(() => {
    const handleResizeMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const delta = resizeStartY.current - e.clientY;
      const newHeight = Math.max(36, Math.min(window.innerHeight * 0.5, resizeStartHeight.current + delta));
      setHeight(newHeight);
    };

    const handleResizeEnd = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener("mousemove", handleResizeMove);
      document.addEventListener("mouseup", handleResizeEnd);
    }

    return () => {
      document.removeEventListener("mousemove", handleResizeMove);
      document.removeEventListener("mouseup", handleResizeEnd);
    };
  }, [isResizing]);

  const tabs: { id: TabId; label: string }[] = [
    { id: "logs", label: "Logs" },
    { id: "agent-feed", label: "Agent Feed" },
    { id: "artifacts", label: "Artifacts" },
  ];

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  return (
    <div
      className={cn(
        "bg-[#16161C] border-t border-[#2D2D35] flex flex-col z-50",
        className
      )}
      style={{ height: isExpanded ? height : 36 }}
    >
      {/* Resize Handle */}
      {isExpanded && (
        <div
          className="h-1 w-full cursor-ns-resize hover:bg-[#3F3F4A] transition-colors"
          onMouseDown={handleResizeStart}
        />
      )}

      {/* Tab Bar */}
      <div className="h-9 flex items-center px-4 border-b border-[#2D2D35] justify-between shrink-0">
        <div className="flex items-center gap-1" role="tablist" aria-label="Bottom panel tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`tabpanel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "h-7 px-3 text-[12px] font-medium border-b-2 transition-colors",
                activeTab === tab.id
                  ? "text-[#EDEDF0] border-[#5E6AD2]"
                  : "text-[#9292A0] hover:text-[#EDEDF0] border-transparent"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {isExecuting && (
            <button
              onClick={() => setIsAutoScroll(!isAutoScroll)}
              className={cn(
                "h-6 px-2 rounded text-xs flex items-center gap-1.5 transition-colors",
                isAutoScroll
                  ? "text-[#00E5FF] bg-[rgba(0,229,255,0.1)]"
                  : "text-[#9292A0] hover:bg-[#22222A]"
              )}
            >
              {isAutoScroll ? (
                <>
                  <Pause className="w-3 h-3" />
                  Auto-scroll
                </>
              ) : (
                <>
                  <Play className="w-3 h-3" />
                  Paused
                </>
              )}
            </button>
          )}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-[#22222A] text-[#9292A0]"
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronUp className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {isExpanded && (
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Logs Tab */}
          {activeTab === "logs" && (
            <div id="tabpanel-logs" role="tabpanel" aria-label="Logs" className="flex-1 flex flex-col min-h-0">
              {/* Completion Banner */}
              {executionComplete && (
                <div
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 border-b shrink-0",
                    executionFailed
                      ? "bg-[rgba(229,57,53,0.08)] border-l-[3px] border-l-[#E53935] border-[#2D2D35]"
                      : "bg-[rgba(40,167,69,0.08)] border-l-[3px] border-l-[#28A745] border-[#2D2D35]"
                  )}
                >
                  {executionFailed ? (
                    <>
                      <XCircle className="w-4 h-4 text-[#E53935] shrink-0" />
                      <span className="text-sm text-[#EDEDF0]">Run failed</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4 text-[#28A745] shrink-0" />
                      <span className="text-sm text-[#EDEDF0]">
                        Run completed successfully in {formatDuration(finalDuration)}
                      </span>
                    </>
                  )}
                </div>
              )}
              <div
                ref={logsContainerRef}
                className="flex-1 overflow-y-auto"
              >
                {logs.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-[#5E5E6B] text-sm">
                    No logs yet. Start execution to see logs.
                  </div>
                ) : (
                  logs.map((log, index) => {
                  const levelStyle = levelConfig[log.level];
                  return (
                    <div
                      key={log.id}
                      className={cn(
                        "flex items-center gap-3 px-3 font-mono text-xs min-h-[24px]",
                        index % 2 === 1 && "bg-[rgba(255,255,255,0.02)]"
                      )}
                    >
                      <span className="text-[#5E5E6B] w-[120px] shrink-0">
                        {formatTimestamp(log.timestamp)}
                      </span>
                      <span
                        className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-medium w-12 text-center shrink-0",
                          levelStyle.bg,
                          levelStyle.text
                        )}
                      >
                        {log.level}
                      </span>
                      {log.nodeName && (
                        <span className="text-[#5E5E6B] w-[100px] shrink-0 truncate">
                          {log.nodeName}
                        </span>
                      )}
                      <span className="text-[#EDEDF0] flex-1 truncate">{log.message}</span>
                    </div>
                  );
                })
              )}
              </div>
            </div>
          )}

          {/* Agent Feed Tab (Placeholder) */}
          {activeTab === "agent-feed" && (
            <div id="tabpanel-agent-feed" role="tabpanel" aria-label="Agent Feed" className="flex items-center justify-center h-full text-[#5E5E6B] text-sm">
              Agent Feed coming soon
            </div>
          )}

          {/* Artifacts Tab (Placeholder) */}
          {activeTab === "artifacts" && (
            <div id="tabpanel-artifacts" role="tabpanel" aria-label="Artifacts" className="flex items-center justify-center h-full text-[#5E5E6B] text-sm">
              Artifacts coming soon
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Helper function to format duration
function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${seconds}s`;
}

export default BottomPanel;
