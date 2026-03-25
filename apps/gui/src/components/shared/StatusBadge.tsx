import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/utils/helpers";

// ---------------------------------------------------------------------------
// CVA variant — maps to the badge spec in components.css
// Base: inline-flex, font-mono, font-size-2xs, tracking-wide, uppercase,
//       radius-full, border, whitespace-nowrap
// ---------------------------------------------------------------------------

const badgeVariants = cva(
  [
    "inline-flex items-center gap-1",
    "px-2 py-0.5",
    "font-mono text-[length:var(--font-size-2xs)] font-medium",
    "tracking-[var(--tracking-wide)] uppercase",
    "leading-[var(--line-height-tight)]",
    "rounded-full border border-transparent",
    "whitespace-nowrap",
  ].join(" "),
  {
    variants: {
      variant: {
        success: "bg-(--success-3) text-(--success-11)",
        danger:  "bg-(--danger-3)  text-(--danger-11)",
        warning: "bg-(--warning-3) text-(--warning-11)",
        info:    "bg-(--info-3)    text-(--info-11)",
        neutral: "bg-(--neutral-3) text-(--neutral-10)",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  }
);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// Maps StatusVariant → badge CVA variant + default label
const statusConfig: Record<
  StatusVariant,
  { variant: VariantProps<typeof badgeVariants>["variant"]; defaultLabel: string }
> = {
  success:   { variant: "success", defaultLabel: "Completed" },
  error:     { variant: "danger",  defaultLabel: "Failed"    },
  warning:   { variant: "warning", defaultLabel: "Warning"   },
  running:   { variant: "info",    defaultLabel: "Running"   },
  pending:   { variant: "neutral", defaultLabel: "Pending"   },
  cancelled: { variant: "neutral", defaultLabel: "Cancelled" },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  const displayLabel = label ?? config.defaultLabel;

  return (
    <div className={cn(badgeVariants({ variant: config.variant }), className)}>
      {/* Dot indicator */}
      <span
        className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0"
        aria-hidden="true"
      />
      <span>{displayLabel}</span>
    </div>
  );
}
