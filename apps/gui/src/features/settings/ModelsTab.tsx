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
import {
  Bot,
  Check,
  X,
  GripVertical,
  ChevronUp,
  ChevronDown,
  AlertCircle,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import type { ModelDefault } from "@/api/settings";

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
        <Select
          value={selectedModel}
          onValueChange={(v) => v && setSelectedModel(v)}
        >
          <SelectTrigger className="min-w-[220px] rounded-md border-border-subtle bg-surface-tertiary font-mono text-sm text-primary">
            <SelectValue placeholder="Select model" />
          </SelectTrigger>
          <SelectContent>
            {models.map((m) => (
              <SelectItem key={m} value={m}>
                {m}
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

function FallbackChainSection({
  enabled,
  modelDefaults,
  onReorder,
}: {
  enabled: boolean;
  modelDefaults: ModelDefault[];
  onReorder: (id: string, chain: string[]) => void;
}) {
  const primary = modelDefaults.find((m) => m.is_default) ?? modelDefaults[0];
  const primaryId = primary?.id ?? null;
  const fallbackChainSource = primary?.fallback_chain;
  const primaryFallbackChain = useMemo(
    () => fallbackChainSource ?? [],
    [fallbackChainSource],
  );
  const [localChain, setLocalChain] = useState<string[]>([]);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (primary && !hasChanges) setLocalChain(primaryFallbackChain);
  }, [primary, primaryFallbackChain, hasChanges]);

  const move = (index: number, direction: 1 | -1) => {
    if (!enabled) return;
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= localChain.length) return;
    const next = [...localChain];
    const a = next[index];
    const b = next[newIndex];
    if (a !== undefined && b !== undefined) {
      next[index] = b;
      next[newIndex] = a;
      setLocalChain(next);
      setHasChanges(true);
    }
  };

  const handleSave = useCallback(() => {
    if (!primaryId) return;
    onReorder(primaryId, localChain);
    setHasChanges(false);
  }, [localChain, onReorder, primaryId]);

  const handleCancel = useCallback(() => {
    setLocalChain(primaryFallbackChain);
    setHasChanges(false);
  }, [primaryFallbackChain]);
  const providerNamesByModel = useMemo(
    () =>
      new Map(
        modelDefaults.map((model) => [model.model_name, model.provider_name]),
      ),
    [modelDefaults],
  );

  if (!primary) return null;

  if (localChain.length === 0 && !hasChanges) {
    return (
      <div className="rounded-lg border border-dashed border-border-default bg-surface-tertiary/30 p-4 text-center text-sm text-muted">
        No fallback models configured. Set default models above first.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted">Retry order when primary fails</span>
        {hasChanges && (
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSave}
              disabled={!enabled}
            >
              Save order
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              disabled={!enabled}
            >
              Cancel
            </Button>
          </div>
        )}
      </div>
      <ul
        className={
          enabled
            ? "space-y-2"
            : "space-y-2 opacity-50 pointer-events-none"
        }
      >
        {localChain.map((name, i) => (
          <li
            key={`${name}-${i}`}
            className="flex items-center gap-3 rounded-md border border-border-default bg-surface-secondary px-3 py-2.5 text-sm"
          >
            <GripVertical className="h-4 w-4 shrink-0 text-muted" />
            <span className="w-5 shrink-0 text-center font-mono text-2xs text-muted">
              {i + 1}
            </span>
            <span className="flex-1 font-mono text-sm text-primary">{name}</span>
            <span className="shrink-0 text-2xs text-muted">
              {providerNamesByModel.get(name) ?? "Unknown provider"}
            </span>
            <div className="ml-auto flex shrink-0 gap-1">
              <Button
                variant="icon-only"
                size="icon-sm"
                onClick={() => move(i, -1)}
                disabled={!enabled || i === 0}
                aria-label={`Move ${name} up`}
              >
                <ChevronUp className="h-4 w-4" />
              </Button>
              <Button
                variant="icon-only"
                size="icon-sm"
                onClick={() => move(i, 1)}
                disabled={!enabled || i === localChain.length - 1}
                aria-label={`Move ${name} down`}
              >
                <ChevronDown className="h-4 w-4" />
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <p className="text-sm leading-relaxed text-muted">
        When enabled, if the primary model fails (rate limit, timeout), the
        system tries the next model in the chain. When disabled, failures are
        reported immediately. Drag to reorder.
      </p>
    </div>
  );
}

export function ModelsTab() {
  const { data, isLoading, error, refetch } = useModelDefaults();
  const { data: providersData } = useProviders();
  const { data: appSettings } = useAppSettings();
  const updateModelDefault = useUpdateModelDefault();
  const updateAppSettings = useUpdateAppSettings();
  const [isRetrying, setIsRetrying] = useState(false);
  const modelDefaults = data?.items ?? [];
  const providers = useMemo(() => providersData?.items ?? [], [providersData?.items]);
  const fallbackChainEnabled = appSettings?.fallback_chain_enabled ?? true;
  const showFallbackChain =
    modelDefaults.filter((model) => model.model_name.trim().length > 0).length > 1;

  const getProviderModels = useCallback(
    (providerId: string) => {
      const p = providers.find((pr) => pr.id === providerId);
      return p?.models ?? [];
    },
    [providers]
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
    [updateModelDefault]
  );

  const handleReorderChain = useCallback(
    async (id: string, chain: string[]) => {
      try {
        await updateModelDefault.mutateAsync({ id, data: { fallback_chain: chain } });
        toast.success("Fallback chain updated");
      } catch {
        toast.error("Failed to update fallback chain");
      }
    },
    [updateModelDefault]
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
              {[1, 2].map((i) => (
                <div
                  key={i}
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
            <h3 className="mb-2 text-lg font-medium text-primary">
              Failed to load model defaults
            </h3>
            <p className="mb-4 text-sm text-muted">
              {error instanceof Error
                ? error.message
                : "An error occurred while fetching model defaults."}
            </p>
            <Button
              onClick={handleRetry}
              variant="secondary"
              disabled={isRetrying}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              {isRetrying ? "Retrying..." : "Retry"}
            </Button>
          </div>
        </div>
      ) : modelDefaults.length === 0 ? (
        <div className="rounded-lg border border-border-default bg-surface-primary p-8">
          <EmptyState
            icon={Bot}
            title="No model defaults configured"
            description="Model defaults and fallback chains will appear here once providers are connected and models are available."
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

          {showFallbackChain ? (
            <section className="space-y-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="font-mono text-2xs font-medium uppercase tracking-wider text-muted">
                    Fallback Chain
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm text-secondary">
                  <Switch
                    checked={fallbackChainEnabled}
                    onCheckedChange={(checked) =>
                      updateAppSettings.mutateAsync({ fallback_chain_enabled: checked })
                    }
                    aria-label="Enable fallback chain"
                    disabled={updateAppSettings.isPending}
                  />
                  Enabled
                </label>
              </div>
              <FallbackChainSection
                enabled={fallbackChainEnabled}
                modelDefaults={modelDefaults}
                onReorder={handleReorderChain}
              />
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}
