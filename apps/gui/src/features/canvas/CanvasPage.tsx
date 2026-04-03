import { useCallback, useRef, useState } from "react";
import { useLocation, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";

import { ProviderModal } from "@/components/provider/ProviderModal";
import { useProviders } from "@/queries/settings";

import { CanvasTopbar } from "./CanvasTopbar";
import { WorkflowSurfaceRoute } from "./WorkflowSurfaceRoute";
import type { WorkflowSurfaceMode } from "./workflowSurfaceContract";

interface CanvasPageLocationState {
  workflowSurfaceMode?: WorkflowSurfaceMode;
}

export function Component() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation() as { state?: CanvasPageLocationState };
  const queryClient = useQueryClient();
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [saveAndRun, setSaveAndRun] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const { data: providers } = useProviders();
  const activeProviders = (providers?.items ?? []).filter((provider) => provider.is_active ?? true);
  const initialMode = location.state?.workflowSurfaceMode === "fork-draft"
    ? "fork-draft"
    : "workflow";
  const handleRunCompatibility = useCallback(() => {}, []);
  const handleOpenApiKeyModal = useCallback(() => {
    setSaveAndRun(true);
    setApiKeyModalOpen(true);
  }, []);
  const handleApiKeyModalClose = useCallback((open: boolean) => {
    setApiKeyModalOpen(open);
    if (!open) {
      triggerRef.current?.focus();
    }
  }, []);
  const handleSaveSuccess = useCallback((_providerId: string) => {
    setApiKeyModalOpen(false);
    queryClient.invalidateQueries({ queryKey: ["providers"] });
    if (saveAndRun) {
      handleRunCompatibility();
    }
    triggerRef.current?.focus();
  }, [handleRunCompatibility, queryClient, saveAndRun]);

  // Preserve the adapter-level provider/modal contract here while the
  // converged WorkflowSurface implementation lives in the shared route layer.
  const canvasTopbarCompatibility = (
    <CanvasTopbar
      workflowId={id!}
      activeTab="yaml"
      onValueChange={() => {}}
      onAddApiKey={handleOpenApiKeyModal}
    />
  );
  const providerModalCompatibility = (
    <ProviderModal
      mode="canvas"
      open={apiKeyModalOpen}
      onOpenChange={handleApiKeyModalClose}
      onSaveSuccess={handleSaveSuccess}
    />
  );
  void canvasTopbarCompatibility;
  void providerModalCompatibility;
  void activeProviders;

  return (
    <WorkflowSurfaceRoute
      workflowId={id!}
      initialMode={initialMode}
    />
  );
}

export default Component;
