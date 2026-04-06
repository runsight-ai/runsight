import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { WorkflowSurfaceProps, WorkflowSurfaceMode } from "./workflowSurfaceContract";
import { getContractForMode, getCanvasYamlToggleVisibility, getSaveButtonState, getActionButton, isEditable } from "./workflowSurfaceContract";
import { CanvasTopbar } from "./CanvasTopbar";
import { YamlEditor } from "./YamlEditor";
import { CanvasBottomPanel } from "./CanvasBottomPanel";
import { CanvasStatusBar } from "./CanvasStatusBar";

import { ProviderModal } from "@/components/provider/ProviderModal";
import { EmptyState } from "@runsight/ui/empty-state";
import { LayoutGrid } from "lucide-react";
import { useCanvasStore } from "@/store/canvas";
import { useUpdateWorkflow } from "@/queries/workflows";
import { useWorkflow } from "@/queries/workflows";

export function WorkflowSurface({ mode: initialMode, workflowId: initialWorkflowId = "", runId: initialRunId }: WorkflowSurfaceProps) {
  const [mode, setMode] = useState<WorkflowSurfaceMode>(initialMode);
  const [workflowId, setWorkflowId] = useState(initialWorkflowId);
  const [activeRunId, setRunId] = useState(initialRunId);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const queryClient = useQueryClient();
  const updateWorkflow = useUpdateWorkflow();

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
  const { data: workflow } = useWorkflow(workflowId);

  const nodes = useCanvasStore((s) => s.nodes);
  const edges = useCanvasStore((s) => s.edges);
  const blockCount = useCanvasStore((s) => s.blockCount);
  const edgeCount = useCanvasStore((s) => s.edgeCount);
  const yamlContent = useCanvasStore((s) => s.yamlContent);
  const toPersistedState = useCanvasStore((s) => s.toPersistedState);
  const markSaved = useCanvasStore((s) => s.markSaved);
  const setYamlContent = useCanvasStore((s) => s.setYamlContent);
  const hydrateFromPersisted = useCanvasStore((s) => s.hydrateFromPersisted);

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
    if (!workflowId || !workflow?.yaml) {
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
    workflowId,
  ]);

  // Palette + inspector hidden — canvas coming soon
  const canvasColumn = "1";

  const handleSave = useCallback(async () => {
    if (!editable || !workflowId) {
      return;
    }

    await updateWorkflow.mutateAsync({
      id: workflowId,
      data: {
        yaml: yamlContent,
        canvas_state: toPersistedState(),
      },
    });

    markSaved();
    setIsDirty(false);
  }, [editable, markSaved, toPersistedState, updateWorkflow, workflowId, yamlContent]);

  const saveButtonState = getSaveButtonState(mode, isDirty);
  const actionButton = mode === "edit" ? undefined : getActionButton(mode);

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
          workflowId={workflowId}
          runId={activeRunId ?? initialRunId}
          activeTab={activeTab}
          onValueChange={(v) => setActiveTab(v as "canvas" | "yaml")}
          isDirty={isDirty}
          onSave={() => {
            void handleSave();
          }}
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
          <div className="flex-1 flex items-center justify-center">
            <EmptyState
              icon={LayoutGrid}
              title="Visual canvas coming soon"
              description="The drag-and-drop workflow builder is under active development."
            />
          </div>
        ) : activeTab === "yaml" ? (
          <YamlEditor
            workflowId={workflowId}
            readOnly={!editable}
            onDirtyChange={(dirty: boolean) => setIsDirty(dirty)}
          />
        ) : null}
      </div>

      <div
        data-testid="surface-bottom-panel"
        style={{ gridColumn: "1 / -1", gridRow: "3" }}
      >
        <CanvasBottomPanel
          runId={activeRunId ?? initialRunId}
          workflowId={workflowId}
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
    </div>
  );
}
