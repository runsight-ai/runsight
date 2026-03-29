import { useState, useCallback, useEffect, useMemo } from "react";
import {
  useModelDefaults,
  useProviders,
  useUpdateModelDefault,
} from "@/queries/settings";
import { EmptyState } from "@runsight/ui/empty-state";
import { Button } from "@runsight/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import { Bot, Check, X, ChevronUp, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import type { ModelDefault } from "@/api/settings";

function ModelRow({
  model,
  availableModels,
  onSave,
  onCancel,
}: {
  model: ModelDefault;
  availableModels: string[];
  onSave: (id: string, modelName: string) => void;
  onCancel: () => void;
}) {
  const [selectedModel, setSelectedModel] = useState(model.model_name);
  const hasChanges = selectedModel !== model.model_name;
  const models = availableModels.length > 0 ? availableModels : [model.model_name];

  return (
    <div className="flex items-center justify-between gap-4 border-b border-border-default py-3 last:border-0">
      <span className="w-28 shrink-0 text-sm font-medium text-primary">
        {model.provider_name}
      </span>
      <div className="flex flex-1 items-center gap-2">
        <Select
          value={selectedModel}
          onValueChange={(v) => v && setSelectedModel(v)}
        >
          <SelectTrigger className="h-8 min-w-[180px] rounded-lg border-border-default bg-surface-secondary">
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
          <div className="flex items-center gap-1">
            <Button
              variant="icon-only"
              size="sm"
              className="h-8 w-8 text-[var(--success-9)] hover:text-[var(--success-9)]"
              onClick={() => onSave(model.id, selectedModel)}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              variant="icon-only"
              size="sm"
              className="h-8 w-8 text-muted"
              onClick={onCancel}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function FallbackChainSection({
  modelDefaults,
  onReorder,
}: {
  modelDefaults: ModelDefault[];
  onReorder: (id: string, chain: string[]) => void;
}) {
  const primary = modelDefaults.find((m) => m.is_default) ?? modelDefaults[0];
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
    onReorder(primary.id, localChain);
    setHasChanges(false);
  }, [primary.id, localChain, onReorder]);

  const handleCancel = useCallback(() => {
    setLocalChain(primaryFallbackChain);
    setHasChanges(false);
  }, [primaryFallbackChain]);

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
        <span className="text-sm text-muted">
          Retry order when primary fails
        </span>
        {hasChanges && (
          <div className="flex items-center gap-1">
            <Button
              variant="secondary"
              size="sm"
              className="h-7 text-xs"
              onClick={handleSave}
            >
              Save order
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={handleCancel}
            >
              Cancel
            </Button>
          </div>
        )}
      </div>
      <ul className="space-y-2">
        {localChain.map((name, i) => (
          <li
            key={`${name}-${i}`}
            className="flex items-center gap-2 rounded-md border border-border-default bg-surface-secondary px-3 py-2 text-sm"
          >
            <div className="flex shrink-0 gap-0.5">
              <Button
                variant="icon-only"
                size="sm"
                className="h-6 w-6"
                onClick={() => move(i, -1)}
                disabled={i === 0}
              >
                <ChevronUp className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="icon-only"
                size="sm"
                className="h-6 w-6"
                onClick={() => move(i, 1)}
                disabled={i === localChain.length - 1}
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </Button>
            </div>
            <span className="flex-1 font-medium text-primary">{name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ModelsTab() {
  const { data, isLoading } = useModelDefaults();
  const { data: providersData } = useProviders();
  const updateModelDefault = useUpdateModelDefault();
  const modelDefaults = data?.items ?? [];
  const providers = useMemo(() => providersData?.items ?? [], [providersData?.items]);

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

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight text-primary">
          Models
        </h2>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-lg border border-border-default bg-surface-secondary"
            />
          ))}
        </div>
      ) : modelDefaults.length === 0 ? (
        <div className="rounded-lg border border-border-default bg-surface-secondary p-8">
          <EmptyState
            icon={Bot}
            title="No model defaults configured"
            description="Model defaults and fallback chains will appear here once providers are connected and models are available."
          />
        </div>
      ) : (
        <div className="space-y-6">
          <section className="rounded-lg border border-border-default bg-surface-secondary p-5">
            <h3 className="mb-4 text-base font-medium text-primary">
              Default Models per Provider
            </h3>
            <p className="mb-6 text-sm text-muted">
              Select the default model for each provider. Souls without an
              explicit model will use these defaults.
            </p>

            <div className="space-y-0">
              {modelDefaults.map((model) => (
                <ModelRow
                  key={model.id}
                  model={model}
                  availableModels={model.provider_id ? getProviderModels(model.provider_id) : []}
                  onSave={handleSaveModel}
                  onCancel={() => {}}
                />
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-border-default bg-surface-secondary p-5">
            <div className="mb-4">
              <h3 className="text-base font-medium text-primary">
                Fallback Chain
              </h3>
              <p className="mt-1 text-sm text-muted">
                When the primary model fails (rate limit, error), the system
                retries with the next model in chain.
              </p>
            </div>
            <FallbackChainSection
              modelDefaults={modelDefaults}
              onReorder={handleReorderChain}
            />
          </section>
        </div>
      )}
    </div>
  );
}
