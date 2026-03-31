import { Radio, RadioGroup } from "@runsight/ui/radio";

const AVATAR_COLOR_OPTIONS = [
  { value: "accent", swatchClassName: "bg-accent-3" },
  { value: "info", swatchClassName: "bg-info-3" },
  { value: "success", swatchClassName: "bg-success-3" },
  { value: "warning", swatchClassName: "bg-warning-3" },
  { value: "danger", swatchClassName: "bg-danger-3" },
  { value: "neutral", swatchClassName: "bg-neutral-3" },
];

interface SoulAvatarColorPickerProps {
  value: string;
  onChange: (value: string) => void;
}

export function SoulAvatarColorPicker({ value, onChange }: SoulAvatarColorPickerProps) {
  return (
    <RadioGroup orientation="horizontal" className="gap-3">
      {AVATAR_COLOR_OPTIONS.map((option) => (
        <label key={option.value} className="inline-flex items-center gap-2 cursor-pointer">
          <Radio
            checked={value === option.value}
            onChange={() => onChange(option.value)}
            value={option.value}
            aria-label={`${option.value} avatar color`}
          />
          <span className={`size-5 rounded-full border border-border-default ${option.swatchClassName}`} />
        </label>
      ))}
    </RadioGroup>
  );
}

export type { SoulAvatarColorPickerProps };
