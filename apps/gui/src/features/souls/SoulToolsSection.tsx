import { TagInput } from "@runsight/ui/tag-input";

import { SoulFormSection } from "./SoulFormSection";

interface SoulToolsSectionProps {
  tools: string[];
  onToolsChange: (tools: string[]) => void;
}

export function SoulToolsSection({ tools, onToolsChange }: SoulToolsSectionProps) {
  return (
    <SoulFormSection title="Tools" collapsible defaultOpen={false}>
      <TagInput
        label="Tools"
        placeholder="Add a tool"
        tags={tools}
        onChange={onToolsChange}
      />
    </SoulFormSection>
  );
}

export type { SoulToolsSectionProps };
