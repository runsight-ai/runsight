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
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-space-6 text-center",
        className
      )}
    >
      {/* Icon container — icon-size-xl controls dimensions */}
      <div className="flex items-center justify-center rounded-radius-lg bg-surface-tertiary p-space-3">
        <Icon
          className="text-muted"
          style={{ width: "var(--icon-size-xl)", height: "var(--icon-size-xl)" }}
          aria-hidden="true"
        />
      </div>

      {/* Text block */}
      <div className="flex flex-col gap-space-2">
        <h3 className="text-heading text-font-size-lg font-medium">{title}</h3>
        {description && (
          <p className="max-w-xs text-secondary text-font-size-sm">{description}</p>
        )}
      </div>

      {/* Optional CTA */}
      {action && (
        <Button variant="outline" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
