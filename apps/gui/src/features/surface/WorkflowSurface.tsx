import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import type { Node } from "@xyflow/react";
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
import type { StepNodeData } from "@/types/schemas/canvas";
import { useRun, useRunNodes, useRunRegressions } from "@/queries/runs";
import { useWorkflow } from "@/queries/workflows";
import { PriorityBanner } from "@/components/shared";
import { SurfaceInspectorPanel } from "./SurfaceInspectorPanel";
import { useOverlayYaml } from "./useOverlayYaml";
import { useReadonlyRunYaml } from "./useReadonlyRunYaml";
import { useCanvasHydration } from "./useCanvasHydration";
import { useRunStatusSync } from "./useRunStatusSync";
import { useNodeStatusMapping } from "./useNodeStatusMapping";
import { useSurfaceTabState } from "./useSurfaceTabState";

type RuntimeStepNodeData = StepNodeData & {
  model?: string;
  duration?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
};

function RunGraphErrorCard({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <Card className="w-full max-w-xl px-6 py-6">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-heading">Unable to load run graph</h2>
          <p className="text-sm leading-6 text-secondary">Runsight could not read the node response for this run. Retry to fetch the graph again.</p>
          {message ? <p className="text-sm text-secondary">{message}</p> : null}
          <div className="pt-2"><Button variant="primary" onClick={onRetry}>Retry</Button></div>
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
          <p className="text-sm leading-6 text-secondary">Runsight could not prepare this workflow for execution, so no nodes were started.</p>
          <div className="rounded-md border border-[var(--danger-9)]/30 bg-danger-3 p-3 font-mono text-xs leading-relaxed text-[var(--danger-9)]">{error}</div>
        </div>
      </Card>
    </div>
  );
}

function getOverlayRefFromLocation(): string | null {
  if (typeof window === "undefined") return null;
  const ref = new URLSearchParams(window.location.search).get("overlayRef");
  return ref && ref.trim().length > 0 ? ref : null;
}

type CenterProps = {
  mode: WorkflowSurfaceMode;
  activeTab: "canvas" | "yaml";
  contract: ReturnType<typeof getContractForMode>;
  readonlyRunId: string;
  regressionCount: number;
  showRunGraphError: boolean;
  showPreExecutionFailure: boolean;
  showReadonlyCanvas: boolean;
  runNodesError: unknown;
  runError?: string;
  refetchRunNodes: () => void;
  inspectorVisible: boolean;
  selectedNode: Node<RuntimeStepNodeData> | null;
  onNodeClick: (id: string) => void;
  onPaneClick: () => void;
  onInspectorClose: () => void;
  inspectorTrigger: "double-click" | "single-click";
  isReadonlyYamlLoading: boolean;
  isOverlayLoading: boolean;
  readonlyYaml: string | null;
  overlayYaml: string | null;
  resolvedWorkflowId: string;
  editable: boolean;
  onDirtyChange: (dirty: boolean) => void;
  inspectorTab: "execution" | "overview" | "context";
};

function SurfaceCenter(p: CenterProps) {
  return (
    <>
      {p.mode === "readonly" ? (
        <PriorityBanner conditions={[{ type: "regressions", active: p.regressionCount > 0, message: `${p.regressionCount} regressions found` }]} />
      ) : null}
      {p.activeTab === "canvas" ? (
        <div className="flex h-full min-h-0">
          <div className="flex-1 min-w-0">
            {p.showRunGraphError ? (
              <RunGraphErrorCard message={p.runNodesError instanceof Error ? p.runNodesError.message : undefined} onRetry={p.refetchRunNodes} />
            ) : p.showPreExecutionFailure ? (
              <RunPreExecutionFailureCard error={p.runError as string} />
            ) : p.showReadonlyCanvas ? (
              <SurfaceCanvas isDraggable={false} connectionsAllowed={false} deletionAllowed={false} runId={p.readonlyRunId} onNodeClick={p.onNodeClick} onPaneClick={p.onPaneClick} />
            ) : p.mode === "readonly" ? (
              <div className="flex h-full items-center justify-center">
                <EmptyState icon={LayoutGrid} title="Canvas layout unavailable" description="Canvas layout unavailable for this run. Switch to the YAML tab to inspect the workflow definition." />
              </div>
            ) : (
              <SurfaceCanvas isDraggable={p.contract.canvas.draggable} connectionsAllowed={p.contract.canvas.connectionsAllowed} deletionAllowed={p.contract.canvas.deletionAllowed} runId={p.readonlyRunId} />
            )}
          </div>
          {p.inspectorVisible && p.selectedNode ? (
            <SurfaceInspectorPanel selectedNode={p.selectedNode} onClose={p.onInspectorClose} trigger={p.inspectorTrigger} runId={p.readonlyRunId} initialTab={p.inspectorTab} />
          ) : null}
        </div>
      ) : p.activeTab === "yaml" ? (
        (p.mode === "readonly" && p.isReadonlyYamlLoading) || p.isOverlayLoading ? (
          <div className="flex h-full items-center justify-center text-muted">{p.mode === "readonly" ? "Loading run details..." : "Loading workflow snapshot..."}</div>
        ) : (
          <SurfaceYamlEditor workflowId={p.resolvedWorkflowId} yaml={p.mode === "readonly" ? (p.readonlyYaml ?? undefined) : (p.overlayYaml ?? undefined)} readOnly={!p.editable} onDirtyChange={p.onDirtyChange} />
        )
      ) : null}
    </>
  );
}

export function WorkflowSurface({ mode: initialMode, workflowId: initialWorkflowId = "", runId: initialRunId }: WorkflowSurfaceProps) {
  const [mode, setMode] = useState<WorkflowSurfaceMode>(initialMode);
  const [workflowId, setWorkflowId] = useState(initialWorkflowId);
  const [activeRunId, setRunId] = useState(initialRunId);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [commitDialogOpen, setCommitDialogOpen] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<"execution" | "overview" | "context">("execution");

  const queryClient = useQueryClient();
  const overlayRef = getOverlayRefFromLocation();
  const readonlyRunId = mode === "readonly" ? (activeRunId ?? initialRunId ?? "") : "";
  const contract = getContractForMode(mode);
  const toggleVisibility = getCanvasYamlToggleVisibility(mode);
  const editable = isEditable(mode);

  const { data: run, isLoading: isRunLoading, isError: isRunError } = useRun(readonlyRunId, {
    refetchInterval: (q) => { const s = (q?.state as { data?: { status?: string } })?.data?.status; return s === "running" || s === "pending" ? 2000 : false; },
  });
  const resolvedWorkflowId = mode === "readonly" ? (run?.workflow_id ?? workflowId) : workflowId;
  const { data: workflow, isError, isLoading: isWorkflowLoading } = useWorkflow(resolvedWorkflowId);
  const { data: runNodes, isError: isRunNodesError, error: runNodesError, refetch: refetchRunNodes } = useRunNodes(readonlyRunId);
  const { data: regressions } = useRunRegressions(readonlyRunId);

  const nodes = useCanvasStore((s) => s.nodes);
  const blockCount = useCanvasStore((s) => s.blockCount);
  const edgeCount = useCanvasStore((s) => s.edgeCount);
  const setYamlContent = useCanvasStore((s) => s.setYamlContent);
  const hydrateFromPersisted = useCanvasStore((s) => s.hydrateFromPersisted);
  const setNodeStatus = useCanvasStore((s) => s.setNodeStatus);
  const setActiveCanvasRunId = useCanvasStore((s) => s.setActiveRunId);
  const setRunCost = useCanvasStore((s) => s.setRunCost);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const resetCanvas = useCanvasStore((s) => (s as { reset?: () => void }).reset);
  const toPersistedState = useCanvasStore((s) => s.toPersistedState);

  const { activeTab, setActiveTab, isDirty, setIsDirty, inspectedNodeId, setInspectedNodeId } = useSurfaceTabState(toggleVisibility.yaml ?? false);

  // Reset canvas on prop changes — must be registered before data-overlay hooks so
  // hydration and run-status effects run AFTER the reset on initial mount.
  useEffect(() => {
    setMode(initialMode); setWorkflowId(initialWorkflowId); setRunId(initialRunId); setInspectedNodeId(null); setInspectorTab("execution"); resetCanvas?.();
  }, [initialMode, initialWorkflowId, initialRunId, resetCanvas, setInspectedNodeId]);

  useEffect(() => {
    if (mode !== "readonly" || !run?.workflow_id || workflowId === run.workflow_id) return;
    setWorkflowId(run.workflow_id);
  }, [mode, run?.workflow_id, workflowId]);

  const { overlayYaml, isOverlayLoading } = useOverlayYaml(workflowId, overlayRef);
  const { readonlyYaml, isReadonlyYamlLoading } = useReadonlyRunYaml(mode, run);
  const { canvasHydrationRevision } = useCanvasHydration({ mode, resolvedWorkflowId, activeRunId, initialRunId, overlayRef, overlayYaml, readonlyYaml, workflow, setYamlContent, hydrateFromPersisted });
  useRunStatusSync({ mode, run, setActiveCanvasRunId, setRunCost });
  useNodeStatusMapping({ mode, nodesLength: nodes.length, runNodes, canvasHydrationRevision, setNodeStatus });

  const handleForkTransition = useCallback((id: string) => { window.history.replaceState(null, "", `/workflows/${id}/edit`); window.dispatchEvent(new PopStateEvent("popstate")); }, []);
  const handleReadonlyForkTransition = useCallback((id: string) => { if (typeof globalThis.setTimeout === "function") { globalThis.setTimeout(() => handleForkTransition(id), 0); return; } handleForkTransition(id); }, [handleForkTransition]);
  const handleProviderSaveSuccess = useCallback(async () => { await queryClient.invalidateQueries({ queryKey: ["providers"] }); setApiKeyModalOpen(false); }, [queryClient]);
  const handleSave = useCallback(() => { if (!editable || !workflowId) return; setCommitDialogOpen(true); }, [editable, workflowId]);
  const handleCommitSuccess = useCallback(() => { setIsDirty(false); setCommitDialogOpen(false); }, [setIsDirty]);

  const selectedNode = inspectedNodeId ? ((nodes.find((n) => n.id === inspectedNodeId) as Node<RuntimeStepNodeData> | undefined) ?? null) : null;
  const showRunGraphError = mode === "readonly" && activeTab === "canvas" && Boolean(isRunNodesError);
  const showPreExecutionFailure = mode === "readonly" && activeTab === "canvas" && !showRunGraphError && (runNodes?.length ?? 0) === 0 && typeof run?.error === "string" && run.error.length > 0;
  const showReadonlyCanvas = mode === "readonly" && nodes.length > 0 && !showRunGraphError && !showPreExecutionFailure;
  const headerSlots = useSurfaceHeaderSlots({ mode, run, workflowId: resolvedWorkflowId, onForkTransition: handleReadonlyForkTransition });
  const regressionCount = mode === "readonly" ? (regressions?.count ?? 0) : 0;
  const executionSummary = mode === "readonly" && run?.status === "completed" ? { tone: "success" as const, text: `Run completed in ${run.duration_seconds ?? 0}s` } : mode === "readonly" && (run?.status === "failed" || run?.status === "error") ? { tone: "danger" as const, text: "Run failed" } : undefined;
  const canvasStoreState = useCanvasStore.getState();
  const draftCanvasState = editable ? toPersistedState() : undefined;
  const currentDraft = { yaml: canvasStoreState.yamlContent, canvas_state: draftCanvasState ? (draftCanvasState as unknown as Record<string, unknown>) : undefined };
  const currentFiles = [{ path: `custom/workflows/${resolvedWorkflowId}.yaml`, status: "modified" }, ...(editable ? [{ path: `custom/workflows/.canvas/${resolvedWorkflowId}.canvas.json`, status: "modified" }] : [])];

  if (mode === "readonly" && (isRunLoading || (!!resolvedWorkflowId && isWorkflowLoading))) return <div className="flex h-full items-center justify-center text-muted">Loading run details...</div>;
  if (mode === "readonly" && (isRunError || (!isRunLoading && !run))) return <div className="flex h-full flex-col items-center justify-center gap-4"><p className="text-lg font-medium">Run not found</p><Link to="/runs" className="text-sm underline">Back to runs</Link></div>;
  if (isError) return <div className="flex h-full flex-col items-center justify-center gap-4"><p className="text-lg font-medium">Workflow not found</p><Link to="/flows" className="text-sm underline">Back to workflows</Link></div>;

  return (
    <>
      <SurfaceShell
        topbar={<SurfaceTopbar workflowId={resolvedWorkflowId} runId={activeRunId ?? initialRunId} activeTab={activeTab} onValueChange={(v) => setActiveTab(v as "canvas" | "yaml")} isDirty={isDirty} onSave={handleSave} nameEditable={contract.topbar.nameEditable} toggleVisibility={toggleVisibility} saveButton={getSaveButtonState(mode, isDirty)} metricsVisible={contract.topbar.metricsVisible} metricsStyle={contract.topbar.metricsStyle} actionButton={mode === "edit" ? undefined : getActionButton(mode)} onAddApiKey={editable ? () => setApiKeyModalOpen(true) : undefined} onForkTransition={mode === "readonly" ? handleReadonlyForkTransition : handleForkTransition} titleAfter={headerSlots.titleAfter} metricsOverride={headerSlots.metricsOverride} actionsOverride={headerSlots.actionsOverride} forkConfigOverride={mode === "readonly" ? { commitSha: run?.commit_sha ?? "", workflowPath: `custom/workflows/${resolvedWorkflowId}.yaml`, workflowName: run?.workflow_name ?? workflow?.name ?? "Untitled Workflow" } : undefined} />}
        center={<SurfaceCenter mode={mode} activeTab={activeTab} contract={contract} readonlyRunId={readonlyRunId} regressionCount={regressionCount} showRunGraphError={showRunGraphError} showPreExecutionFailure={showPreExecutionFailure} showReadonlyCanvas={showReadonlyCanvas} runNodesError={runNodesError} runError={typeof run?.error === "string" ? run.error : undefined} refetchRunNodes={() => void refetchRunNodes()} inspectorVisible={contract.inspectorVisible} selectedNode={selectedNode} onNodeClick={(nodeId) => { setInspectorTab("execution"); setInspectedNodeId(nodeId); }} onPaneClick={() => setInspectedNodeId(null)} onInspectorClose={() => { setInspectedNodeId(null); selectNode(null); }} inspectorTrigger={contract.inspector.trigger} isReadonlyYamlLoading={isReadonlyYamlLoading} isOverlayLoading={isOverlayLoading} readonlyYaml={readonlyYaml} overlayYaml={overlayYaml} resolvedWorkflowId={resolvedWorkflowId} editable={editable} onDirtyChange={setIsDirty} inspectorTab={inspectorTab} />}
        bottomPanel={<SurfaceBottomPanel runId={activeRunId ?? initialRunId} workflowId={resolvedWorkflowId} defaultState={contract.bottomPanel.defaultState} executionSummary={executionSummary} selectedNodeId={inspectedNodeId} onAuditOpen={() => setActiveTab("canvas")} onAuditNodeSelect={(nodeId) => { selectNode(nodeId); setInspectedNodeId(nodeId); setInspectorTab("context"); }} />}
        statusBar={<SurfaceStatusBar activeTab={activeTab} blockCount={blockCount} edgeCount={edgeCount} stepCountFormat={contract.statusBar.stepCountFormat} metricsVisibility={contract.statusBar.metricsVisibility} />}
      />
      <ProviderModal mode="canvas" open={apiKeyModalOpen} onOpenChange={setApiKeyModalOpen} onSaveSuccess={handleProviderSaveSuccess} />
      <CommitDialog open={commitDialogOpen} onOpenChange={setCommitDialogOpen} files={currentFiles} workflowId={resolvedWorkflowId} draft={currentDraft} onCommitSuccess={handleCommitSuccess} />
    </>
  );
}
