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
  { bg: string; text: string; dot: string; defaultLabel: string }
> = {
  success: {
    bg: "bg-[var(--success-12)]",
    text: "text-[var(--success-9)]",
    dot: "bg-[var(--success-9)]",
    defaultLabel: "Completed",
  },
  error: {
    bg: "bg-[var(--error-12)]",
    text: "text-[var(--danger-9)]",
    dot: "bg-[var(--danger-9)]",
    defaultLabel: "Failed",
  },
  warning: {
    bg: "bg-[var(--warning-12)]",
    text: "text-[var(--warning-9)]",
    dot: "bg-[var(--warning-9)]",
    defaultLabel: "Warning",
  },
  running: {
    bg: "bg-[var(--running-12)]",
    text: "text-[var(--info-9)]",
    dot: "bg-[var(--info-9)]",
    defaultLabel: "Running",
  },
  pending: {
    bg: "bg-[var(--muted-12)]",
    text: "text-[var(--muted-foreground)]",
    dot: "bg-[var(--muted-foreground)]",
    defaultLabel: "Pending",
  },
  cancelled: {
    bg: "bg-[var(--muted-12)]",
    text: "text-[var(--muted-foreground)]",
    dot: "bg-[var(--muted-foreground)]",
    defaultLabel: "Cancelled",
  },
};

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  const displayLabel = label ?? config.defaultLabel;

  return (
    <div
      className={cn(
        "inline-flex h-[22px] items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium uppercase",
        config.bg,
        config.text,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      <span>{displayLabel}</span>
    </div>
  );
}
