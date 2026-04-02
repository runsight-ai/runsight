import { Label } from "@runsight/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import { AlertTriangle } from "lucide-react";

import { useModelsForProvider, useProviders } from "@/queries/settings";

import { SoulFormSection } from "./SoulFormSection";

interface SoulModelSectionProps {
  providerId: string | null;
  modelId: string | null;
  providerError?: string;
  modelError?: string;
  onProviderChange: (id: string | null) => void;
  onModelChange: (id: string | null) => void;
}

export function SoulModelSection({
  providerId,
  modelId,
  providerError,
  modelError,
  onProviderChange,
  onModelChange,
}: SoulModelSectionProps) {
  const providersQuery = useProviders();
  const allProviders = providersQuery.data?.items ?? [];
  const configuredProviders = allProviders.filter(
    (providerSummary) => providerSummary.is_active ?? true,
  );
  const currentProvider = allProviders.find(
    (providerSummary) => providerSummary.id === providerId,
  );
  const hasConfiguredProviders = configuredProviders.length > 0;
  const selectedProvider = configuredProviders.find(
    (providerSummary) => providerSummary.id === providerId,
  );
  const providerTriggerEnabled = hasConfiguredProviders || !!currentProvider;
  const currentProviderIsDisabled =
    !!currentProvider && !(currentProvider.is_active ?? true);
  const modelProviderType = selectedProvider?.type ?? null;
  const modelsQuery = useModelsForProvider(modelProviderType);
  const selectedProviderValue = selectedProvider?.id ?? undefined;
  const currentProviderLabel = currentProvider?.name ?? providerId ?? null;

  return (
    <SoulFormSection title="Model">
      <div className="space-y-5">
        <div className="space-y-2">
          <Label>Provider</Label>
          <Select
            value={selectedProviderValue}
            disabled={!providerTriggerEnabled}
            onValueChange={(value) => onProviderChange(value)}
          >
            <SelectTrigger aria-label="Select provider">
              {currentProviderIsDisabled && currentProviderLabel ? (
                <span className="truncate text-left text-primary">
                  {currentProviderLabel}
                </span>
              ) : (
                <SelectValue
                  placeholder={
                    hasConfiguredProviders ? "Select provider" : "No providers configured"
                  }
                />
              )}
            </SelectTrigger>
            <SelectContent>
              {configuredProviders.length > 0 ? (
                configuredProviders.map((providerSummary) => (
                  <SelectItem key={providerSummary.id} value={providerSummary.id}>
                    {providerSummary.name}
                  </SelectItem>
                ))
              ) : (
                <div className="px-[var(--space-2-5)] py-[var(--space-2)] text-sm text-muted">
                  No active providers available
                </div>
              )}
            </SelectContent>
          </Select>
          {currentProviderIsDisabled ? (
            <div className="flex items-center gap-2 text-sm text-warning-11">
              <AlertTriangle className="h-4 w-4 shrink-0 text-warning-9" />
              <span>
                This provider is disabled in Settings. Select an active provider
                to continue editing this soul.
              </span>
            </div>
          ) : !hasConfiguredProviders ? (
            <p className="text-sm text-muted">
              Add a provider in Settings before selecting a model.
            </p>
          ) : null}
          {providerError ? <p className="text-sm text-danger">{providerError}</p> : null}
        </div>

        <div className="space-y-2">
          <Label>Model</Label>
          <Select
            value={modelId ?? undefined}
            onValueChange={(value) => onModelChange(value)}
            disabled={!selectedProvider}
          >
            <SelectTrigger aria-label="Select model">
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              {(modelsQuery.data ?? []).map((model) => (
                <SelectItem key={model.model_id} value={model.model_id}>
                  {model.provider_name} - {model.model_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {modelError ? <p className="text-sm text-danger">{modelError}</p> : null}
        </div>
      </div>
    </SoulFormSection>
  );
}

export type { SoulModelSectionProps };
