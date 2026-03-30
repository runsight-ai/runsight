import { useState, useCallback, useRef } from "react";
import { useParams, useBlocker } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "lucide-react";
import { CanvasTopbar } from "./CanvasTopbar";
import { UncommittedBanner } from "./UncommittedBanner";
import { CanvasStatusBar } from "./CanvasStatusBar";
import { CanvasBottomPanel } from "./CanvasBottomPanel";
import { FirstTimeTooltip } from "./FirstTimeTooltip";
import { PaletteSidebar } from "./PaletteSidebar";
import { ExploreBanner } from "./ExploreBanner";
import { ApiKeyModal } from "@/features/setup/ApiKeyModal";
import { EmptyState } from "@runsight/ui/empty-state";
import { YamlEditor } from "./YamlEditor";
import { useUpdateWorkflow } from "@/queries/workflows";
import { useCreateRun } from "@/queries/runs";
import { useCanvasStore } from "@/store/canvas";
import { Dialog, DialogContent, DialogTitle, DialogFooter } from "@runsight/ui/dialog";
import { Button } from "@runsight/ui/button";
import type { ValidationState } from "./useYamlValidation";

export function Component() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("yaml");
  const [isDirty, setIsDirty] = useState(false);
  const [yamlValid, setYamlValid] = useState(true);
  const [errorCount, setErrorCount] = useState(0);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [saveAndRun, setSaveAndRun] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const updateWorkflow = useUpdateWorkflow();
  const createRun = useCreateRun();
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);

  const blocker = useBlocker(isDirty);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setIsDirty(dirty);
  }, []);

  const handleValidation = useCallback((state: ValidationState) => {
    setYamlValid(state.isValid);
    setErrorCount(state.errorCount);
  }, []);

  const handleSave = useCallback(() => {
    const yamlContent = useCanvasStore.getState().yamlContent;
    updateWorkflow.mutate(
      { id: id!, data: { yaml: yamlContent } },
      { onSuccess: () => setIsDirty(false) },
    );
  }, [id, updateWorkflow]);

  const handleOpenApiKeyModal = useCallback(() => {
    setSaveAndRun(false);
    setApiKeyModalOpen(true);
  }, []);

  const handleRun = useCallback(() => {
    createRun.mutate(
      { workflow_id: id!, source: "manual" },
      { onSuccess: (result) => setActiveRunId(result.id) },
    );
  }, [id, createRun, setActiveRunId]);

  const handleApiKeyModalClose = useCallback(
    (open: boolean) => {
      setApiKeyModalOpen(open);
      if (!open) {
        triggerRef.current?.focus();
      }
    },
    [],
  );

  const handleSaveSuccess = useCallback(
    (_providerId: string) => {
      setApiKeyModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      if (saveAndRun) {
        handleRun();
      }
      triggerRef.current?.focus();
    },
    [queryClient, saveAndRun, handleRun],
  );

  return (
    <div
      data-layout="flex-row"
      className="grid h-full"
      style={{
        gridTemplateRows: "var(--header-height) 1fr 37px var(--status-bar-height)",
        gridTemplateColumns: sidebarCollapsed ? "48px 1fr" : "240px 1fr",
      }}
    >
      <CanvasTopbar
        workflowId={id!}
        activeTab={activeTab}
        onValueChange={setActiveTab}
        isDirty={isDirty}
        onSave={handleSave}
        yamlValid={yamlValid}
        errorCount={errorCount}
        onAddApiKey={handleOpenApiKeyModal}
      />
      <PaletteSidebar onCollapse={setSidebarCollapsed} />
      <div className="relative flex flex-col overflow-hidden" style={{ gridColumn: "2", gridRow: "2" }}>
        <ExploreBanner onAddApiKey={() => setApiKeyModalOpen(true)} />
        <UncommittedBanner />
        {activeTab === "canvas" ? (
          <EmptyState
            icon={Layout}
            title="Visual canvas coming soon"
            description="Switch to YAML to edit your workflow."
            action={{ label: "Switch to YAML", onClick: () => setActiveTab("yaml") }}
          />
        ) : (
          <div className="flex-1 overflow-hidden">
            <YamlEditor workflowId={id!} onDirtyChange={handleDirtyChange} onValidation={handleValidation} />
          </div>
        )}
      </div>

      <FirstTimeTooltip />
      <CanvasBottomPanel />
      <CanvasStatusBar activeTab={activeTab} />

      {/* Unsaved changes dialog */}
      <Dialog open={blocker.state === "blocked"}>
        <DialogContent>
          <DialogTitle>You have unsaved changes</DialogTitle>
          <p className="text-sm text-secondary px-5 py-4">
            Your changes will be lost if you leave without saving.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => blocker.reset?.()}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={() => blocker.proceed?.()}>
              Discard
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                handleSave();
                blocker.proceed?.();
              }}
            >
              Save & Leave
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ApiKeyModal
        open={apiKeyModalOpen}
        onOpenChange={handleApiKeyModalClose}
        onSaveSuccess={handleSaveSuccess}
        saveAndRun={saveAndRun}
      />
    </div>
  );
}
