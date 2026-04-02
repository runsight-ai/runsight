import { useState, useCallback, useEffect, useMemo, useId } from "react";
import {
  useAppSettings,
  useFallbackTargets,
  useProviders,
  useUpdateAppSettings,
  useUpdateFallbackTarget,
} from "@/queries/settings";
import { EmptyState } from "@runsight/ui/empty-state";
import { Button } from "@runsight/ui/button";
import { Switch } from "@runsight/ui/switch";
import { Skeleton } from "@runsight/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import { AlertCircle, Bot, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import type { FallbackTarget } from "@/api/settings";

type ProviderOption = {
  id: string;
  name: string;
  models: string[];
  is_active?: boolean;
};

function FallbackTargetRow({
  fallbackTarget,
  enabledSiblingProviders,
  enabled,
  onCommit,
  onClear,
}: {
  fallbackTarget: FallbackTarget;
  enabledSiblingProviders: ProviderOption[];
  enabled: boolean;
  onCommit: (providerId: string, fallbackProviderId: string, fallbackModelId: string) => Promise<void>;
  onClear: (providerId: string) => Promise<void>;
}) {
  const [draftFallbackProvider, setDraftFallbackProvider] = useState<string | null>(
    fallbackTarget.fallback_provider_id,
  );
  const [draftFallbackModel, setDraftFallbackModel] = useState<string | null>(
    fallbackTarget.fallback_model_id,
  );
  const selectedFallbackProvider = useMemo(
    () => enabledSiblingProviders.find((provider) => provider.id === draftFallbackProvider) ?? null,
    [draftFallbackProvider, enabledSiblingProviders],
  );

  useEffect(() => {
    setDraftFallbackProvider(fallbackTarget.fallback_provider_id);
    setDraftFallbackModel(fallbackTarget.fallback_model_id);
  }, [fallbackTarget.fallback_model_id, fallbackTarget.fallback_provider_id]);

  const handleFallbackProviderChange = useCallback(
    (nextFallbackProviderName: string | null) => {
      const nextFallbackProvider =
        enabledSiblingProviders.find((provider) => provider.name === nextFallbackProviderName) ??
        null;
      setDraftFallbackProvider(nextFallbackProvider?.id ?? null);
      setDraftFallbackModel(null);
    },
    [enabledSiblingProviders],
  );

  const handleFallbackModelChange = useCallback(
    async (nextFallbackModelId: string | null) => {
      setDraftFallbackModel(nextFallbackModelId);

      const fallbackProviderId = draftFallbackProvider;
      const fallbackModelId = nextFallbackModelId;
      if (!fallbackProviderId || !fallbackModelId) return;

      await onCommit(fallbackTarget.provider_id, fallbackProviderId, fallbackModelId);
    },
    [draftFallbackProvider, fallbackTarget.provider_id, onCommit],
  );

  const handleClear = useCallback(async () => {
    setDraftFallbackProvider(null);
    setDraftFallbackModel(null);
    await onClear(fallbackTarget.provider_id);
  }, [fallbackTarget.provider_id, onClear]);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-default bg-surface-secondary p-3 md:flex-row md:items-center">
      <span className="min-w-[100px] shrink-0 text-sm font-medium text-heading">
        {fallbackTarget.provider_name}
      </span>
      <span className="shrink-0 text-sm text-muted">{"->"}</span>
      <div className="flex flex-1 flex-col gap-3 md:flex-row md:items-center">
        <Select
          value={selectedFallbackProvider?.name ?? undefined}
          onValueChange={handleFallbackProviderChange}
          disabled={!enabled}
        >
          <SelectTrigger
            aria-label={`Fallback provider for ${fallbackTarget.provider_name}`}
            className="min-w-[220px] rounded-md border-border-subtle bg-surface-tertiary text-sm text-primary"
          >
            <SelectValue placeholder="Select fallback provider" />
          </SelectTrigger>
          <SelectContent>
            {enabledSiblingProviders.map((provider) => (
              <SelectItem key={provider.id} value={provider.name}>
                {provider.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={draftFallbackModel ?? undefined}
          onValueChange={handleFallbackModelChange}
          disabled={!enabled || !selectedFallbackProvider}
        >
          <SelectTrigger
            aria-label={`Fallback model for ${fallbackTarget.provider_name}`}
            className="min-w-[220px] rounded-md border-border-subtle bg-surface-tertiary font-mono text-sm text-primary"
          >
            <SelectValue placeholder="Select fallback model" />
          </SelectTrigger>
          <SelectContent>
            {(selectedFallbackProvider?.models ?? []).map((model) => (
              <SelectItem key={model} value={model}>
                {model}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleClear}
          disabled={!enabled || (!draftFallbackProvider && !draftFallbackModel)}
          aria-label={`Clear fallback for ${fallbackTarget.provider_name}`}
        >
          Clear
        </Button>
      </div>
    </div>
  );
}

function FallbackSection({
  fallbackTargets,
  enabledProviders,
  fallbackEnabled,
  onToggle,
  onCommit,
  onClear,
  isPending,
}: {
  fallbackTargets: FallbackTarget[];
  enabledProviders: ProviderOption[];
  fallbackEnabled: boolean;
  onToggle: (settings: { fallback_enabled: boolean }) => Promise<void>;
  onCommit: (providerId: string, fallbackProviderId: string, fallbackModelId: string) => Promise<void>;
  onClear: (providerId: string) => Promise<void>;
  isPending: boolean;
}) {
  const canConfigureFallback = enabledProviders.length >= 2;
  const rowsDisabled = !fallbackEnabled;
  const fallbackToggleLabelId = useId();

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <div className="font-mono text-2xs font-medium uppercase tracking-wider text-muted">
          Fallback
        </div>
        <div className="flex items-center gap-2 text-sm text-secondary">
          <Switch
            checked={fallbackEnabled}
            onCheckedChange={(checked) => onToggle({ fallback_enabled: checked })}
            aria-labelledby={fallbackToggleLabelId}
            disabled={isPending || !canConfigureFallback}
          />
          <span id={fallbackToggleLabelId}>Enable fallback</span>
        </div>
      </div>

      {!canConfigureFallback ? (
        <div className="rounded-lg border border-dashed border-border-default bg-surface-tertiary/30 p-4 text-sm text-muted">
          Enable at least two enabled providers to configure fallback targets.
        </div>
      ) : (
        <>
          <p className="text-sm text-muted">
            If the primary provider fails at runtime, Runsight retries once on the configured
            fallback provider and model.
          </p>
          <div
            className="space-y-2"
            style={rowsDisabled ? { opacity: 0.4, pointerEvents: "none" } : undefined}
          >
            {fallbackTargets.map((fallbackTarget) => (
              <FallbackTargetRow
                key={fallbackTarget.id}
                fallbackTarget={fallbackTarget}
                enabledSiblingProviders={enabledProviders.filter(
                  (provider) => provider.id !== fallbackTarget.provider_id,
                )}
                enabled={!rowsDisabled}
                onCommit={onCommit}
                onClear={onClear}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export function ModelsTab() {
  const { data, isLoading, error, refetch } = useFallbackTargets();
  const { data: providersData } = useProviders();
  const { data: appSettings } = useAppSettings();
  const updateFallbackTarget = useUpdateFallbackTarget();
  const updateAppSettings = useUpdateAppSettings();
  const [isRetrying, setIsRetrying] = useState(false);

  const allProviders = useMemo<ProviderOption[]>(
    () =>
      (providersData?.items ?? []).map((provider) => ({
        id: provider.id,
        name: provider.name,
        models: provider.models ?? [],
        is_active: provider.is_active,
      })),
    [providersData?.items],
  );
  const enabledProviders = useMemo(
    () => allProviders.filter((provider) => provider.is_active ?? true),
    [allProviders],
  );
  const fallbackTargets = useMemo(() => data?.items ?? [], [data?.items]);
  const fallbackEnabled = appSettings?.fallback_enabled ?? false;

  const handleCommitFallback = useCallback(
    async (providerId: string, fallbackProviderId: string, fallbackModelId: string) => {
      try {
        await updateFallbackTarget.mutateAsync({
          id: providerId,
          data: {
            fallback_provider_id: fallbackProviderId,
            fallback_model_id: fallbackModelId,
          },
        });
        toast.success("Fallback target updated");
      } catch {
        toast.error("Failed to update fallback target");
      }
    },
    [updateFallbackTarget],
  );

  const handleClearFallback = useCallback(
    async (providerId: string) => {
      try {
        await updateFallbackTarget.mutateAsync({
          id: providerId,
          data: {
            fallback_provider_id: "",
            fallback_model_id: "",
          },
        });
        toast.success("Fallback target cleared");
      } catch {
        toast.error("Failed to clear fallback target");
      }
    },
    [updateFallbackTarget],
  );

  const handleToggleFallback = useCallback(
    async ({ fallback_enabled: nextFallbackEnabled }: { fallback_enabled: boolean }) => {
      await updateAppSettings.mutateAsync({ fallback_enabled: nextFallbackEnabled });
    },
    [updateAppSettings],
  );

  const handleRetry = useCallback(async () => {
    setIsRetrying(true);
    try {
      await refetch();
    } finally {
      setIsRetrying(false);
    }
  }, [refetch]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <section>
          <div className="mb-3 font-mono text-2xs font-medium uppercase tracking-wider text-muted">
            Fallback
          </div>
          <div className="space-y-2">
            {[1, 2].map((item) => (
              <div
                key={item}
                className="rounded-md border border-border-default bg-surface-secondary p-3"
              >
                <div className="flex items-center gap-3">
                  <Skeleton className="w-24" />
                  <Skeleton className="h-8 w-full max-w-[240px]" />
                  <Skeleton className="h-8 w-full max-w-[240px]" />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-border-default bg-surface-secondary p-8">
        <div className="max-w-md text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-danger" />
          <h3 className="mb-2 text-lg font-medium text-primary">Failed to load fallback settings</h3>
          <p className="mb-4 text-sm text-muted">
            {error instanceof Error
              ? error.message
              : "An error occurred while fetching fallback settings."}
          </p>
          <Button onClick={handleRetry} variant="secondary" disabled={isRetrying}>
            <RotateCcw className="mr-2 h-4 w-4" />
            {isRetrying ? "Retrying..." : "Retry"}
          </Button>
        </div>
      </div>
    );
  }

  if (allProviders.length === 0) {
    return (
      <div className="rounded-lg border border-border-default bg-surface-primary p-8">
        <EmptyState
          icon={Bot}
          title="No providers configured"
          description="Connect at least one provider to manage runtime fallback."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <FallbackSection
        fallbackTargets={fallbackTargets}
        enabledProviders={enabledProviders}
        fallbackEnabled={fallbackEnabled}
        onToggle={handleToggleFallback}
        onCommit={handleCommitFallback}
        onClear={handleClearFallback}
        isPending={updateAppSettings.isPending || updateFallbackTarget.isPending}
      />
    </div>
  );
}
