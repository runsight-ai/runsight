import { useState, useMemo } from "react";
import { useNavigate } from "react-router";

import { cn } from "@runsight/ui/utils";
import { Badge } from "@runsight/ui/badge";
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
import { formatTimestamp, formatDuration } from "@/utils/formatting";
import { CheckCircle, XCircle, FileText, List, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { useRuns, useRunRegressions } from "@/queries/runs";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import type { RunLogResponse as LogResponse } from "@/api/runs";
import { RunStatusDot } from "./RunStatusDot";
import {
  RUN_TABLE_CELL_CLASS,
  RUN_TABLE_CLASS,
  RUN_TABLE_CONTAINER_CLASS,
  RUN_TABLE_HEAD_CLASS,
  RUN_TABLE_HEADER_ROW_CLASS,
  RUN_TABLE_ROW_CLASS,
  RUN_TABLE_STATUS_CELL_CLASS,
  RUN_TABLE_STATUS_HEAD_CLASS,
} from "./runTable.styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RunBottomPanelProps {
  logs: LogResponse[];
  executionComplete: boolean;
  executionFailed: boolean;
  finalDuration: number;
  runId: string;
  workflowId: string;
  currentRunId: string;
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

type TabId = "logs" | "runs" | "regressions";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function RegressionCell({ runId, regressionCount }: { runId: string; regressionCount: number | null | undefined }) {
  const { data: regressionData } = useRunRegressions(regressionCount ? runId : "");

  if (!regressionCount) {
    return <span className="text-muted">—</span>;
  }

  const tooltip = regressionData?.issues?.length
    ? formatRegressionTooltip(regressionData.issues)
    : { header: `${regressionCount} ${regressionCount === 1 ? "regression" : "regressions"}`, lines: ["Regression detected"] };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger render={
          <span className="inline-flex items-center gap-1" style={{ color: "var(--warning-11)" }}>
            <AlertTriangle className="h-3.5 w-3.5" />
            {regressionCount}
          </span>
        } />
        <TooltipContent className="max-w-[320px] whitespace-normal px-3 py-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-9" />
            <div className="min-w-0 text-sm">
              <p className="mb-1 font-medium text-primary">{tooltip.header}</p>
              {tooltip.lines.map((line, index) => (
                <p key={`${runId}-${index}`} className="leading-5 text-secondary">{line}</p>
              ))}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunBottomPanel({
  logs,
  executionComplete,
  executionFailed,
  finalDuration,
  runId,
  workflowId,
  currentRunId,
}: RunBottomPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("logs");
  const [isExpanded, setIsExpanded] = useState(true);
  const navigate = useNavigate();

  const { data: runsData } = useRuns({ workflow_id: workflowId });
  const { data: regressions } = useRunRegressions(runId);

  const sortedRuns = useMemo(() => {
    const items = runsData?.items ?? [];
    return [...items].sort((a, b) => {
      const aTime = a.started_at ?? a.created_at ?? "";
      const bTime = b.started_at ?? b.created_at ?? "";
      return bTime > aTime ? 1 : bTime < aTime ? -1 : 0;
    });
  }, [runsData]);

  const regressionCount = regressions?.count ?? 0;
  const regressionIssues = regressions?.issues ?? [];

  const visibleTabs = useMemo(() => {
    return [
      { id: "logs", label: "Logs", icon: FileText },
      { id: "runs", label: "Runs", icon: List },
      { id: "regressions", label: "Regressions", icon: AlertTriangle },
    ] as { id: TabId; label: string; icon: typeof FileText }[];
  }, []);

  return (
    <div data-testid="bottom-panel" className={cn("bg-[var(--surface-secondary)] border-t border-[var(--border-default)] flex flex-col z-50", isExpanded ? "h-[200px]" : "h-[36px]")}>
      {/* Tab Bar */}
      <div role="tablist" aria-label="Bottom panel tabs" className="h-9 flex items-center px-4 border-b border-[var(--border-default)] justify-between shrink-0">
        <div className="flex items-center gap-1">
          {visibleTabs.map((tab) => (
            <button key={tab.id} role="tab" aria-selected={activeTab === tab.id} aria-controls={`bottom-panel-${tab.id}`} onClick={() => setActiveTab(tab.id)} className={cn("h-7 px-3 text-[12px] font-medium flex items-center gap-1.5 border-b-2 transition-colors", activeTab === tab.id ? "text-[var(--text-primary)] border-[var(--interactive-default)]" : "text-[var(--text-muted)] hover:text-[var(--text-primary)] border-transparent")}>
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
              {tab.id === "regressions" && regressionCount > 0 && (
                <Badge variant="warning" className="ml-1">{regressionCount}</Badge>
              )}
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

          {activeTab === "runs" && (
            <div className="flex-1 overflow-y-auto">
              {sortedRuns.length === 0 ? (
                <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">No runs found for this workflow.</div>
              ) : (
                <div className={RUN_TABLE_CONTAINER_CLASS}>
                  <Table className={RUN_TABLE_CLASS}>
                    <TableHeader>
                      <TableRow className={RUN_TABLE_HEADER_ROW_CLASS}>
                        <TableHead className={cn(RUN_TABLE_HEAD_CLASS, RUN_TABLE_STATUS_HEAD_CLASS)}>
                          Status
                        </TableHead>
                        <TableHead className={RUN_TABLE_HEAD_CLASS}>Run</TableHead>
                        <TableHead className={RUN_TABLE_HEAD_CLASS}>Commit</TableHead>
                        <TableHead className={RUN_TABLE_HEAD_CLASS}>Started</TableHead>
                        <TableHead className={RUN_TABLE_HEAD_CLASS}>Duration</TableHead>
                        <TableHead className={RUN_TABLE_HEAD_CLASS}>Regr</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedRuns.map((run) => (
                        <TableRow
                          key={run.id}
                          onClick={() => navigate(`/runs/${run.id}`)}
                          className={cn(
                            RUN_TABLE_ROW_CLASS,
                            run.id === currentRunId && "bg-[var(--surface-selected)]",
                          )}
                        >
                          <TableCell className={RUN_TABLE_STATUS_CELL_CLASS}>
                            <RunStatusDot status={run.status} className="w-full justify-center" />
                          </TableCell>
                          <TableCell data-type="data" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
                            {run.run_number != null ? `#${run.run_number}` : "—"}
                          </TableCell>
                          <TableCell data-type="id" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
                            {run.commit_sha ? run.commit_sha.slice(0, 7) : "—"}
                          </TableCell>
                          <TableCell data-type="timestamp" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
                            {run.started_at ? formatTimestamp(run.started_at) : "—"}
                          </TableCell>
                          <TableCell data-type="metric" className={cn(RUN_TABLE_CELL_CLASS, "text-secondary")}>
                            {run.duration_seconds ? formatDuration(run.duration_seconds) : "—"}
                          </TableCell>
                          <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>
                            <RegressionCell runId={run.id} regressionCount={run.regression_count} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          )}

          {activeTab === "regressions" && (
            <div className="flex-1 overflow-y-auto">
              {regressionIssues.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
                  No regressions detected for this run.
                </div>
              ) : (
                regressionIssues.map((regression, index) => (
                  <div key={index} className={cn("flex items-center gap-3 px-3 py-2 text-xs", index % 2 === 1 && "bg-surface-secondary")}>
                    <AlertTriangle className="w-3.5 h-3.5 text-[var(--warning-9)] shrink-0" />
                    <span className="text-[var(--text-primary)] w-[140px] shrink-0 truncate">{regression.node_name}</span>
                    <span className="text-[var(--text-muted)] w-[120px] shrink-0">{regression.type.replaceAll("_", " ")}</span>
                    <span className="text-[var(--text-primary)] flex-1">{regression.delta.cost_pct != null ? `+${Number(regression.delta.cost_pct).toFixed(0)}%` : regression.delta.score_delta != null ? `${Number(regression.delta.score_delta).toFixed(2)}` : "—"}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
