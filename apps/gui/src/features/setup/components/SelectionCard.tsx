import type { ReactNode } from "react";

interface SelectionCardProps {
  selected: boolean;
  onSelect: () => void;
  children: ReactNode;
  label: string;
}

/**
 * A selectable card with role="radio" for the Setup Choose screen radiogroup.
 */
export function SelectionCard({
  selected,
  onSelect,
  children,
  label,
}: SelectionCardProps) {
  return (
    <div
      role="radio"
      aria-checked={selected}
      aria-label={label}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className={[
        "flex flex-col gap-3 rounded-lg border-2 p-4 cursor-pointer transition-colors duration-100",
        selected
          ? "border-accent-9 bg-accent-2"
          : "border-border-default bg-surface-primary hover:border-border-hover",
      ].join(" ")}
    >
      {children}
    </div>
  );
}
