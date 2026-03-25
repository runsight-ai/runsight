import { cn } from "@/utils/helpers";

export type StatusVariant =
  | "success"
  | "error"
  | "warning"
  | "running"
  | "pending"
  | "cancelled";

interface StatusBadgeProps {
  status: StatusVariant;
  label?: string;
  className?: string;
}

const statusConfig: Record<
  StatusVariant,
  { modifier: string; defaultLabel: string }
> = {
  success: {
    modifier: "badge--success",
    defaultLabel: "Completed",
  },
  error: {
    modifier: "badge--danger",
    defaultLabel: "Failed",
  },
  warning: {
    modifier: "badge--warning",
    defaultLabel: "Warning",
  },
  running: {
    modifier: "badge--info",
    defaultLabel: "Running",
  },
  pending: {
    modifier: "badge--neutral",
    defaultLabel: "Pending",
  },
  cancelled: {
    modifier: "badge--neutral",
    defaultLabel: "Cancelled",
  },
};

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  const displayLabel = label ?? config.defaultLabel;

  return (
    <div className={cn("badge", config.modifier, className)}>
      <span className="badge__dot" />
      <span>{displayLabel}</span>
    </div>
  );
}
