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
    bg: "bg-[rgba(40,167,69,0.12)]",
    text: "text-[var(--success)]",
    dot: "bg-[var(--success)]",
    defaultLabel: "Completed",
  },
  error: {
    bg: "bg-[rgba(229,57,53,0.12)]",
    text: "text-[var(--error)]",
    dot: "bg-[var(--error)]",
    defaultLabel: "Failed",
  },
  warning: {
    bg: "bg-[rgba(245,166,35,0.12)]",
    text: "text-[var(--warning)]",
    dot: "bg-[var(--warning)]",
    defaultLabel: "Warning",
  },
  running: {
    bg: "bg-[rgba(0,229,255,0.12)]",
    text: "text-[var(--running)]",
    dot: "bg-[var(--running)]",
    defaultLabel: "Running",
  },
  pending: {
    bg: "bg-[rgba(146,146,160,0.12)]",
    text: "text-[var(--muted-foreground)]",
    dot: "bg-[var(--muted-foreground)]",
    defaultLabel: "Pending",
  },
  cancelled: {
    bg: "bg-[rgba(146,146,160,0.12)]",
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
