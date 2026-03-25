import { cn } from "@/utils/helpers";
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
    <div className={cn("empty-state", className)}>
      {/* Icon — .empty-state__icon wraps a 48x48 SVG */}
      <div
        data-slot="empty-state-icon"
        className="empty-state__icon"
      >
        <Icon
          width={48}
          height={48}
          aria-hidden="true"
        />
      </div>

      {/* Title — .empty-state__title */}
      <div
        data-slot="empty-state-title"
        className="empty-state__title"
      >
        {title}
      </div>

      {/* Description — .empty-state__description */}
      {description && (
        <div
          data-slot="empty-state-description"
          className="empty-state__description"
        >
          {description}
        </div>
      )}

      {/* Optional CTA */}
      {action && (
        <button
          type="button"
          className="btn btn--primary"
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
