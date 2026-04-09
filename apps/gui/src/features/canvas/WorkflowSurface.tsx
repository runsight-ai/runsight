import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import type { WorkflowSurfaceProps, WorkflowSurfaceMode } from "./workflowSurfaceContract";
import { getContractForMode, getCanvasYamlToggleVisibility, getSaveButtonState, getActionButton, isEditable } from "./workflowSurfaceContract";
import { CanvasTopbar } from "./CanvasTopbar";
import { YamlEditor } from "./YamlEditor";
import { CanvasBottomPanel } from "./CanvasBottomPanel";
import { CanvasStatusBar } from "./CanvasStatusBar";
import { WorkflowCanvas } from "./WorkflowCanvas";

import { ProviderModal } from "@/components/provider/ProviderModal";
import { CommitDialog } from "@/features/git/CommitDialog";
import { EmptyState } from "@runsight/ui/empty-state";
import { LayoutGrid } from "lucide-react";
import { useCanvasStore } from "@/store/canvas";
import { useRun, useRunNodes } from "@/queries/runs";
import { useWorkflow } from "@/queries/workflows";
import { gitApi } from "@/api/git";
import { mapRunStatus } from "@/features/runs/runDetailUtils";

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
  const queryClient = useQueryClient();
  const overlayRef = getOverlayRefFromLocation();
  const readonlyRunId = mode === "readonly" ? (activeRunId ?? initialRunId ?? "") : "";

  const handleForkTransition = useCallback((newWorkflowId: string) => {
    setMode("edit");
    setWorkflowId(newWorkflowId);
    setRunId(undefined);
    window.history.replaceState(null, "", `/workflows/${newWorkflowId}/edit`);
  }, []);

  const contract = getContractForMode(mode);

  const { topbar, bottomPanel, statusBar } = contract;

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
  } = useRun(readonlyRunId, {
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
  const { data: runNodes } = useRunNodes(readonlyRunId);

  const nodes = useCanvasStore((s) => s.nodes);
  const edges = useCanvasStore((s) => s.edges);
  const blockCount = useCanvasStore((s) => s.blockCount);
  const edgeCount = useCanvasStore((s) => s.edgeCount);
  const setYamlContent = useCanvasStore((s) => s.setYamlContent);
  const hydrateFromPersisted = useCanvasStore((s) => s.hydrateFromPersisted);
  const setNodeStatus = useCanvasStore((s) => s.setNodeStatus);
  const setActiveCanvasRunId = useCanvasStore((s) => s.setActiveRunId);
  const setRunCost = useCanvasStore((s) => s.setRunCost);

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
      setNodeStatus(runNode.node_id, mapRunStatus(runNode.status));
    }
  }, [mode, workflow?.canvas_state, runNodes, setNodeStatus]);

  // Palette + inspector hidden — canvas coming soon
  const canvasColumn = "1";

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

  return (
    <div
      className="grid h-full"
      style={{
        gridTemplateRows: "var(--header-height) 1fr auto var(--status-bar-height)",
        gridTemplateColumns: "1fr",
      }}
    >
      <div data-testid="surface-topbar" style={{ gridColumn: "1 / -1", gridRow: "1" }}>
        <CanvasTopbar
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
          onForkTransition={handleForkTransition}
        />
      </div>

      <div
        data-testid="surface-center"
        className="relative flex flex-col overflow-hidden"
        style={{ gridColumn: canvasColumn, gridRow: "2" }}
      >
        {activeTab === "canvas" ? (
          mode === "readonly" && workflow?.canvas_state ? (
            <WorkflowCanvas
              isDraggable={false}
              connectionsAllowed={false}
              deletionAllowed={false}
            />
          ) : mode === "readonly" ? (
            <div className="flex-1 flex items-center justify-center">
              <EmptyState
                icon={LayoutGrid}
                title="Canvas layout unavailable"
                description="Canvas layout unavailable for this run. Switch to the YAML tab to inspect the workflow definition."
              />
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <EmptyState
                icon={LayoutGrid}
                title="Visual canvas coming soon"
                description="The drag-and-drop workflow builder is under active development."
              />
            </div>
          )
        ) : activeTab === "yaml" ? (
          (mode === "readonly" && isReadonlyYamlLoading) || isOverlayLoading ? (
            <div className="flex h-full items-center justify-center text-muted">
              {mode === "readonly" ? "Loading run details..." : "Loading workflow snapshot..."}
            </div>
          ) : (
            <YamlEditor
              workflowId={resolvedWorkflowId}
              yaml={mode === "readonly" ? (readonlyYaml ?? undefined) : (overlayYaml ?? undefined)}
              readOnly={!editable}
              onDirtyChange={(dirty: boolean) => setIsDirty(dirty)}
            />
          )
        ) : null}
      </div>

      <div
        data-testid="surface-bottom-panel"
        style={{ gridColumn: "1 / -1", gridRow: "3" }}
      >
        <CanvasBottomPanel
          runId={activeRunId ?? initialRunId}
          workflowId={resolvedWorkflowId}
          defaultState={defaultState}
        />
      </div>

      <div
        data-testid="surface-status-bar"
        style={{ gridColumn: "1 / -1", gridRow: "4" }}
      >
        <CanvasStatusBar
          activeTab={activeTab}
          blockCount={blockCount}
          edgeCount={edgeCount}
          stepCountFormat={stepCountFormat}
          metricsVisibility={metricsVisibility}
        />
      </div>

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
    </div>
  );
}
