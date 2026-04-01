import type { SoulFormValues } from "./useSoulForm";
import { SoulAdvancedSection } from "./SoulAdvancedSection";
import { SoulIdentitySection } from "./SoulIdentitySection";
import { SoulModelSection } from "./SoulModelSection";
import { SoulPromptSection } from "./SoulPromptSection";
import { SoulToolsSection, type WorkflowToolContext } from "./SoulToolsSection";

interface SoulFormBodyProps {
  values: SoulFormValues;
  workflowTools?: WorkflowToolContext[];
  setField: <K extends keyof SoulFormValues>(field: K, value: SoulFormValues[K]) => void;
  errors?: Partial<Record<keyof SoulFormValues, string>>;
}

export function SoulFormBody({
  values,
  workflowTools,
  setField,
  errors,
}: SoulFormBodyProps) {
  return (
    <div className="space-y-4">
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
