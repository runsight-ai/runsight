import { useState } from "react";

import { cn } from "@/utils/helpers";
import { formatTimestamp, formatDuration } from "@/utils/formatting";
import {
  CheckCircle,
  XCircle,
  FileText,
  Bot,
  Package,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { RunLogResponse as LogResponse } from "@/api/runs";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RunBottomPanelProps {
  logs: LogResponse[];
  executionComplete: boolean;
  executionFailed: boolean;
  finalDuration: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const levelConfig = {
  INFO: { bg: "bg-transparent", text: "text-[var(--text-muted)]" },
  WARN: { bg: "bg-warning-3", text: "text-[var(--warning-9)]" },
  ERROR: { bg: "bg-danger-3", text: "text-[var(--danger-9)]" },
  DEBUG: { bg: "bg-transparent", text: "text-[var(--text-muted)]" },
} as const;

const tabs = [
  { id: "logs", label: "Logs", icon: FileText },
  { id: "agent-feed", label: "Agent Feed", icon: Bot },
  { id: "artifacts", label: "Artifacts", icon: Package },
] as const;

type TabId = (typeof tabs)[number]["id"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunBottomPanel({ logs, executionComplete, executionFailed, finalDuration }: RunBottomPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("logs");
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div data-testid="bottom-panel" className={cn("bg-[var(--surface-secondary)] border-t border-[var(--border-default)] flex flex-col z-50", isExpanded ? "h-[200px]" : "h-[36px]")}>
      {/* Tab Bar */}
      <div role="tablist" aria-label="Bottom panel tabs" className="h-9 flex items-center px-4 border-b border-[var(--border-default)] justify-between shrink-0">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => (
            <button key={tab.id} role="tab" aria-selected={activeTab === tab.id} aria-controls={`bottom-panel-${tab.id}`} onClick={() => setActiveTab(tab.id)} className={cn("h-7 px-3 text-[12px] font-medium flex items-center gap-1.5 border-b-2 transition-colors", activeTab === tab.id ? "text-[var(--text-primary)] border-[var(--interactive-default)]" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] border-transparent")}>
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>
        <button onClick={() => setIsExpanded(!isExpanded)} aria-label={isExpanded ? "Collapse panel" : "Expand panel"} className="w-6 h-6 flex items-center justify-center rounded hover:bg-[var(--surface-raised)] text-[var(--text-muted)]">
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {/* Tab Content */}
      {isExpanded && (
        <div className="flex-1 overflow-hidden flex flex-col">
          {activeTab === "logs" && (
            <>
              {executionComplete && (
                <div className={cn("flex items-center gap-2 px-4 py-2 border-b shrink-0", executionFailed ? "bg-danger-3 border-l-[3px] border-l-[var(--danger-9)] border-[var(--border-default)]" : "bg-success-3 border-l-[3px] border-l-[var(--success-9)] border-[var(--border-default)]")}>
                  {executionFailed ? (
                    <><XCircle className="w-4 h-4 text-[var(--danger-9)] shrink-0" /><span className="text-sm text-[var(--text-primary)]">Run failed</span></>
                  ) : (
                    <><CheckCircle className="w-4 h-4 text-[var(--success-9)] shrink-0" /><span className="text-sm text-[var(--text-primary)]">Run completed in {formatDuration(finalDuration)}</span></>
                  )}
                </div>
              )}
              <div className="flex-1 overflow-y-auto">
                {logs.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">No logs available for this run.</div>
                ) : (
                  logs.map((log, index) => {
                    const logLevelKey = log.level?.toUpperCase() as keyof typeof levelConfig;
                    const logLevel = logLevelKey in levelConfig ? logLevelKey : "INFO";
                    const levelStyle = levelConfig[logLevel];
                    return (
                      <div key={log.id} className={cn("flex items-center gap-3 px-3 font-mono text-xs min-h-[24px]", index % 2 === 1 && "bg-surface-secondary")}>
                        <span className="text-[var(--text-muted)] w-[80px] shrink-0">{formatTimestamp(log.timestamp)}</span>
                        <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-medium w-12 text-center shrink-0", levelStyle.bg, levelStyle.text)}>{log.level}</span>
                        {log.node_id && <span className="text-[var(--text-muted)] w-[100px] shrink-0 truncate">[{log.node_id}]</span>}
                        <span className="text-[var(--text-primary)] flex-1 truncate">{log.message}</span>
                      </div>
                    );
                  })
                )}
              </div>
            </>
          )}
          {activeTab === "agent-feed" && (
            <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">Agent Feed coming soon</div>
          )}
          {activeTab === "artifacts" && (
            <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">Artifacts coming soon</div>
          )}
        </div>
      )}
    </div>
  );
}
