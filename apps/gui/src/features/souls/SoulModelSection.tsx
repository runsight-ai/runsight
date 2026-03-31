import { Label } from "@runsight/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";

import { useModelProviders, useModelsForProvider } from "@/queries/settings";

import { SoulFormSection } from "./SoulFormSection";

interface SoulModelSectionProps {
  providerId: string | null;
  modelId: string | null;
  provider: string | null;
  providerError?: string;
  modelError?: string;
  onProviderChange: (id: string | null, providerStr: string | null) => void;
  onModelChange: (id: string | null) => void;
}

export function SoulModelSection({
  providerId,
  modelId,
  provider,
  providerError,
  modelError,
  onProviderChange,
  onModelChange,
}: SoulModelSectionProps) {
  const providersQuery = useModelProviders();
  const modelsQuery = useModelsForProvider(provider);

  return (
    <SoulFormSection title="Model">
      <div className="space-y-5">
        <div className="space-y-2">
          <Label>Provider</Label>
          <Select
            value={providerId ?? undefined}
            onValueChange={(value) => onProviderChange(value, value)}
          >
            <SelectTrigger aria-label="Select provider">
              <SelectValue placeholder="Select provider" />
            </SelectTrigger>
            <SelectContent>
              {(providersQuery.data ?? []).map((providerSummary) => (
                <SelectItem key={providerSummary.id} value={providerSummary.id}>
                  {providerSummary.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {providerError ? <p className="text-sm text-danger">{providerError}</p> : null}
          {(providersQuery.data ?? []).map((providerSummary) =>
            providerSummary.id === providerId && providerSummary.is_configured === false ? (
              <p
                key={`${providerSummary.id}-warning`}
                className="text-sm text-[var(--warning-11)]"
              >
                {providerSummary.name} is not configured yet.
              </p>
            ) : null,
          )}
        </div>

        <div className="space-y-2">
          <Label>Model</Label>
          <Select
            value={modelId ?? undefined}
            onValueChange={(value) => onModelChange(value)}
            disabled={!provider}
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
