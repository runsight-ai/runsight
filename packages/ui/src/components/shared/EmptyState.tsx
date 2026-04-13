import { cn } from "../../utils/helpers";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      data-slot="empty-state"
      className={cn(
        "flex flex-col items-center justify-center gap-3",
        "px-4 py-12 text-center",
        className
      )}
    >
      {/* Icon — w-12 / h-12, muted + half-opacity */}
      <div
        data-slot="empty-state-icon"
        className="w-12 h-12 text-(--text-muted) opacity-50"
      >
        <Icon
          width={48}
          height={48}
          aria-hidden="true"
        />
      </div>

      {/* Title */}
      <h2
        data-slot="empty-state-title"
        className="m-0 text-[length:var(--font-size-lg)] font-medium text-(--text-primary)"
      >
        {title}
      </h2>

      {/* Description */}
      {description && (
        <div
          data-slot="empty-state-description"
          className="text-[length:var(--font-size-sm)] text-(--text-secondary) max-w-[36ch]"
        >
          {description}
        </div>
      )}

      {/* Optional CTA */}
      {action && (
        <button
          type="button"
          className={[
            "inline-flex items-center justify-center gap-1.5",
            "h-(--control-height-sm) px-3",
            "text-[length:var(--font-size-sm)] font-medium",
            "bg-(--interactive-default) text-(--text-on-accent)",
            "border border-(--interactive-default)",
            "rounded-[var(--radius-md)]",
            "cursor-pointer select-none whitespace-nowrap",
            "transition-[background,border-color,color,box-shadow] duration-100",
            "hover:bg-(--interactive-hover) hover:border-(--interactive-hover)",
            "active:bg-(--interactive-active)",
            "focus-visible:outline focus-visible:outline-[var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:outline-offset-[var(--focus-ring-offset)]",
            "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none",
          ].join(" ")}
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
