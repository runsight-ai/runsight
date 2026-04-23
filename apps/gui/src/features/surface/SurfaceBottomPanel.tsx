import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useCreateRun, useRunContextAudit, useRunContextAuditStream, useRunRegressions } from "@/queries/runs";
import { useWorkflow, useWorkflowRegressions } from "@/queries/workflows";
import { useCanvasStore } from "@/store/canvas";
import { gitApi } from "@/api/git";
import { useNavigate } from "react-router";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import { RegressionTooltipBody } from "@/components/shared/RegressionTooltipBody";
import { SurfaceRunsTable } from "./SurfaceRunsTable";
import { RunInputsModal } from "./RunInputsModal";
import type { RunResponse, WorkflowInputSchemaItem } from "@runsight/shared/zod";
import type { WorkflowRegression } from "@/types/schemas/regressions";
import { ContextAuditPanel } from "./contextAuditSurfaces";
import { resolveRunInputSchemaDecision } from "./runInputSchemaPolicy";
import { useSurfaceBottomPanelAudit } from "./useSurfaceBottomPanelAudit";
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

type RerunModalState = {
  source: "manual" | "simulation";
  branch: string;
  workflow: {
    id: string;
    name?: unknown;
    commit_sha?: unknown;
    branch?: string;
    input_schema?: unknown;
  };
  initialValues: Record<string, unknown>;
};

type AuditPanelWithQueryProps = {
  runId: string | undefined;
  selectedNodeId: string | null;
  fetchNextPage?: () => Promise<unknown>;
  hasNextPage?: boolean;
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
  const [rerunModalState, setRerunModalState] = useState<RerunModalState | null>(null);
  const navigate = useNavigate();
  const setActiveRunId = useCanvasStore((state) => state.setActiveRunId);
  const isDirty = useCanvasStore((state) => state.isDirty);
  const yamlContent = useCanvasStore((state) => state.yamlContent);
  const createRun = useCreateRun();
  const { data: workflow } = useWorkflow(workflowId ?? "");
  const { activeTab, isExpanded, openTab, toggleExpanded } = useSurfaceBottomPanelTabs({
    defaultState,
    onAuditOpen,
  });
  const { currentRunId, sortedRuns, selectRun } = useSurfaceBottomPanelRunSelection({
    initialRunId,
    workflowId,
  });
  const { entries } = useSurfaceBottomPanelLogs({ runId: currentRunId });
  const contextAuditQuery = useSurfaceBottomPanelAudit({
    runId: currentRunId,
    useRunContextAudit,
    useRunContextAuditStream,
  });

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

  async function openRerunModal(run: RunResponse) {
    if (!workflow) {
      return;
    }

    const shouldRunOnSimulation = isDirty || !workflow.commit_sha;
    let workflowInputSchema = workflow.input_schema;
    let source: "manual" | "simulation" = "manual";
    let branch = "main";
    let commitSha = workflow.commit_sha;

    if (shouldRunOnSimulation) {
      let decision;
      try {
        decision = await resolveRunInputSchemaDecision({
          workflow: {
            id: workflow.id,
            input_schema: workflow.input_schema,
          },
          isDirty: true,
          yamlContent,
          prepareSimulation: gitApi.createSimBranch,
        });
      } catch (error) {
        const description =
          error instanceof Error ? error.message : "Failed to prepare simulation snapshot.";
        toast.error("Unable to start run", { description });
        return;
      }

      if (decision.kind === "blocked") {
        toast.error("Unable to start run", { description: decision.error.message });
        return;
      }

      workflowInputSchema = decision.kind === "needs_inputs" ? decision.input_schema : null;
      source = decision.branch ? "simulation" : "manual";
      branch = decision.branch ?? "main";
      commitSha = decision.commit_sha ?? commitSha;
    }

    if (!hasWorkflowInputs(workflowInputSchema)) {
      void createRunRequest({}, { source, branch }).catch(() => undefined);
      return;
    }

    setRerunModalState({
      source,
      branch,
      workflow: {
        id: workflow.id,
        name: workflow.name,
        commit_sha: commitSha,
        branch,
        input_schema: workflowInputSchema,
      },
      initialValues: getRerunInitialValues(workflowInputSchema, run.workflow_inputs),
    });
  }

  function closeRerunModal(nextOpen: boolean) {
    if (!nextOpen) {
      setRerunModalState(null);
    }
  }

  function createRunRequest(
    inputs: Record<string, unknown>,
    options: { source: "manual" | "simulation"; branch: string } = {
      source: "manual",
      branch: "main",
    },
  ) {
    const workflowIdToUse = workflow?.id ?? workflowId;

    if (!workflowIdToUse) {
      return Promise.reject(new Error("Workflow is unavailable."));
    }

    return new Promise<void>((resolve, reject) => {
      createRun.mutate(
        {
          workflow_id: workflowIdToUse,
          inputs,
          source: options.source,
          branch: options.branch,
        },
        {
          onSuccess: (result) => {
            setActiveRunId(result.id);
            navigate(`/runs/${result.id}`);
            resolve();
          },
          onError: (error) => {
            reject(error);
          },
        },
      );
    });
  }

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
        <div
          data-testid="workflow-runs-panel"
          aria-hidden={rerunModalState ? true : undefined}
          className="overflow-auto flex-1"
        >
          <SurfaceRunsTable
            runs={sortedRuns}
            currentRunId={currentRunId}
            onRowClick={onRunSelect}
            onRerun={(run) => {
              void openRerunModal(run);
            }}
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
            fetchNextPage={contextAuditQuery.fetchNextPage}
            hasNextPage={contextAuditQuery.hasNextPage}
            onSelectNode={(nodeId) => {
              onAuditNodeSelect?.(nodeId, currentRunId);
            }}
          />
        </div>
      )}
      {rerunModalState ? (
        <RunInputsModal
          open
          workflow={rerunModalState.workflow}
          initialValues={rerunModalState.initialValues}
          submitLabel="Rerun"
          submitting={createRun.isPending}
          onOpenChange={closeRerunModal}
          onSubmit={async (inputs) => {
            await createRunRequest(inputs, {
              source: rerunModalState.source,
              branch: rerunModalState.branch,
            });
            setRerunModalState(null);
          }}
        />
      ) : null}
    </div>
  );
}

function SurfaceBottomPanelAuditController({
  runId,
  selectedNodeId,
  fetchNextPage,
  hasNextPage,
  onSelectNode,
}: AuditPanelWithQueryProps) {
  return (
    <ContextAuditPanel
      runId={runId}
      selectedNodeId={selectedNodeId}
      onSelectNode={(nodeId) => onSelectNode(nodeId, runId)}
      fetchNextPage={fetchNextPage}
      hasNextPage={hasNextPage}
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

type WorkflowInputSnapshotEntry = {
  sensitive?: boolean;
  value?: unknown;
};

function hasWorkflowInputs(
  inputSchema: unknown,
): inputSchema is Record<string, WorkflowInputSchemaItem> {
  return inputSchema !== null && typeof inputSchema === "object" && !Array.isArray(inputSchema) && Object.keys(inputSchema).length > 0;
}

function getRerunInitialValues(
  schema: Record<string, WorkflowInputSchemaItem>,
  workflowInputs: RunResponse["workflow_inputs"],
) {
  if (!workflowInputs || typeof workflowInputs !== "object" || Array.isArray(workflowInputs)) {
    return {};
  }

  const initialValues: Record<string, unknown> = {};
  for (const [name, item] of Object.entries(schema)) {
    if (item.sensitive === true) {
      continue;
    }

    const snapshotEntry = workflowInputs[name];
    if (!isWorkflowInputSnapshotEntry(snapshotEntry) || !Object.hasOwn(snapshotEntry, "value")) {
      continue;
    }

    if (snapshotEntry.sensitive !== false) {
      continue;
    }

    if (snapshotEntry.value !== undefined) {
      initialValues[name] = snapshotEntry.value;
    }
  }

  return initialValues;
}

function isWorkflowInputSnapshotEntry(value: unknown): value is WorkflowInputSnapshotEntry {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
