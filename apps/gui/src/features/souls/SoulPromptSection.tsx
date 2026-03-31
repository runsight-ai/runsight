import { Label } from "@runsight/ui/label";
import { Textarea } from "@runsight/ui/textarea";

import { SoulFormSection } from "./SoulFormSection";

interface SoulPromptSectionProps {
  systemPrompt: string;
  onSystemPromptChange: (value: string) => void;
}

export function SoulPromptSection({
  systemPrompt,
  onSystemPromptChange,
}: SoulPromptSectionProps) {
  return (
    <SoulFormSection title="Prompt">
      <div className="space-y-2">
        <Label htmlFor="soul-system-prompt">System Prompt</Label>
        <Textarea
          id="soul-system-prompt"
          value={systemPrompt}
          onChange={(event) => onSystemPromptChange(event.currentTarget.value)}
          placeholder="Define how this soul should behave."
          className="min-h-32"
        />
      </div>
    </SoulFormSection>
  );
}

export type { SoulPromptSectionProps };
