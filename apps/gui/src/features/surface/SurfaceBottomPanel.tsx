import { useEffect, useRef } from "react";
import { useRunContextAudit, useRunContextAuditStream, useRunRegressions } from "@/queries/runs";
import { useWorkflowRegressions } from "@/queries/workflows";
import { useNavigate } from "react-router";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import { RegressionTooltipBody } from "@/components/shared/RegressionTooltipBody";
import { SurfaceRunsTable } from "./SurfaceRunsTable";
import type { WorkflowRegression } from "@/types/schemas/regressions";
import { useContextAuditStore } from "@/store/contextAudit";
import { ContextAuditPanel } from "./contextAuditSurfaces";
import { useSurfaceBottomPanelLogs } from "./useSurfaceBottomPanelLogs";
import { useSurfaceBottomPanelRunSelection } from "./useSurfaceBottomPanelRunSelection";
import { useSurfaceBottomPanelTabs } from "./useSurfaceBottomPanelTabs";

interface SurfaceBottomPanelProps {
  runId?: string;
  workflowId?: string;
  defaultState?: "collapsed" | "expanded";
  executionSummary?: {
    tone: "success" | "danger";
    text: string;
  };
  selectedNodeId?: string | null;
  onAuditNodeSelect?: (nodeId: string, runId?: string) => void;
  onAuditOpen?: () => void;
}

type RegressionsData = {
  count?: number;
  issues?: WorkflowRegression[];
};

type SurfaceBottomPanelContentProps = SurfaceBottomPanelProps & {
  regressionsData?: RegressionsData;
};

type AuditPanelWithQueryProps = {
  runId: string | undefined;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string, runId?: string) => void;
};

function SurfaceBottomPanelContent({
  runId: initialRunId,
  workflowId,
  defaultState = "collapsed",
  executionSummary,
  regressionsData,
  selectedNodeId,
  onAuditNodeSelect,
  onAuditOpen,
}: SurfaceBottomPanelContentProps) {
  const logsRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { activeTab, isExpanded, openTab, toggleExpanded } = useSurfaceBottomPanelTabs({
    defaultState,
    onAuditOpen,
  });
  const { currentRunId, sortedRuns, selectRun } = useSurfaceBottomPanelRunSelection({
    initialRunId,
    workflowId,
  });
  const { entries } = useSurfaceBottomPanelLogs({ runId: currentRunId });

  const count = regressionsData?.count ?? 0;
  const regressionsItems = regressionsData?.issues ?? [];
  const regressionEmptyMessage = initialRunId
    ? "No regressions detected for this run."
    : "No regressions detected for this workflow.";

  // Auto-scroll when new entries arrive
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [entries.length]);

  const onRunSelect = (runId: string) => {
    selectRun(runId);
    openTab("logs");
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
          onClick={() => openTab("logs")}
          className={`font-mono text-2xs uppercase bg-transparent border-none cursor-pointer py-1 tracking-wide ${activeTab === "logs" ? "text-heading" : "text-muted hover:text-primary"}`}
        >
          Logs
        </button>
        <button
          data-testid="workflow-runs-tab"
          role="tab"
          aria-label="Expand runs panel"
          aria-selected={activeTab === "runs"}
          onClick={() => openTab("runs")}
          className={`font-mono text-2xs uppercase bg-transparent border-none cursor-pointer py-1 tracking-wide ${activeTab === "runs" ? "text-heading" : "text-muted hover:text-primary"}`}
        >
          Runs
        </button>
        <button
          data-testid="workflow-regressions-tab"
          role="tab"
          aria-label="Expand regressions panel"
          aria-selected={activeTab === "regressions"}
          onClick={() => openTab("regressions")}
          className={`font-mono text-2xs uppercase bg-transparent border-none cursor-pointer py-1 tracking-wide ${activeTab === "regressions" ? "text-heading" : "text-muted hover:text-primary"}`}
        >
          Regressions{count > 0 ? ` (${count})` : ""}
        </button>
        <button
          data-testid="workflow-audit-tab"
          role="tab"
          aria-label="Expand audit panel"
          aria-selected={activeTab === "audit"}
          onClick={() => openTab("audit")}
          className={`font-mono text-2xs uppercase bg-transparent border-none cursor-pointer py-1 tracking-wide ${activeTab === "audit" ? "text-heading" : "text-muted hover:text-primary"}`}
        >
          Audit
        </button>
        <button
          type="button"
          aria-label={isExpanded ? "Collapse panel" : "Expand panel"}
          data-testid="workflow-bottom-panel-toggle"
          onClick={toggleExpanded}
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
      {isExpanded && activeTab === "audit" && (
        <div data-testid="workflow-audit-panel" className="overflow-hidden flex-1">
          <SurfaceBottomPanelAuditController
            runId={currentRunId}
            selectedNodeId={selectedNodeId ?? null}
            onSelectNode={(nodeId) => {
              onAuditNodeSelect?.(nodeId, currentRunId);
            }}
          />
        </div>
      )}
    </div>
  );
}

function SurfaceBottomPanelAuditController({
  runId,
  selectedNodeId,
  onSelectNode,
}: AuditPanelWithQueryProps) {
  const replaceContextAuditEvents = useContextAuditStore((state) => state.replaceRunEvents);
  const contextAuditQuery = useRunContextAudit(runId ?? "", { page_size: 100 });
  useRunContextAuditStream(runId);

  useEffect(() => {
    if (!runId) {
      return;
    }
    const currentEvents = useContextAuditStore.getState().eventsByRun[runId] ?? [];
    replaceContextAuditEvents(runId, currentEvents);
  }, [replaceContextAuditEvents, runId]);

  return (
    <ContextAuditPanel
      runId={runId}
      selectedNodeId={selectedNodeId}
      onSelectNode={(nodeId) => onSelectNode(nodeId, runId)}
      fetchNextPage={contextAuditQuery.fetchNextPage}
      hasNextPage={contextAuditQuery.hasNextPage}
    />
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
