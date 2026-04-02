import { Label } from "@runsight/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";

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
  const configuredProviders = (providersQuery.data?.items ?? []).filter(
    (providerSummary) => providerSummary.is_active ?? true,
  );
  const hasConfiguredProviders = configuredProviders.length > 0;
  const selectedProvider = configuredProviders.find(
    (providerSummary) => providerSummary.id === providerId,
  );
  const modelProviderType = selectedProvider?.type ?? null;
  const modelsQuery = useModelsForProvider(modelProviderType);
  const selectedProviderValue = selectedProvider?.id ?? undefined;

  return (
    <SoulFormSection title="Model">
      <div className="space-y-5">
        <div className="space-y-2">
          <Label>Provider</Label>
          <Select
            value={selectedProviderValue}
            disabled={!hasConfiguredProviders}
            onValueChange={(value) => onProviderChange(value)}
          >
            <SelectTrigger aria-label="Select provider">
              <SelectValue
                placeholder={
                  hasConfiguredProviders ? "Select provider" : "No providers configured"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {configuredProviders.map((providerSummary) => (
                <SelectItem key={providerSummary.id} value={providerSummary.id}>
                  {providerSummary.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!hasConfiguredProviders ? (
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
            disabled={!providerId || !hasConfiguredProviders}
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
