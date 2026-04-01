import type { SoulFormValues } from "./useSoulForm";
import { SoulAdvancedSection } from "./SoulAdvancedSection";
import { SoulIdentitySection } from "./SoulIdentitySection";
import { SoulModelSection } from "./SoulModelSection";
import { SoulPromptSection } from "./SoulPromptSection";
import {
  SoulToolsSection,
  type AvailableTool,
  type WorkflowToolContext,
} from "./SoulToolsSection";

interface SoulFormBodyProps {
  values: SoulFormValues;
  workflowTools?: WorkflowToolContext[];
  availableTools?: AvailableTool[];
  setField: <K extends keyof SoulFormValues>(field: K, value: SoulFormValues[K]) => void;
  errors?: Partial<Record<keyof SoulFormValues, string>>;
}

export function SoulFormBody({
  values,
  workflowTools,
  availableTools,
  setField,
  errors,
}: SoulFormBodyProps) {
  return (
    <div className="space-y-4">
      <div className="sr-only">
        {availableTools?.map((tool) => (
          <span key={`${tool.slug}-type`}>{tool.type}</span>
        ))}
      </div>
      <SoulIdentitySection
        name={values.name}
        avatarColor={values.avatarColor}
        onNameChange={(value) => setField("name", value)}
        onAvatarColorChange={(value) => setField("avatarColor", value)}
      />
      <SoulModelSection
        providerId={values.providerId}
        modelId={values.modelId}
        provider={values.provider}
        providerError={errors?.provider}
        modelError={errors?.modelId}
        onProviderChange={(id, providerStr) => {
          setField("providerId", id);
          setField("provider", providerStr);
        }}
        onModelChange={(id) => setField("modelId", id)}
      />
      <SoulPromptSection
        systemPrompt={values.systemPrompt}
        onSystemPromptChange={(value) => setField("systemPrompt", value)}
      />
      <SoulToolsSection
        tools={values.tools}
        workflowTools={workflowTools}
        availableTools={availableTools}
        onToolsChange={(tools) => setField("tools", tools)}
      />
      <SoulAdvancedSection
        temperature={values.temperature}
        maxTokens={values.maxTokens}
        maxToolIterations={values.maxToolIterations}
        onTemperatureChange={(value) => setField("temperature", value)}
        onMaxTokensChange={(value) => setField("maxTokens", value)}
        onMaxToolIterationsChange={(value) => setField("maxToolIterations", value)}
      />
    </div>
  );
}

export type { SoulFormBodyProps };
