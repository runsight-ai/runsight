import { useState, useCallback, useEffect, useMemo } from "react";
import {
  useAppSettings,
  useModelDefaults,
  useProviders,
  useUpdateAppSettings,
  useUpdateModelDefault,
} from "@/queries/settings";
import { EmptyState } from "@runsight/ui/empty-state";
import { Button } from "@runsight/ui/button";
import { Skeleton } from "@runsight/ui/skeleton";
import { Switch } from "@runsight/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import { Bot, Check, X, AlertCircle, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import type { ModelDefault } from "@/api/settings";

type ProviderOption = {
  id: string;
  name: string;
  models: string[];
  is_active?: boolean;
};

function ModelRow({
  model,
  availableModels,
  onSave,
}: {
  model: ModelDefault;
  availableModels: string[];
  onSave: (id: string, modelName: string) => void;
}) {
  const [selectedModel, setSelectedModel] = useState(model.model_name);
  const hasChanges = selectedModel !== model.model_name;
  const models = availableModels.length > 0 ? availableModels : [model.model_name];
  const handleCancel = () => setSelectedModel(model.model_name);

  useEffect(() => {
    setSelectedModel(model.model_name);
  }, [model.model_name]);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-default bg-surface-secondary p-3 md:flex-row md:items-center">
      <span className="min-w-[100px] shrink-0 text-sm font-medium text-heading">
        {model.provider_name}
      </span>
      <div className="flex flex-1 flex-col gap-3 md:flex-row md:items-center">
        <Select value={selectedModel} onValueChange={(value) => value && setSelectedModel(value)}>
          <SelectTrigger className="min-w-[220px] rounded-md border-border-subtle bg-surface-tertiary font-mono text-sm text-primary">
            <SelectValue placeholder="Select model" />
          </SelectTrigger>
          <SelectContent>
            {models.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {hasChanges && (
          <div className="flex items-center gap-2 md:ml-auto">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onSave(model.id, selectedModel)}
              aria-label={`Save ${model.provider_name} default model`}
            >
              <Check className="h-4 w-4 text-[var(--success-11)]" />
              Save
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              aria-label={`Cancel ${model.provider_name} model change`}
            >
              <X className="h-4 w-4" />
              Cancel
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function FallbackTargetRow({
  modelDefaultId,
  providerId,
  providerName,
  fallbackProviderId,
  fallbackModelId,
  enabledSiblingProviders,
  enabled,
  onCommit,
  onClear,
}: {
  modelDefaultId: string;
  providerId: string;
  providerName: string;
  fallbackProviderId: string | null;
  fallbackModelId: string | null;
  enabledSiblingProviders: ProviderOption[];
  enabled: boolean;
  onCommit: (modelDefaultId: string, fallbackProviderId: string, fallbackModelId: string) => Promise<void>;
  onClear: (modelDefaultId: string) => Promise<void>;
}) {
  const [draftFallbackProvider, setDraftFallbackProvider] = useState<string | null>(
    fallbackProviderId,
  );
  const [draftFallbackModel, setDraftFallbackModel] = useState<string | null>(fallbackModelId);
  const selectedFallbackProvider = useMemo(
    () => enabledSiblingProviders.find((provider) => provider.id === draftFallbackProvider) ?? null,
    [draftFallbackProvider, enabledSiblingProviders],
  );

  useEffect(() => {
    setDraftFallbackProvider(fallbackProviderId);
    setDraftFallbackModel(fallbackModelId);
  }, [fallbackModelId, fallbackProviderId]);

  const handleFallbackProviderChange = useCallback((nextFallbackProviderId: string) => {
    setDraftFallbackProvider(nextFallbackProviderId);
    setDraftFallbackModel(null);
  }, []);

  const handleFallbackModelChange = useCallback(
    async (nextFallbackModelId: string) => {
      setDraftFallbackModel(nextFallbackModelId);

      const fallbackProviderId = draftFallbackProvider;
      const fallbackModelId = nextFallbackModelId;
      if (!fallbackProviderId || !fallbackModelId) return;

      await onCommit(modelDefaultId, fallbackProviderId, fallbackModelId);
    },
    [draftFallbackProvider, modelDefaultId, onCommit],
  );

  const handleClear = useCallback(async () => {
    setDraftFallbackProvider(null);
    setDraftFallbackModel(null);
    await onClear(modelDefaultId);
  }, [modelDefaultId, onClear]);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-default bg-surface-secondary p-3 md:flex-row md:items-center">
      <span className="min-w-[100px] shrink-0 text-sm font-medium text-heading">{providerName}</span>
      <span className="shrink-0 text-sm text-muted">{"->"}</span>
      <div className="flex flex-1 flex-col gap-3 md:flex-row md:items-center">
        <Select
          value={draftFallbackProvider ?? undefined}
          onValueChange={handleFallbackProviderChange}
          disabled={!enabled}
        >
          <SelectTrigger
            aria-label={`Fallback provider for ${providerName}`}
            className="min-w-[220px] rounded-md border-border-subtle bg-surface-tertiary text-sm text-primary"
          >
            <SelectValue placeholder="Select fallback provider" />
          </SelectTrigger>
          <SelectContent>
            {enabledSiblingProviders
              .filter((provider) => provider.id !== providerId)
              .map((provider) => (
                <SelectItem key={provider.id} value={provider.id}>
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
            aria-label={`Fallback model for ${providerName}`}
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
          aria-label={`Clear fallback for ${providerName}`}
        >
          Clear
        </Button>
      </div>
    </div>
  );
}

function FallbackSection({
  modelDefaults,
  enabledProviders,
  fallbackEnabled,
  onToggle,
  onCommit,
  onClear,
  isPending,
}: {
  modelDefaults: ModelDefault[];
  enabledProviders: ProviderOption[];
  fallbackEnabled: boolean;
  onToggle: (settings: { fallback_enabled: boolean }) => Promise<void>;
  onCommit: (modelDefaultId: string, fallbackProviderId: string, fallbackModelId: string) => Promise<void>;
  onClear: (modelDefaultId: string) => Promise<void>;
  isPending: boolean;
}) {
  const canConfigureFallback = enabledProviders.length >= 2;
  const rowsDisabled = !fallbackEnabled;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <div className="font-mono text-2xs font-medium uppercase tracking-wider text-muted">
          Fallback
        </div>
        <label className="flex items-center gap-2 text-sm text-secondary">
          <Switch
            checked={fallbackEnabled}
            onCheckedChange={(checked) => onToggle({ fallback_enabled: checked })}
            aria-label="Enable fallback"
            disabled={isPending || enabledProviders.length < 2}
          />
          Enabled
        </label>
      </div>

      {!canConfigureFallback ? (
        <div className="rounded-lg border border-dashed border-border-default bg-surface-tertiary/30 p-4 text-sm text-muted">
          Enable at least two providers to configure fallback targets.
        </div>
      ) : (
        <div
          className="space-y-2"
          style={rowsDisabled ? { opacity: 0.4, pointerEvents: "none" } : undefined}
        >
          {modelDefaults.map((model) => (
            <FallbackTargetRow
              key={model.id}
              providerName={model.provider_name}
              modelDefaultId={model.id}
              providerId={model.provider_id}
              fallbackProviderId={model.fallback_provider_id ?? null}
              fallbackModelId={model.fallback_model_id ?? null}
              enabledSiblingProviders={enabledProviders.filter((provider) => provider.id !== model.provider_id)}
              enabled={!rowsDisabled}
              onCommit={onCommit}
              onClear={onClear}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export function ModelsTab() {
  const { data, isLoading, error, refetch } = useModelDefaults();
  const { data: providersData } = useProviders();
  const { data: appSettings } = useAppSettings();
  const updateModelDefault = useUpdateModelDefault();
  const updateAppSettings = useUpdateAppSettings();
  const [isRetrying, setIsRetrying] = useState(false);
  const modelDefaults = useMemo(() => data?.items ?? [], [data?.items]);
  const allProviders = useMemo(() => providersData?.items ?? [], [providersData?.items]);
  const enabledProviders = useMemo(
    () => allProviders.filter((provider) => provider.is_active ?? true),
    [allProviders],
  );
  const fallbackEnabled = appSettings?.fallback_enabled ?? true;
  const fallbackModelDefaults = useMemo(
    () =>
      modelDefaults.filter((model) =>
        enabledProviders.some((provider) => provider.id === model.provider_id),
      ),
    [enabledProviders, modelDefaults],
  );

  const getProviderModels = useCallback(
    (providerId: string) => {
      const provider = allProviders.find((item) => item.id === providerId);
      return provider?.models ?? [];
    },
    [allProviders],
  );

  const handleSaveModel = useCallback(
    async (id: string, modelName: string) => {
      try {
        await updateModelDefault.mutateAsync({ id, data: { model_name: modelName } });
        toast.success("Model default saved");
      } catch {
        toast.error("Failed to save model default");
      }
    },
    [updateModelDefault],
  );

  const handleCommitFallback = useCallback(
    async (modelDefaultId: string, fallbackProviderId: string, fallbackModelId: string) => {
      try {
        await updateModelDefault.mutateAsync({
          id: modelDefaultId,
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
    [updateModelDefault],
  );

  const handleClearFallback = useCallback(
    async (modelDefaultId: string) => {
      try {
        await updateModelDefault.mutateAsync({
          id: modelDefaultId,
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
    [updateModelDefault],
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

  return (
    <div className="w-full">
      {isLoading ? (
        <div className="space-y-6">
          <section>
            <div className="mb-3 font-mono text-2xs font-medium uppercase tracking-wider text-muted">
              Default Model per Provider
            </div>
            <div className="space-y-2">
              {[1, 2].map((item) => (
                <div
                  key={item}
                  className="rounded-md border border-border-default bg-surface-secondary p-3"
                >
                  <div className="flex items-center gap-3">
                    <Skeleton className="w-24" />
                    <Skeleton className="h-8 w-full max-w-[360px]" />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center rounded-lg border border-border-default bg-surface-secondary p-8">
          <div className="max-w-md text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-danger" />
            <h3 className="mb-2 text-lg font-medium text-primary">Failed to load model defaults</h3>
            <p className="mb-4 text-sm text-muted">
              {error instanceof Error
                ? error.message
                : "An error occurred while fetching model defaults."}
            </p>
            <Button onClick={handleRetry} variant="secondary" disabled={isRetrying}>
              <RotateCcw className="mr-2 h-4 w-4" />
              {isRetrying ? "Retrying..." : "Retry"}
            </Button>
          </div>
        </div>
      ) : allProviders.length === 0 ? (
        <div className="rounded-lg border border-border-default bg-surface-primary p-8">
          <EmptyState
            icon={Bot}
            title="No model defaults configured"
            description="Model defaults and fallback targets will appear here once providers are connected and models are available."
          />
        </div>
      ) : (
        <div className="space-y-6">
          <section>
            <div className="mb-3 font-mono text-2xs font-medium uppercase tracking-wider text-muted">
              Default Model per Provider
            </div>
            <div className="space-y-2">
              {modelDefaults.map((model) => (
                <ModelRow
                  key={model.id}
                  model={model}
                  availableModels={model.provider_id ? getProviderModels(model.provider_id) : []}
                  onSave={handleSaveModel}
                />
              ))}
            </div>
          </section>

          <FallbackSection
            modelDefaults={fallbackModelDefaults}
            enabledProviders={enabledProviders}
            fallbackEnabled={fallbackEnabled}
            onToggle={handleToggleFallback}
            onCommit={handleCommitFallback}
            onClear={handleClearFallback}
            isPending={updateAppSettings.isPending || updateModelDefault.isPending}
          />
        </div>
      )}
    </div>
  );
}
