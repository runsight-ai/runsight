import type { ReactNode } from "react";

interface SelectionCardProps {
  selected: boolean;
  onSelect: () => void;
  children: ReactNode;
  label: string;
  title?: string;
  badge?: ReactNode;
  description?: string;
  footer?: ReactNode;
}

/**
 * A selectable card with role="radio" for the Setup Choose screen radiogroup.
 */
export function SelectionCard({
  selected,
  onSelect,
  children,
  label,
  title,
  badge,
  description,
  footer,
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
        "flex flex-col gap-4 rounded-xl border p-5 cursor-pointer text-left",
        "transition-[border-color,box-shadow] duration-200 ease-default",
        selected
          ? "border-accent-9 shadow-[0_0_0_1px_hsla(38,92%,55%,0.3)]"
          : "border-border-subtle bg-surface-secondary hover:border-border-hover",
      ].join(" ")}
    >
      {/* Header: title + badge */}
      {title && (
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-heading">{title}</span>
          {badge}
        </div>
      )}

      {/* Description */}
      {description && (
        <p className="text-sm text-secondary leading-relaxed">{description}</p>
      )}

      {/* Visual content (MiniDiagram or EmptyCanvasPreview) */}
      {children}

      {/* Footer */}
      {footer}
    </div>
  );
}
