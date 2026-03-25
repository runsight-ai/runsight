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
      className={cn("empty-state", className)}
      style={{ gap: "var(--space-6)" }}
    >
      {/* Icon container */}
      <div
        className="flex items-center justify-center rounded-lg bg-surface-tertiary"
        style={{ padding: "var(--space-3)" }}
      >
        <Icon
          className="text-muted"
          style={{
            width: "var(--icon-size-xl)",
            height: "var(--icon-size-xl)",
          }}
          aria-hidden="true"
        />
      </div>

      {/* Text block */}
      <div className="flex flex-col" style={{ gap: "var(--space-2)" }}>
        <h3
          className="text-heading font-medium"
          style={{ fontSize: "var(--font-size-lg)" }}
        >
          {title}
        </h3>
        {description && (
          <p
            className="text-secondary max-w-xs"
            style={{ fontSize: "var(--font-size-sm)" }}
          >
            {description}
          </p>
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
