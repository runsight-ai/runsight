import { cn } from "@runsight/ui/utils";

const AVATAR_COLOR_OPTIONS = [
  { value: "accent", swatchClassName: "bg-accent-8" },
  { value: "info", swatchClassName: "bg-info-9" },
  { value: "success", swatchClassName: "bg-success-9" },
  { value: "warning", swatchClassName: "bg-warning-9" },
  { value: "danger", swatchClassName: "bg-danger-9" },
  { value: "neutral", swatchClassName: "bg-neutral-8" },
];

interface SoulAvatarColorPickerProps {
  value: string;
  onChange: (value: string) => void;
}

export function SoulAvatarColorPicker({ value, onChange }: SoulAvatarColorPickerProps) {
  return (
    <div
      role="group"
      aria-label="Avatar color"
      className="flex flex-wrap items-center gap-3"
    >
      {AVATAR_COLOR_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-label={`${option.value} avatar color`}
          aria-pressed={value === option.value}
          className={cn(
            "flex size-9 items-center justify-center rounded-full border transition",
            value === option.value
              ? "border-accent-8 bg-accent-3/30 shadow-[0_0_0_1px_var(--accent-8)]"
              : "border-border-default bg-surface-secondary hover:border-border-strong",
          )}
        >
          <span
            className={cn(
              "size-5 rounded-full border border-white/10 shadow-sm",
              option.swatchClassName,
            )}
          />
          <span className="sr-only">{option.value}</span>
        </button>
        
      ))}
    </div>
  );
}

export type { SoulAvatarColorPickerProps };
