import { useState, useCallback, useRef } from "react";
import { useParams, useBlocker } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { CanvasTopbar } from "./CanvasTopbar";
import { CanvasStatusBar } from "./CanvasStatusBar";
import { CanvasBottomPanel } from "./CanvasBottomPanel";
import { FirstTimeTooltip } from "./FirstTimeTooltip";
import { PaletteSidebar } from "./PaletteSidebar";
import { PriorityBanner } from "@/components/shared/PriorityBanner";
import type { BannerCondition } from "@/components/shared/PriorityBanner";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { ProviderModal } from "@/components/provider/ProviderModal";
import { CommitDialog } from "@/features/git/CommitDialog";
import { gitApi } from "@/api/git";
import { YamlEditor } from "./YamlEditor";
import { getWorkflowSurfaceModeConfig } from "./workflowSurfaceContract";
import { useCreateRun } from "@/queries/runs";
import { useWorkflow, useWorkflowRegressions } from "@/queries/workflows";
import { useProviders } from "@/queries/settings";
import { useGitStatus } from "@/queries/git";
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
  const [commitDialogOpen, setCommitDialogOpen] = useState(false);
  const [, setLeaveAfterCommit] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const createRun = useCreateRun();
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);
  const blockCount = useCanvasStore((s) => s.blockCount);
  const edgeCount = useCanvasStore((s) => s.edgeCount);
  const { data: providers } = useProviders();
  const { data: gitStatus } = useGitStatus();
  const { data: workflow } = useWorkflow(id!);
  const { data: regressionsData } = useWorkflowRegressions(id!);
  const activeProviders = (providers?.items ?? []).filter((p) => p.is_active ?? true);
  const isCommitted = Boolean(workflow?.commit_sha);
  const workflowSurface = getWorkflowSurfaceModeConfig("workflow");

  const bannerConditions: BannerCondition[] = [
    {
      type: "explore",
      active: activeProviders.length === 0,
      message: "You are in explore mode.",
      action: { label: "Add an API key", onClick: () => setApiKeyModalOpen(true) },
    },
    {
      type: "uncommitted",
      active: Boolean(gitStatus && !gitStatus.is_clean),
      message: `${gitStatus?.uncommitted_files?.length ?? 0} uncommitted change${(gitStatus?.uncommitted_files?.length ?? 0) === 1 ? "" : "s"}`,
      action: { label: "Commit", onClick: () => setCommitDialogOpen(true) },
    },
    {
      type: "regressions",
      active: (regressionsData?.count ?? 0) > 0,
      message: `${regressionsData?.count ?? 0} regression${(regressionsData?.count ?? 0) === 1 ? "" : "s"} detected across runs`,
    },
  ];

  const blocker = useBlocker(isDirty);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setIsDirty(dirty);
  }, []);

  const handleValidation = useCallback((state: ValidationState) => {
    setYamlValid(state.isValid);
    setErrorCount(state.errorCount);
  }, []);

  const handleSave = useCallback(() => {
    setLeaveAfterCommit(false);
    setCommitDialogOpen(true);
  }, []);

  const handleOpenApiKeyModal = useCallback(() => {
    setSaveAndRun(true);
    setApiKeyModalOpen(true);
  }, []);

  const handleRun = useCallback(async () => {
    if (isDirty || !isCommitted) {
      const yamlContent = useCanvasStore.getState().yamlContent;
      const simResult = await gitApi.createSimBranch(id!, yamlContent);
      createRun.mutate(
        { workflow_id: id!, source: "simulation", branch: simResult.branch },
        { onSuccess: (result) => setActiveRunId(result.id) },
      );
    } else {
      createRun.mutate(
        { workflow_id: id!, source: "manual", branch: "main" },
        { onSuccess: (result) => setActiveRunId(result.id) },
      );
    }
  }, [createRun, id, isCommitted, isDirty, setActiveRunId]);

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

  const handleCommitDialogOpenChange = useCallback((open: boolean) => {
    setCommitDialogOpen(open);
    if (!open) {
      setLeaveAfterCommit(false);
    }
  }, []);

  const handleLeaveAfterSave = useCallback(() => {
    setLeaveAfterCommit(true);
    setCommitDialogOpen(true);
  }, []);

  const handleCommitSuccess = useCallback(() => {
    setIsDirty(false);
    setCommitDialogOpen(false);
    setLeaveAfterCommit((shouldLeave) => {
      if (shouldLeave && blocker.state === "blocked") {
        blocker.proceed?.();
      }
      return false;
    });
  }, [blocker]);

  const handleCommitError = useCallback(() => {}, []);

  const canvasStoreState = useCanvasStore.getState();
  const currentCanvasState =
    typeof canvasStoreState.toPersistedState === "function"
      ? canvasStoreState.toPersistedState()
      : undefined;
  const currentDraft = {
    yaml: canvasStoreState.yamlContent,
    canvas_state: currentCanvasState as Record<string, unknown> | undefined,
  };
  const currentFiles = [{ path: `custom/workflows/${id!}.yaml`, status: "modified" }];

  if (currentCanvasState) {
    currentFiles.push({
      path: `custom/workflows/.canvas/${id!}.canvas.json`,
      status: "modified",
    });
  }

  return (
    <div
      data-layout="flex-row"
      className="grid h-full"
      style={{
        gridTemplateRows: "var(--header-height) 1fr 37px var(--status-bar-height)",
        gridTemplateColumns: sidebarCollapsed ? "48px 1fr" : "240px 1fr",
      }}
    >
      {workflowSurface.regions.topbar.visible ? (
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
      ) : null}
      {workflowSurface.regions.palette.visible ? (
        <PaletteSidebar onCollapse={setSidebarCollapsed} />
      ) : null}
      <div className="relative flex flex-col overflow-hidden" style={{ gridColumn: "2", gridRow: "2" }}>
        <PriorityBanner conditions={bannerConditions} />
        {workflowSurface.regions.center.visible ? (
          activeTab === "canvas" ? (
            <WorkflowCanvas />
          ) : (
            <div className="flex-1 overflow-hidden">
              <YamlEditor
                workflowId={id!}
                onDirtyChange={handleDirtyChange}
                onValidation={handleValidation}
              />
            </div>
          )
        ) : null}
      </div>

      <FirstTimeTooltip />
      {workflowSurface.regions.footer.visible ? (
        <CanvasBottomPanel workflowId={id} />
      ) : null}
      {workflowSurface.regions.statusBar.visible ? (
        <CanvasStatusBar activeTab={activeTab} blockCount={blockCount} edgeCount={edgeCount} />
      ) : null}

      {/* Unsaved changes dialog */}
      <Dialog open={blocker.state === "blocked" && !commitDialogOpen}>
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
              onClick={handleLeaveAfterSave}
            >
              Save & Leave
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ProviderModal
        mode="canvas"
        open={apiKeyModalOpen}
        onOpenChange={handleApiKeyModalClose}
        onSaveSuccess={handleSaveSuccess}
      />

      <CommitDialog
        open={commitDialogOpen}
        onOpenChange={handleCommitDialogOpenChange}
        files={currentFiles}
        workflowId={id!}
        draft={currentDraft}
        onCommitSuccess={handleCommitSuccess}
        onCommitError={handleCommitError}
      />
    </div>
  );
}
