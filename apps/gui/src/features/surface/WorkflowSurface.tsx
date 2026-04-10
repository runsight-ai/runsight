import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import type { WorkflowSurfaceProps, WorkflowSurfaceMode } from "./surfaceContract";
import { getContractForMode, getCanvasYamlToggleVisibility, getSaveButtonState, getActionButton, isEditable } from "./surfaceContract";
import { SurfaceTopbar } from "./SurfaceTopbar";
import { SurfaceYamlEditor } from "./SurfaceYamlEditor";
import { SurfaceBottomPanel } from "./SurfaceBottomPanel";
import { SurfaceStatusBar } from "./SurfaceStatusBar";
import { SurfaceCanvas } from "./SurfaceCanvas";
import { useSurfaceHeaderSlots } from "./useSurfaceHeaderSlots";
import { SurfaceShell } from "./SurfaceShell";

import { ProviderModal } from "@/components/provider/ProviderModal";
import { CommitDialog } from "@/features/git/CommitDialog";
import { EmptyState } from "@runsight/ui/empty-state";
import { Card } from "@runsight/ui/card";
import { Button } from "@runsight/ui/button";
import { LayoutGrid } from "lucide-react";
import { useCanvasStore } from "@/store/canvas";
import * as runQueries from "@/queries/runs";
import { useWorkflow } from "@/queries/workflows";
import { gitApi } from "@/api/git";
import { PriorityBanner } from "@/components/shared";
import { mapRunStatus } from "./surfaceUtils";
import { SurfaceInspectorPanel } from "./SurfaceInspectorPanel";

const useOptionalRunRegressions =
  "useRunRegressions" in runQueries
    ? (
        runQueries as {
          useRunRegressions: (runId: string) => { data?: { count?: number } };
        }
      ).useRunRegressions
    : (_runId: string) => ({ data: undefined });

function RunGraphErrorCard({
  message,
  onRetry,
}: {
  message?: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <Card className="w-full max-w-xl px-6 py-6">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-heading">Unable to load run graph</h2>
          <p className="text-sm leading-6 text-secondary">
            Runsight could not read the node response for this run. Retry to fetch the
            graph again.
          </p>
          {message ? <p className="text-sm text-secondary">{message}</p> : null}
          <div className="pt-2">
            <Button variant="primary" onClick={onRetry}>
              Retry
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

function RunPreExecutionFailureCard({ error }: { error: string }) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <Card className="w-full max-w-xl px-6 py-6">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-heading">Run failed before execution started</h2>
          <p className="text-sm leading-6 text-secondary">
            Runsight could not prepare this workflow for execution, so no nodes were started.
          </p>
          <div className="rounded-md border border-[var(--danger-9)]/30 bg-danger-3 p-3 font-mono text-xs leading-relaxed text-[var(--danger-9)]">
            {error}
          </div>
        </div>
      </Card>
    </div>
  );
}

function getOverlayRefFromLocation(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const overlayRef = new URLSearchParams(window.location.search).get("overlayRef");
  return overlayRef && overlayRef.trim().length > 0 ? overlayRef : null;
}

export function WorkflowSurface({ mode: initialMode, workflowId: initialWorkflowId = "", runId: initialRunId }: WorkflowSurfaceProps) {
  const [mode, setMode] = useState<WorkflowSurfaceMode>(initialMode);
  const [workflowId, setWorkflowId] = useState(initialWorkflowId);
  const [activeRunId, setRunId] = useState(initialRunId);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [overlayYaml, setOverlayYaml] = useState<string | null>(null);
  const [isOverlayLoading, setIsOverlayLoading] = useState(false);
  const [readonlyYaml, setReadonlyYaml] = useState<string | null>(null);
  const [isReadonlyYamlLoading, setIsReadonlyYamlLoading] = useState(false);
  const [inspectedNodeId, setInspectedNodeId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const overlayRef = getOverlayRefFromLocation();
  const readonlyRunId = mode === "readonly" ? (activeRunId ?? initialRunId ?? "") : "";

  const handleForkTransition = useCallback((newWorkflowId: string) => {
    window.history.replaceState(null, "", `/workflows/${newWorkflowId}/edit`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, []);
  const handleReadonlyForkTransition = useCallback((newWorkflowId: string) => {
    if (typeof globalThis.setTimeout === "function") {
      globalThis.setTimeout(() => handleForkTransition(newWorkflowId), 0);
      return;
    }

    handleForkTransition(newWorkflowId);
  }, [handleForkTransition]);

  const contract = getContractForMode(mode);

  const { topbar, bottomPanel, statusBar, inspector, inspectorVisible } = contract;

  const nameEditable = topbar.nameEditable;
  const defaultState = bottomPanel.defaultState;
  const stepCountFormat = statusBar.stepCountFormat;
  const metricsVisibility = statusBar.metricsVisibility;
  const toggleVisibility = getCanvasYamlToggleVisibility(mode);
  const editable = isEditable(mode);

  const [activeTab, setActiveTab] = useState<"canvas" | "yaml">("yaml");
  const [isDirty, setIsDirty] = useState(false);
  const [commitDialogOpen, setCommitDialogOpen] = useState(false);
  const {
    data: run,
    isLoading: isRunLoading,
    isError: isRunError,
  } = runQueries.useRun(readonlyRunId, {
    refetchInterval: (query) => {
      const status = (query?.state as { data?: { status?: string } })?.data?.status;
      if (status === "running" || status === "pending") return 2000;
      return false;
    },
  });
  const resolvedWorkflowId =
    mode === "readonly" ? (run?.workflow_id ?? workflowId) : workflowId;
  const {
    data: workflow,
    isError,
    isLoading: isWorkflowLoading,
  } = useWorkflow(resolvedWorkflowId);
  const {
    data: runNodes,
    isError: isRunNodesError,
    error: runNodesError,
    refetch: refetchRunNodes,
  } = runQueries.useRunNodes(readonlyRunId);
  const { data: regressions } = useOptionalRunRegressions(readonlyRunId);

  const nodes = useCanvasStore((s) => s.nodes);
  const edges = useCanvasStore((s) => s.edges);
  const blockCount = useCanvasStore((s) => s.blockCount);
  const edgeCount = useCanvasStore((s) => s.edgeCount);
  const setYamlContent = useCanvasStore((s) => s.setYamlContent);
  const hydrateFromPersisted = useCanvasStore((s) => s.hydrateFromPersisted);
  const setNodeStatus = useCanvasStore((s) => s.setNodeStatus);
  const setActiveCanvasRunId = useCanvasStore((s) => s.setActiveRunId);
  const setRunCost = useCanvasStore((s) => s.setRunCost);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const resetCanvas = useCanvasStore((s) => (s as { reset?: () => void }).reset);

  const handleOpenApiKeyModal = useCallback(() => {
    setApiKeyModalOpen(true);
  }, []);

  const handleApiKeyModalOpenChange = useCallback((open: boolean) => {
    setApiKeyModalOpen(open);
  }, []);

  const handleProviderSaveSuccess = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["providers"] });
    setApiKeyModalOpen(false);
  }, [queryClient]);

  // Force canvas tab when yaml is unavailable (execution/historical modes)
  useEffect(() => {
    if (!toggleVisibility.yaml) {
      setActiveTab("canvas");
    }
  }, [toggleVisibility.yaml]);

  useEffect(() => {
    setMode(initialMode);
    setWorkflowId(initialWorkflowId);
    setRunId(initialRunId);
    setInspectedNodeId(null);
    setOverlayYaml(null);
    setReadonlyYaml(null);
    resetCanvas?.();
  }, [initialMode, initialWorkflowId, initialRunId, resetCanvas]);

  useEffect(() => {
    if (mode !== "readonly" || !run?.workflow_id || workflowId === run.workflow_id) {
      return;
    }
    setWorkflowId(run.workflow_id);
  }, [mode, run?.workflow_id, workflowId]);

  useEffect(() => {
    let cancelled = false;

    if (!workflowId || !overlayRef) {
      setOverlayYaml(null);
      setIsOverlayLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setIsOverlayLoading(true);
    gitApi
      .getGitFile(overlayRef, `custom/workflows/${workflowId}.yaml`)
      .then(({ content }) => {
        if (cancelled) return;
        setOverlayYaml(content);
      })
      .catch(() => {
        if (cancelled) return;
        setOverlayYaml(null);
      })
      .finally(() => {
        if (cancelled) return;
        setIsOverlayLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [overlayRef, workflowId]);

  useEffect(() => {
    if (!resolvedWorkflowId || !workflow?.yaml) {
      return;
    }

    if (mode !== "readonly" && overlayRef && overlayYaml !== null) {
      setYamlContent(overlayYaml);
      return;
    }

    setYamlContent(workflow.yaml);

    if (workflow.canvas_state && nodes.length === 0 && edges.length === 0) {
      hydrateFromPersisted({
        nodes: workflow.canvas_state.nodes ?? [],
        edges: workflow.canvas_state.edges ?? [],
        viewport: workflow.canvas_state.viewport ?? { x: 0, y: 0, zoom: 1 },
        selected_node_id: workflow.canvas_state.selected_node_id ?? null,
        canvas_mode:
          workflow.canvas_state.canvas_mode === "state-machine" ? "state-machine" : "dag",
      });
    }
  }, [
    edges.length,
    hydrateFromPersisted,
    nodes.length,
    setYamlContent,
    workflow?.canvas_state,
    workflow?.yaml,
    resolvedWorkflowId,
    mode,
    overlayRef,
    overlayYaml,
  ]);

  useEffect(() => {
    if (mode !== "readonly" || !run?.workflow_id || !run?.commit_sha) {
      setReadonlyYaml(null);
      setIsReadonlyYamlLoading(false);
      return;
    }

    let cancelled = false;
    setIsReadonlyYamlLoading(true);
    gitApi.getGitFile(run.commit_sha, `custom/workflows/${run.workflow_id}.yaml`)
      .then(({ content }) => {
        if (cancelled) return;
        setReadonlyYaml(content);
      })
      .catch(() => {
        if (cancelled) return;
        setReadonlyYaml(null);
      })
      .finally(() => {
        if (cancelled) return;
        setIsReadonlyYamlLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mode, run?.commit_sha, run?.workflow_id]);

  useEffect(() => {
    if (mode !== "readonly" || !run) {
      setActiveCanvasRunId(null);
      return;
    }

    setRunCost(run.total_cost_usd ?? 0);
    if (run.status === "running" || run.status === "pending") {
      setActiveCanvasRunId(run.id);
      return;
    }
    setActiveCanvasRunId(null);
  }, [mode, run, setActiveCanvasRunId, setRunCost]);

  useEffect(() => {
    if (mode !== "readonly" || !workflow?.canvas_state || !runNodes?.length) {
      return;
    }

    for (const runNode of runNodes) {
      setNodeStatus(runNode.node_id, mapRunStatus(runNode.status), {
        executionCost:
          typeof runNode.cost_usd === "number" ? runNode.cost_usd : undefined,
        duration:
          typeof runNode.duration_seconds === "number" ? runNode.duration_seconds : undefined,
        tokens:
          runNode.tokens && typeof runNode.tokens === "object"
            ? (runNode.tokens as { input?: number; output?: number; total?: number })
            : undefined,
        error:
          typeof runNode.error === "string" || runNode.error === null
            ? runNode.error
            : undefined,
      });
    }
  }, [mode, workflow?.canvas_state, runNodes, setNodeStatus]);

  const selectedNode = inspectedNodeId
    ? (nodes.find((node) => node.id === inspectedNodeId) ?? null)
    : null;
  const showRunGraphError =
    mode === "readonly" && activeTab === "canvas" && Boolean(isRunNodesError);
  const showPreExecutionFailure =
    mode === "readonly"
    && activeTab === "canvas"
    && !showRunGraphError
    && (runNodes?.length ?? 0) === 0
    && typeof run?.error === "string"
    && run.error.length > 0;
  const showReadonlyCanvas =
    mode === "readonly"
    && Boolean(workflow?.canvas_state)
    && !showRunGraphError
    && !showPreExecutionFailure;
  const headerSlots = useSurfaceHeaderSlots({
    mode,
    run,
    workflowId: resolvedWorkflowId,
    onForkTransition: handleReadonlyForkTransition,
  });
  const regressionCount = mode === "readonly" ? (regressions?.count ?? 0) : 0;
  const executionSummary =
    mode === "readonly" && run?.status === "completed"
      ? {
          tone: "success" as const,
          text: `Run completed in ${run.duration_seconds ?? 0}s`,
        }
      : mode === "readonly" && (run?.status === "failed" || run?.status === "error")
        ? {
            tone: "danger" as const,
            text: "Run failed",
          }
        : undefined;

  const handleSave = useCallback(() => {
    if (!editable || !workflowId) return;
    setCommitDialogOpen(true);
  }, [editable, workflowId]);

  const handleCommitSuccess = useCallback(() => {
    setIsDirty(false);
    setCommitDialogOpen(false);
  }, []);

  const saveButtonState = getSaveButtonState(mode, isDirty);
  const actionButton = mode === "edit" ? undefined : getActionButton(mode);

  const canvasStoreState = useCanvasStore.getState();
  const currentDraft = {
    yaml: canvasStoreState.yamlContent,
  };
  const currentFiles: { path: string; status: string }[] = [
    { path: `custom/workflows/${resolvedWorkflowId}.yaml`, status: "modified" },
  ];

  if (mode === "readonly" && (isRunLoading || (!!resolvedWorkflowId && isWorkflowLoading))) {
    return (
      <div className="flex h-full items-center justify-center text-muted">
        Loading run details...
      </div>
    );
  }

  if (mode === "readonly" && (isRunError || (!isRunLoading && !run))) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <p className="text-lg font-medium">Run not found</p>
        <Link to="/runs" className="text-sm underline">
          Back to runs
        </Link>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <p className="text-lg font-medium">Workflow not found</p>
        <Link to="/flows" className="text-sm underline">
          Back to workflows
        </Link>
      </div>
    );
  }

  const topbarNode = (
    <SurfaceTopbar
      workflowId={resolvedWorkflowId}
      runId={activeRunId ?? initialRunId}
      activeTab={activeTab}
      onValueChange={(v) => setActiveTab(v as "canvas" | "yaml")}
      isDirty={isDirty}
      onSave={handleSave}
      nameEditable={nameEditable}
      toggleVisibility={toggleVisibility}
      saveButton={saveButtonState}
      metricsVisible={topbar.metricsVisible}
      metricsStyle={topbar.metricsStyle}
      actionButton={actionButton}
      onAddApiKey={editable ? handleOpenApiKeyModal : undefined}
      onForkTransition={mode === "readonly" ? handleReadonlyForkTransition : handleForkTransition}
      titleAfter={headerSlots.titleAfter}
      metricsOverride={headerSlots.metricsOverride}
      actionsOverride={headerSlots.actionsOverride}
      forkConfigOverride={
        mode === "readonly"
          ? {
              commitSha: run?.commit_sha ?? "",
              workflowPath: `custom/workflows/${resolvedWorkflowId}.yaml`,
              workflowName: run?.workflow_name ?? workflow?.name ?? "Untitled Workflow",
            }
          : undefined
      }
    />
  );

  const centerNode = (
    <>
      {mode === "readonly" ? (
        <PriorityBanner
          conditions={[{
            type: "regressions",
            active: regressionCount > 0,
            message: `${regressionCount} regressions found`,
          }]}
        />
      ) : null}
      {activeTab === "canvas" ? (
        <div className="flex h-full min-h-0">
          <div className="flex-1 min-w-0">
            {showRunGraphError ? (
              <RunGraphErrorCard
                message={runNodesError instanceof Error ? runNodesError.message : undefined}
                onRetry={() => void refetchRunNodes()}
              />
            ) : showPreExecutionFailure ? (
              <RunPreExecutionFailureCard error={run.error as string} />
            ) : showReadonlyCanvas ? (
              <SurfaceCanvas
                isDraggable={false}
                connectionsAllowed={false}
                deletionAllowed={false}
                runId={readonlyRunId}
                onNodeClick={setInspectedNodeId}
                onPaneClick={() => setInspectedNodeId(null)}
              />
            ) : mode === "readonly" ? (
              <div className="flex h-full items-center justify-center">
                <EmptyState
                  icon={LayoutGrid}
                  title="Canvas layout unavailable"
                  description="Canvas layout unavailable for this run. Switch to the YAML tab to inspect the workflow definition."
                />
              </div>
            ) : (
              <SurfaceCanvas
                isDraggable={contract.canvas.draggable}
                connectionsAllowed={contract.canvas.connectionsAllowed}
                deletionAllowed={contract.canvas.deletionAllowed}
              />
            )}
          </div>
          {inspectorVisible && selectedNode ? (
            <SurfaceInspectorPanel
              selectedNode={selectedNode}
              onClose={() => {
                setInspectedNodeId(null);
                selectNode(null);
              }}
              trigger={inspector.trigger}
            />
          ) : null}
        </div>
      ) : activeTab === "yaml" ? (
        (mode === "readonly" && isReadonlyYamlLoading) || isOverlayLoading ? (
          <div className="flex h-full items-center justify-center text-muted">
            {mode === "readonly" ? "Loading run details..." : "Loading workflow snapshot..."}
          </div>
        ) : (
          <SurfaceYamlEditor
            workflowId={resolvedWorkflowId}
            yaml={mode === "readonly" ? (readonlyYaml ?? undefined) : (overlayYaml ?? undefined)}
            readOnly={!editable}
            onDirtyChange={(dirty: boolean) => setIsDirty(dirty)}
          />
        )
      ) : null}
    </>
  );

  const bottomPanelNode = (
    <SurfaceBottomPanel
      runId={activeRunId ?? initialRunId}
      workflowId={resolvedWorkflowId}
      defaultState={defaultState}
      executionSummary={executionSummary}
    />
  );

  const statusBarNode = (
    <SurfaceStatusBar
      activeTab={activeTab}
      blockCount={blockCount}
      edgeCount={edgeCount}
      stepCountFormat={stepCountFormat}
      metricsVisibility={metricsVisibility}
    />
  );

  return (
    <>
      <SurfaceShell
        topbar={topbarNode}
        center={centerNode}
        bottomPanel={bottomPanelNode}
        statusBar={statusBarNode}
      />
      <ProviderModal
        mode="canvas"
        open={apiKeyModalOpen}
        onOpenChange={handleApiKeyModalOpenChange}
        onSaveSuccess={handleProviderSaveSuccess}
      />

      <CommitDialog
        open={commitDialogOpen}
        onOpenChange={setCommitDialogOpen}
        files={currentFiles}
        workflowId={resolvedWorkflowId}
        draft={currentDraft}
        onCommitSuccess={handleCommitSuccess}
      />
    </>
  );
}
