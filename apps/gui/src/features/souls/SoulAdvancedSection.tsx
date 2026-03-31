import { Input } from "@runsight/ui/input";
import { Label } from "@runsight/ui/label";
import { Slider } from "@runsight/ui/slider";

import { SoulFormSection } from "./SoulFormSection";

interface SoulAdvancedSectionProps {
  temperature: number;
  maxTokens: number | null;
  maxToolIterations: number;
  onTemperatureChange: (v: number) => void;
  onMaxTokensChange: (v: number | null) => void;
  onMaxToolIterationsChange: (v: number) => void;
}

export function SoulAdvancedSection({
  temperature,
  maxTokens,
  maxToolIterations,
  onTemperatureChange,
  onMaxTokensChange,
  onMaxToolIterationsChange,
}: SoulAdvancedSectionProps) {
  return (
    <SoulFormSection title="Advanced" collapsible defaultOpen={false}>
      <div className="space-y-5">
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="soul-temperature">Temperature</Label>
            <span className="text-sm text-muted">{temperature.toFixed(1)}</span>
          </div>
          <Slider
            id="soul-temperature"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            onChange={(event) => onTemperatureChange(Number(event.currentTarget.value))}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="soul-max-tokens">Max Tokens</Label>
          <Input
            id="soul-max-tokens"
            type="number"
            value={maxTokens ?? ""}
            onChange={(event) => {
              const nextValue = event.currentTarget.value;
              onMaxTokensChange(nextValue === "" ? null : Number(nextValue));
            }}
            placeholder="Default"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="soul-max-tool-iterations">Max Tool Iterations</Label>
          <Input
            id="soul-max-tool-iterations"
            type="number"
            min={1}
            max={50}
            value={maxToolIterations}
            onChange={(event) =>
              onMaxToolIterationsChange(Number(event.currentTarget.value))
            }
          />
        </div>
      </div>
    </SoulFormSection>
  );
}

export type { SoulAdvancedSectionProps };
