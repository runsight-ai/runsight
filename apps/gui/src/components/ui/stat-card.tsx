import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

const statCardVariants = cva(
  // base — surface-tertiary, border, rounded bottom, padding, flex column
  [
    "bg-surface-tertiary border border-border-subtle",
    "border-t-[3px]",
    "rounded-none rounded-b-md",
    "p-4 flex flex-col gap-1",
    "transition-[border-top-color] duration-150 ease-[var(--ease-out)]",
    "hover:border-t-accent-7",
  ],
  {
    variants: {
      variant: {
        default: "border-t-border-default",
        accent:  "border-t-interactive-default",
        success: "border-t-success-9",
        danger:  "border-t-danger-9",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface StatCardProps
  extends React.ComponentProps<"div">,
    VariantProps<typeof statCardVariants> {
  /** Metric label — displayed uppercase in font-size-xs */
  label: string
  /** Metric value — displayed in font-mono font-size-3xl */
  value: React.ReactNode
  /** Optional delta/change/trend indicator (positive or negative) */
  delta?: React.ReactNode
  /** Optional icon displayed alongside the value */
  icon?: React.ReactNode
}

export function StatCard({
  label,
  value,
  delta,
  variant = "default",
  icon,
  className,
  ...props
}: StatCardProps) {
  const isPositiveDelta =
    typeof delta === "string" && (delta.startsWith("+") || delta.startsWith("↑"))
  const isNegativeDelta =
    typeof delta === "string" && (delta.startsWith("-") || delta.startsWith("↓"))

  return (
    <div
      data-slot="stat-card"
      data-variant={variant}
      className={cn(statCardVariants({ variant }), className)}
      {...props}
    >
      {/* Label — font-mono, 2xs, medium, wider tracking, uppercase, text-muted */}
      <span
        data-slot="stat-card-label"
        className="font-mono text-2xs font-medium tracking-wider uppercase text-muted"
      >
        {label}
      </span>

      {/* Value — font-mono, 3xl, bold, tighter tracking, tight leading, text-heading */}
      <span
        data-slot="stat-card-value"
        className="font-mono text-3xl font-bold tracking-tighter leading-tight text-heading"
      >
        {value}
      </span>

      {/* Delta / trend badge */}
      {delta !== undefined && delta !== null && (
        <span
          data-slot="stat-card-delta"
          className={cn(
            "font-mono text-xs flex items-center gap-1",
            isPositiveDelta && "text-success-11",
            isNegativeDelta && "text-danger-11",
          )}
        >
          {delta}
        </span>
      )}
    </div>
  )
}
