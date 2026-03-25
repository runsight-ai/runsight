import { cn } from "@/utils/helpers";
import { Button } from "@/components/ui/button";
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
      {/* Icon — .empty-state__icon */}
      <Icon
        data-slot="empty-state-icon"
        className="empty-state__icon"
        aria-hidden="true"
      />

      {/* Title — .empty-state__title */}
      <p
        data-slot="empty-state-title"
        className="empty-state__title"
      >
        {title}
      </p>

      {/* Description — .empty-state__description */}
      {description && (
        <p
          data-slot="empty-state-description"
          className="empty-state__description"
        >
          {description}
        </p>
      )}

      {/* Optional CTA */}
      {action && (
        <Button variant="primary" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
